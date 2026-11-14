"""Tests for run_shards.py: a synthetic pipeline run over several packs and parts (synthetic_run.py), a made-up pack table,
and the real shard_writer.py with G6's baseline tokenizer (--any-tokenizer, as in test_shard_writer.py).

  python -m pytest teams/01-data-a/shards/tests/test_run_shards.py
"""
import json
import sys
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow")
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from synthetic_run import make_run  # noqa: E402  (also puts shards/ and pipeline/ on the path)
import run_shards as rs  # noqa: E402  (imports shard_writer, which puts G6's folder on the path)
from dataio.tokenizer import BrahmicTokenizer  # noqa: E402

BASE = BrahmicTokenizer().path
TEXTS = ["The water cycle moves water between the sea, the air and the land.\n",
         "package main\n\nfunc area(r float64) float64 {\n\treturn 3.14159 * r * r\n}\n",
         "पानी समुद्र, हवा और ज़मीन के बीच घूमता है।\n"]
TABLE = {"packs": {
    "pk-a": {"language": "go", "script": "Latn", "domain": "code", "lane": "code"},
    "pk-b": {"language": "en", "script": "Latn", "domain": "english", "lane": "general"},
    "pk-nolane": {"language": "en", "script": "Latn", "domain": "english", "lane": None},
}}


def rows(pack, tag):
    return [{"doc_id": f"{tag}{k}", "text": t, "url": "", "lang_label": "en", "pack_id": pack} for k, t in enumerate(TEXTS)]


@pytest.fixture
def run(tmp_path, monkeypatch):
    """A finished run over pk-a part-00000 and part-00001, pk-b part-00000, pk-nolane part-00000 and a held-out pk-a part."""
    parts = {("train", "pk-a/part-00000.parquet"): rows("pk-a", "a0_"), ("train", "pk-a/part-00001.parquet"): rows("pk-a", "a1_"),
             ("train", "pk-b/part-00000.parquet"): rows("pk-b", "b0_"), ("train", "pk-nolane/part-00000.parquet"): rows("pk-nolane", "n0_"),
             ("heldout", "pk-a/part-00000.parquet"): rows("pk-a", "h0_")}
    return make_run(tmp_path / "pipeline", monkeypatch, parts)


@pytest.fixture
def table(tmp_path):
    path = tmp_path / "pack_table.json"
    path.write_text(json.dumps(TABLE), encoding="utf-8")
    return path


def go(run, tmp_path, table, *extra, out="shards"):
    out = tmp_path / out
    code = rs.main(["--input", str(run / "final"), "--manifest", str(run / "pipeline_manifest.json"), "--tokenizer", str(BASE),
                    "--any-tokenizer", "--pack-table", str(table), "--out", str(out), *extra])
    return code, out, json.loads((out / "shards_summary.json").read_text(encoding="utf-8"))


def test_every_part_gets_its_shard_and_the_table_row(run, tmp_path, table):
    code, out, s = go(run, tmp_path, table, "--pack", "pk-a", "--pack", "pk-b")
    written = {k: v for k, v in s["parts"].items() if v["status"] == "written"}
    assert sorted(written) == ["train/pk-a/part-00000.parquet", "train/pk-a/part-00001.parquet", "train/pk-b/part-00000.parquet"]
    assert [written[k]["shard_id"] for k in sorted(written)] == ["pk-a-train-000000", "pk-a-train-000001", "pk-b-train-000000"]
    m = json.loads((out / "pk-b-train-000000.json").read_text(encoding="utf-8"))
    assert (m["language"], m["script"], m["domain"], m["capability_lane"]) == ("en", "Latn", "english", "general")
    assert all(v["docs"] == 3 and not v["truncated"] and v["rows_read"] == v["rows_in_part"] == 3 for v in written.values())
    assert sorted(p.name for p in out.glob("*.bin")) == ["pk-a-train-000000.bin", "pk-a-train-000001.bin", "pk-b-train-000000.bin"]
    assert len(set((out / n).read_bytes() for n in ("pk-a-train-000000.json", "pk-a-train-000001.json"))) == 2
    assert len(list(out.glob("cleaning_pipeline.json"))) == 1  # one file for the whole run


