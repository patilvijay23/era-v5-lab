"""Tests for ledger.py: the runner takes the synthetic chain through F2 (fake_run_f2.py), then the ledger is built from
what each stage wrote, and changed inputs must stop it.

  python -m pytest teams/01-data-a/pipeline/tests -q
"""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from conftest import HEADER, PIPELINE
import ledger
import run_pipeline as rp
from test_run_pipeline import GROUP_HEADER, config, tsai_outputs, write_csv  # noqa: F401  (fixtures)


@pytest.fixture
def chain(tmp_path, config, tsai_outputs):
    """The runner's outputs up to F2, and the arguments ledger.build takes."""
    rp.run(config, to="f2")
    run = tmp_path / "runs" / "test-run"
    d = tsai_outputs["dedup"]
    return {"cleaned": tsai_outputs["cleaned"], "remove_list": d / "remove_list.csv", "groups_csv": d / "dedup_groups.csv",
            "f2": run / "final", "out": tmp_path / "ledger", "log": d / "dedup_log.jsonl"}


def rows(out):
    """{(split, part, doc_id): ledger row} over every ledger file."""
    got = {}
    for f in sorted(Path(out).rglob("*.parquet")):
        for r in pq.read_table(f).to_pylist():
            got[(r["split"], r["part"], r["doc_id"])] = r
    return got


def test_mode_c_decisions_per_document(chain):
    s = ledger.build(**chain)
    assert s["clean_mode"] == "C"
    assert s["totals"] == {"rows": 13, "rows_cleaned": 13, "kept": 9, "dropped_by_clean": 0, "removed_by_dedup": 2,
                           "dropped_by_f2": 2, "f2_error": 0, "clean_fix_by_text": None}
    assert s["by_pack"]["code-go"]["heldout"] == {"rows": 2, "rows_cleaned": 2, "kept": 1, "dropped_by_clean": 0,
                                                  "removed_by_dedup": 0, "dropped_by_f2": 1, "f2_error": 0}
    r = rows(chain["out"])
    assert len(r) == 13
    copy = r[("train", "code-go/part-00001.parquet", "g0")]  # removed by dedup: the copy of g0 in part 1
    assert (copy["final"], copy["dedup_role"], copy["dedup_group"], copy["dedup_list"]) == (
        "removed_by_dedup", "removed", "G000001", "dedup")
    assert (copy["dedup_match_rule"], copy["dedup_similarity"], copy["dedup_kept_doc"], copy["dedup_stage"]) == (
        "H1", 1.0, "g0", "within_pack")
    assert copy["f2_action"] is None and copy["final_part"] is None and copy["final_row"] is None
    surv = r[("train", "code-go/part-00000.parquet", "g0")]  # its survivor, then dropped by F2
    assert (surv["final"], surv["dedup_role"], surv["f2_action"], surv["f2_items"], surv["f2_offset"]) == (
        "dropped_by_f2", "survivor", "dropped", "fake:1", 0)
    g1 = r[("train", "code-go/part-00000.parquet", "g1")]
    assert (g1["final"], g1["dedup_role"], g1["f2_action"], g1["final_part"], g1["final_row"], g1["row_in_part"]) == (
        "kept", "none", "kept", "code-go/part-00000.parquet", 0, 1)
    assert r[("train", "en-dclm/part-00000.parquet", "e2")]["dedup_stage"] == "cross_pack"
    assert {x["clean_action"] for x in r.values()} == {"unknown"} and all(x["raw_row"] is None for x in r.values())


def test_final_rows_point_into_the_final_parts(chain):
    ledger.build(**chain)
    for (split, part, doc_id), r in rows(chain["out"]).items():
        if r["final"] == "kept":
            ids = pq.read_table(chain["f2"] / split / r["final_part"]).column("doc_id").to_pylist()
            assert ids[r["final_row"]] == doc_id


def test_sample_and_summary_hold_no_text(chain):
    s = ledger.build(**chain)
    sample = (chain["out"] / "ledger_sample.csv").read_text(encoding="utf-8")
    summary = (chain["out"] / "ledger_summary.json").read_text(encoding="utf-8")
    assert "synthetic text" not in sample + summary
    with (chain["out"] / "ledger_sample.csv").open(encoding="utf-8", newline="") as f:
        got = list(csv.DictReader(f))
    assert {r["final"] for r in got} == {"kept", "removed_by_dedup", "dropped_by_f2"}
    assert [f["file"] for f in s["files"]] == ["heldout/code-go.parquet", "train/code-go.parquet", "train/en-dclm.parquet"]


