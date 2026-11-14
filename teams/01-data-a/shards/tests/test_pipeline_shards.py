"""run_pipeline.py through its shard stage with the real run_shards.py and shard_writer.py (G6's baseline tokenizer with
any_tokenizer, as in test_shard_writer.py), on a synthetic run. The runner's own tests (pipeline/tests) use a stand-in.

  python -m pytest teams/01-data-a/shards/tests/test_pipeline_shards.py
"""
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("pyarrow")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from synthetic_run import make_run, sha  # noqa: E402
import run_shards  # noqa: E402,F401  (puts G6's folder on the path)
from dataio.tokenizer import BrahmicTokenizer  # noqa: E402

BASE = BrahmicTokenizer().path
TEXTS = ["The water cycle moves water between the sea, the air and the land.\n",
         "package main\n\nfunc area(r float64) float64 {\n\treturn 3.14159 * r * r\n}\n"]


def rows(pack, tag):
    return [{"doc_id": f"{tag}{k}", "text": t, "url": "", "lang_label": "en", "pack_id": pack} for k, t in enumerate(TEXTS)]


def test_the_pipeline_runs_through_the_shard_stage(tmp_path, monkeypatch):
    table = tmp_path / "pack_table.json"
    table.write_text(json.dumps({"packs": {"pk-a": {"language": "en", "script": "Latn", "domain": "web", "lane": "test"}}}), encoding="utf-8")
    parts = {("train", "pk-a/part-00000.parquet"): rows("pk-a", "a_"), ("heldout", "pk-a/part-00000.parquet"): rows("pk-a", "h_")}
    run = make_run(tmp_path / "pipeline", monkeypatch, parts,
                   shards={"tokenizer": str(BASE), "any_tokenizer": True, "pack_table": str(table)})
    manifest = json.loads((run / "pipeline_manifest.json").read_text(encoding="utf-8"))
    stage = manifest["stages"][-1]
    assert stage["stage"] == "shards" and manifest["totals"]["shards_written"] == 1 and all(c["ok"] for c in manifest["checks"])
    assert stage["counts"]["written"] == 1 and stage["counts"]["not_sharded"] == 1 and stage["counts"]["failed"] == 0
    out = run / "shards"
    shard = json.loads((out / "pk-a-train-000000.json").read_text(encoding="utf-8"))
    assert shard["doc_count"] == 2 and shard["cleaning_pipeline_sha256"] == sha(run / "cleaning_pipeline.json") == stage["cleaning_pipeline_sha256"]
    assert (out / "cleaning_pipeline.json").read_bytes() == (run / "cleaning_pipeline.json").read_bytes()
    summary = json.loads((out / "shards_summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == "test-run" and summary["cleaning_pipeline_sha256"] == shard["cleaning_pipeline_sha256"]
    assert not list(out.glob("*heldout*")) and (run / "logs" / "shards.log").is_file()