def test_a_pack_without_a_lane_or_row_is_skipped_and_the_rest_written(run, tmp_path, table):
    code, out, s = go(run, tmp_path, table, "--pack", "pk-nolane", "--pack", "pk-b")
    assert code == 1
    assert s["parts"]["train/pk-nolane/part-00000.parquet"]["status"] == "skipped"
    assert "no lane" in s["parts"]["train/pk-nolane/part-00000.parquet"]["reason"]
    assert s["parts"]["train/pk-b/part-00000.parquet"]["status"] == "written"
    assert s["counts"] == {"written": 1, "failed": 0, "skipped": 1, "truncated": 0}
    assert not list(out.glob("pk-nolane*"))
    table.write_text(json.dumps({"packs": {}}), encoding="utf-8")
    code, _, s = go(run, tmp_path, table, "--pack", "pk-b", out="shards2")
    assert code == 1 and "not in pack_table.json" in s["parts"]["train/pk-b/part-00000.parquet"]["reason"]


def test_a_held_out_part_fails_in_the_writer_and_the_others_still_run(run, tmp_path, table):
    code, out, s = go(run, tmp_path, table, "--pack", "pk-a")
    assert code == 1
    failed = s["parts"]["heldout/pk-a/part-00000.parquet"]
    assert failed["status"] == "failed" and "heldout part" in failed["reason"] and "G3 and G9" in failed["reason"]
    assert s["counts"] == {"written": 2, "failed": 1, "skipped": 0, "truncated": 0}


def test_a_part_whose_file_changed_after_f2_fails_alone(run, tmp_path, table):
    path = run / "final" / "train" / "pk-a" / "part-00001.parquet"
    pq.write_table(pa.Table.from_pylist(rows("pk-a", "x_")), path)
    code, out, s = go(run, tmp_path, table, "--pack", "pk-a")
    assert s["parts"]["train/pk-a/part-00001.parquet"]["status"] == "failed"
    assert s["parts"]["train/pk-a/part-00000.parquet"]["status"] == "written"
    assert not (out / "pk-a-train-000001.json").exists()


def test_an_existing_shard_stops_the_run_before_anything_is_written(run, tmp_path, table):
    go(run, tmp_path, table, "--pack", "pk-b")
    out = tmp_path / "shards"
    before = sorted(p.name for p in out.iterdir())
    with pytest.raises(SystemExit, match="already in .*pk-b-train-000000.json"):
        go(run, tmp_path, table, "--pack", "pk-a", "--pack", "pk-b")
    assert sorted(p.name for p in out.iterdir()) == before  # pk-a was not started


def test_a_second_run_for_other_packs_adds_to_the_summary(run, tmp_path, table):
    go(run, tmp_path, table, "--pack", "pk-b")
    code, out, s = go(run, tmp_path, table, "--pack", "pk-a")
    assert sorted(v["shard_id"] for v in s["parts"].values() if v["status"] == "written") == \
        ["pk-a-train-000000", "pk-a-train-000001", "pk-b-train-000000"]
    assert code == 1  # this run's held-out pk-a part failed


def test_a_summary_from_another_run_is_refused(run, tmp_path, table):
    go(run, tmp_path, table, "--pack", "pk-b")
    summary = tmp_path / "shards" / "shards_summary.json"
    s = json.loads(summary.read_text(encoding="utf-8"))
    s["manifest_sha256"] = "0" * 64
    summary.write_text(json.dumps(s), encoding="utf-8")
    with pytest.raises(SystemExit, match="another pipeline run"):
        go(run, tmp_path, table, "--pack", "pk-a")


def test_a_part_that_does_not_fit_is_flagged_truncated(run, tmp_path, table):
    code, out, s = go(run, tmp_path, table, "--pack", "pk-b", "--tokens", "40")
    e = s["parts"]["train/pk-b/part-00000.parquet"]
    assert e["truncated"] is True and e["rows_read"] < e["rows_in_part"] == 3 and e["docs"] < 3
    assert s["counts"]["truncated"] == 1 and code == 0  # truncated is a warning: the part was written


def test_a_part_not_named_part_number_fails(run, tmp_path, table):
    odd = run / "final" / "train" / "pk-b" / "other.parquet"
    (run / "final" / "train" / "pk-b" / "part-00000.parquet").rename(odd)
    code, out, s = go(run, tmp_path, table, "--pack", "pk-b")
    assert code == 1 and "not named part-<number>.parquet" in s["parts"]["train/pk-b/other.parquet"]["reason"]


def test_no_parts_is_an_error(run, tmp_path, table):
    with pytest.raises(SystemExit, match="no <split>/<pack>/<part>.parquet"):
        go(run, tmp_path, table, "--pack", "nothing")