def test_same_inputs_same_bytes(chain, tmp_path):
    ledger.build(**chain)
    ledger.build(**{**chain, "out": tmp_path / "ledger2"})
    for f in sorted(chain["out"].rglob("*")):
        if f.is_file():
            assert f.read_bytes() == (tmp_path / "ledger2" / f.relative_to(chain["out"])).read_bytes(), f.name


def test_without_the_log_the_match_columns_are_empty(chain):
    ledger.build(**{**chain, "log": None})
    copy = rows(chain["out"])[("train", "code-go/part-00001.parquet", "g0")]
    assert copy["final"] == "removed_by_dedup" and copy["dedup_match_rule"] is None and copy["dedup_group"] == "G000001"


def make_raw(cleaned, raw, layout="split"):
    """Raw parts: each cleaned part plus one doc the cleaner 'dropped' (at row 1); e0's text 'fixed' by the cleaner."""
    for f in cleaned.rglob("*.parquet"):
        rel = f.relative_to(cleaned)
        split, pack, name = rel.parts
        t = pq.read_table(f).to_pylist()
        t.insert(1, dict(t[0], doc_id="x-" + t[0]["doc_id"]))
        for r in t:
            if r["doc_id"] == "e0":
                r["text"] = "synthetic text of e0, before the fix"
        dst = raw / rel if layout == "split" else raw / pack / split / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(t), dst)
    return raw


@pytest.mark.parametrize("layout", ["split", "pack"])
def test_mode_b_keep_fix_drop(chain, tmp_path, layout):
    raw = make_raw(chain["cleaned"], tmp_path / "raw", layout)
    s = ledger.build(**chain, raw=raw)
    assert s["clean_mode"] == "B"
    assert (s["totals"]["rows"], s["totals"]["dropped_by_clean"], s["totals"]["kept"], s["totals"]["clean_fix_by_text"]) == (
        17, 4, 9, 1)
    r = rows(chain["out"])
    drop = r[("train", "code-go/part-00000.parquet", "x-g0")]
    assert (drop["final"], drop["clean_action"], drop["raw_row"], drop["row_in_part"], drop["dedup_role"]) == (
        "dropped_by_clean", "drop", 1, None, None)
    g1 = r[("train", "code-go/part-00000.parquet", "g1")]
    assert (g1["clean_action"], g1["raw_row"], g1["row_in_part"], g1["final_row"]) == ("keep", 2, 1, 0)
    assert r[("train", "en-dclm/part-00000.parquet", "e0")]["clean_action"] == "fix"


def test_mode_b_checks_the_cleaning_reports(chain, tmp_path):
    raw = make_raw(chain["cleaned"], tmp_path / "raw")
    rep = chain["cleaned"] / "reports" / "train" / "en-dclm" / "part-00000.parquet.json"
    rep.parent.mkdir(parents=True)
    rep.write_text(json.dumps({"input_rows": 4, "output_rows": 3, "actions": {"keep": 2, "fix": 1, "drop": 1}}), encoding="utf-8")
    s = ledger.build(**chain, raw=raw)
    assert s["clean_reports"] == {"parts": 1, "input_rows": 4, "drop": 1, "fix": 1, "keep": 2}
    rep.write_text(json.dumps({"input_rows": 4, "output_rows": 2, "actions": {"keep": 2, "drop": 2}}), encoding="utf-8")
    with pytest.raises(ledger.Stop, match="cleaning report"):
        ledger.build(**{**chain, "out": tmp_path / "l2"}, raw=raw)


def test_mode_b_raw_from_another_run_stops(chain, tmp_path):
    raw = make_raw(chain["cleaned"], tmp_path / "raw")
    f = raw / "train" / "en-dclm" / "part-00000.parquet"
    t = pq.read_table(f).to_pylist()
    pq.write_table(pa.Table.from_pylist([r for r in t if r["doc_id"] != "e1"]), f)
    with pytest.raises(ledger.Stop, match="not in the raw part"):
        ledger.build(**chain, raw=raw)


def test_mode_b_missing_raw_part_stops(chain, tmp_path):
    raw = make_raw(chain["cleaned"], tmp_path / "raw")
    (raw / "heldout" / "code-go" / "part-00000.parquet").unlink()
    with pytest.raises(ledger.Stop, match="no raw part for heldout/code-go"):
        ledger.build(**chain, raw=raw)


def test_remove_list_with_another_doc_id_stops(chain, tmp_path):
    bad = tmp_path / "bad_remove.csv"
    write_csv(bad, HEADER, [["code-go", "train", "code-go/part-00001.parquet", 0, "g5"],
                            ["en-dclm", "train", "en-dclm/part-00000.parquet", 2, "e2"]])
    with pytest.raises(ledger.Stop, match="another doc_id"):
        ledger.build(**{**chain, "remove_list": bad})


def test_row_past_the_end_stops(chain, tmp_path):
    bad = tmp_path / "bad_remove.csv"
    write_csv(bad, HEADER, [["code-go", "train", "code-go/part-00001.parquet", 9, "g0"],
                            ["en-dclm", "train", "en-dclm/part-00000.parquet", 2, "e2"]])
    with pytest.raises(ledger.Stop, match="not rows of this cleaned part"):
        ledger.build(**{**chain, "remove_list": bad})


def test_groups_disagreeing_with_the_remove_list_stop(chain, tmp_path):
    rows_ = list(csv.reader(chain["groups_csv"].open(encoding="utf-8")))[1:]
    rows_[4][3] = "survivor"  # e2 removed in the list, a survivor in the groups
    bad = tmp_path / "bad_groups.csv"
    write_csv(bad, GROUP_HEADER, rows_)
    with pytest.raises(ledger.Stop, match="not the other"):
        ledger.build(**{**chain, "groups_csv": bad})


def test_unknown_part_stops(chain, tmp_path):
    bad = tmp_path / "bad_remove.csv"
    write_csv(bad, HEADER, [["code-go", "train", "code-go/part-00009.parquet", 0, "g0"]])
    with pytest.raises(ledger.Stop, match="not among the cleaned parts"):
        ledger.build(**{**chain, "remove_list": bad})


def test_final_part_out_of_order_stops(chain):
    f = chain["f2"] / "train" / "code-go" / "part-00000.parquet"
    t = pq.read_table(f)
    pq.write_table(t.take(list(reversed(range(t.num_rows)))), f)
    with pytest.raises(ledger.Stop, match="does not hold the ledger's"):
        ledger.build(**chain)


def test_missing_f2_report_stops(chain):
    (chain["f2"] / "train" / "en-dclm" / "part-00000.parquet.f2.json").unlink()
    with pytest.raises(ledger.Stop, match="no F2 report"):
        ledger.build(**chain)


def test_f2_report_naming_a_removed_doc_stops(chain):
    rep = chain["f2"] / "train" / "en-dclm" / "part-00000.parquet.f2.json"
    r = json.loads(rep.read_text(encoding="utf-8"))
    r["dropped"].append({"doc_id": "e2", "items": ["fake:1"], "offset": 0})  # e2 was removed by dedup: F2 never saw it
    rep.write_text(json.dumps(r), encoding="utf-8")
    with pytest.raises(ledger.Stop, match="not among the rows apply kept"):
        ledger.build(**chain)


def test_f2_errors_are_their_own_status(chain):
    rep = chain["f2"] / "train" / "en-dclm" / "part-00000.parquet.f2.json"
    r = json.loads(rep.read_text(encoding="utf-8"))
    r["errors"] = [["e1", "ValueError"]]
    rep.write_text(json.dumps(r), encoding="utf-8")
    f = chain["f2"] / "train" / "en-dclm" / "part-00000.parquet"
    t = pq.read_table(f)
    pq.write_table(t.filter(pa.array([d != "e1" for d in t.column("doc_id").to_pylist()])), f)
    s = ledger.build(**chain)
    e1 = rows(chain["out"])[("train", "en-dclm/part-00000.parquet", "e1")]
    assert (e1["final"], e1["f2_action"], e1["f2_items"]) == ("f2_error", "error", "error:ValueError")
    assert (s["totals"]["f2_error"], s["totals"]["kept"]) == (1, 8)


def test_stale_ledger_file_stops(chain):
    stale = chain["out"] / "train" / "old-pack.parquet"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"left by an earlier run")
    with pytest.raises(ledger.Stop, match="not write"):
        ledger.build(**chain)
    assert not list(chain["out"].rglob("*.tmp"))


def test_cli(chain):
    args = [sys.executable, "-I", str(PIPELINE / "ledger.py"), "--cleaned", chain["cleaned"], "--remove-list",
            chain["remove_list"], "--groups", chain["groups_csv"], "--log", chain["log"], "--f2", chain["f2"],
            "--out", chain["out"]]
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout.strip().splitlines()[-1]) == {"clean_mode": "C", "rows": 13, "rows_cleaned": 13, "kept": 9,
                                                             "dropped_by_clean": 0, "removed_by_dedup": 2,
                                                             "dropped_by_f2": 2, "f2_error": 0}


def test_log_naming_a_survivor_stops(chain, tmp_path):
    entries = [json.loads(line) for line in chain["log"].read_text(encoding="utf-8").splitlines()]
    entries[1].update(removed_part="code-go/part-00000.parquet", removed_row_in_part=0, removed_id="g0")  # a survivor
    bad = tmp_path / "bad_log.jsonl"
    bad.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    with pytest.raises(ledger.Stop, match="dedup_log.jsonl but not the other"):
        ledger.build(**{**chain, "log": bad})


def test_row_in_two_groups_stops(chain, tmp_path):
    rows_ = list(csv.reader(chain["groups_csv"].open(encoding="utf-8")))[1:]
    rows_.append(["G000003", 2, 4, "survivor", "en-dclm", "train", "en-dclm/part-00000.parquet", 2, "e2"])
    bad = tmp_path / "bad_groups.csv"
    write_csv(bad, GROUP_HEADER, rows_)
    with pytest.raises(ledger.Stop, match="more than once"):
        ledger.build(**{**chain, "groups_csv": bad})


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def test_mode_b_finds_the_raw_part_by_sha256_under_any_name(chain, tmp_path):
    raw = make_raw(chain["cleaned"], tmp_path / "raw")
    src = raw / "train" / "en-dclm" / "part-00000.parquet"
    renamed = src.with_name("part-00000 (7).parquet")
    src.rename(renamed)
    rep = chain["cleaned"] / "reports" / "train" / "en-dclm" / "part-00000.parquet.json"
    rep.parent.mkdir(parents=True)
    rep.write_text(json.dumps({"input_sha256": sha(renamed), "input_rows": 4, "actions": {"keep": 2, "fix": 1, "drop": 1}}),
                   encoding="utf-8")
    s = ledger.build(**chain, raw=raw)
    files = {f["part"]: f for f in s["inputs"]["raw"]["files"]}
    assert files["train/en-dclm/part-00000.parquet"] == {"part": "train/en-dclm/part-00000.parquet",
                                                         "file": "train/en-dclm/part-00000 (7).parquet", "sha256": sha(renamed)}
    assert len(files) == 4


def test_mode_b_same_name_but_another_raw_file_stops(chain, tmp_path):
    raw = make_raw(chain["cleaned"], tmp_path / "raw")
    rep = chain["cleaned"] / "reports" / "train" / "en-dclm" / "part-00000.parquet.json"
    rep.parent.mkdir(parents=True)
    rep.write_text(json.dumps({"input_sha256": "0" * 64, "input_rows": 4, "actions": {"keep": 2, "fix": 1, "drop": 1}}),
                   encoding="utf-8")
    with pytest.raises(ledger.Stop, match="no raw part has the sha256"):
        ledger.build(**chain, raw=raw)


def test_a_stopped_rebuild_leaves_no_summary(chain):
    ledger.build(**chain)
    f = chain["f2"] / "train" / "en-dclm" / "part-00000.parquet"
    t = pq.read_table(f)
    pq.write_table(t.take(list(reversed(range(t.num_rows)))), f)
    with pytest.raises(ledger.Stop):
        ledger.build(**chain)
    assert not (chain["out"] / "ledger_summary.json").exists() and not list(chain["out"].rglob("*.tmp"))
