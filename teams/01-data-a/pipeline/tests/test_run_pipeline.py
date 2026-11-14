"""Tests for run_pipeline.py: the whole chain on synthetic data, with clean, overlap and dedup adopted (as when TSAI ran
them) and apply, F2 (a stand-in, fake_run_f2.py) and survivor_loss run by the runner.

  python -m pytest teams/01-data-a/pipeline/tests -q
"""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import pyarrow.parquet as pq

from conftest import HEADER, PARTS, PIPELINE
import run_pipeline as rp

FAKE_F2 = Path(__file__).resolve().parent / "fake_run_f2.py"
FAKE_SHARDS = Path(__file__).resolve().parent / "fake_run_shards.py"
GROUP_HEADER = ["group_id", "group_size", "priority_rule", "role", "pack_id", "split", "part", "row_in_part", "doc_id"]


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def overlap_folder(folder, cleaned_parts=PARTS, docs_all=13):
    """What overlap.py returns, shaped like its real summary (status, documents_all, inputs.parts, outputs)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "overlap_matches.csv").write_text("row_a,row_b\n0,1\n", encoding="utf-8")
    (folder / "overlap_docs.parquet").write_bytes(b"stand-in for overlap_docs.parquet")
    summary = {"status": "complete", "documents_all": docs_all,
               "inputs": {"parts": [{"part": f"{s}/{p}", "documents": len(rows)} for (s, p), rows in cleaned_parts.items()]},
               "outputs": {n: {"sha256": sha(folder / n)} for n in ("overlap_matches.csv", "overlap_docs.parquet")}}
    (folder / "overlap_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return folder


def dedup_folder(folder, overlap, removed=2, heldout_removed=0):
    """What dedup.py returns: G-numbered groups, integer rules, and the overlap files it checked."""
    write_csv(folder / "remove_list.csv", HEADER, [["code-go", "train", "code-go/part-00001.parquet", 0, "g0"],
                                                   ["en-dclm", "train", "en-dclm/part-00000.parquet", 2, "e2"]])
    write_csv(folder / "dedup_groups.csv", GROUP_HEADER, [
        ["G000001", 2, 4, "survivor", "code-go", "train", "code-go/part-00000.parquet", 0, "g0"],
        ["G000001", 2, 4, "removed", "code-go", "train", "code-go/part-00001.parquet", 0, "g0"],
        ["G000002", 3, 0, "survivor", "code-go", "heldout", "code-go/part-00000.parquet", 0, "h0"],
        ["G000002", 3, 0, "survivor", "code-go", "heldout", "code-go/part-00000.parquet", 1, "h1"],
        ["G000002", 3, 0, "removed", "en-dclm", "train", "en-dclm/part-00000.parquet", 2, "e2"]])
    checked = {n: sha(overlap / n) for n in ("overlap_matches.csv", "overlap_docs.parquet")}
    (folder / "dedup_summary.json").write_text(json.dumps({
        "status": "complete", "overlap_run": {"documents_all": 13, "checked_sha256": checked}, "documents_all": 13,
        "removed": removed, "heldout_removed": heldout_removed}), encoding="utf-8")
    return folder


@pytest.fixture
def tsai_outputs(tmp_path, cleaned):
    overlap = overlap_folder(tmp_path / "overlap")
    return {"cleaned": cleaned, "overlap": overlap, "dedup": dedup_folder(tmp_path / "dedup", overlap)}


def write_config(path, outs, run_id="test-run", **extra):
    cfg = {"run_id": run_id, "out": str(path.parent / "runs"),
           "stages": {"clean": {"mode": "adopt", "output": str(outs["cleaned"])},
                      "overlap": {"mode": "adopt", "output": str(outs["overlap"])},
                      "dedup": {"mode": "adopt", "output": str(outs["dedup"])},
                      "f2": {"script": str(FAKE_F2)}}}
    cfg["stages"].update(extra)
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


@pytest.fixture
def config(tmp_path, tsai_outputs, monkeypatch):
    for k in ("FAKE_F2_ERROR", "FAKE_F2_BAD_SHA", "FAKE_F2_CRASH"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("FAKE_F2_DROP", "g0,h1")
    return write_config(tmp_path / "pipeline.json", tsai_outputs)


def final_ids(run):
    return sorted(d for f in (run / "final").rglob("*.parquet") for d in pq.read_table(f).column("doc_id").to_pylist())


def test_full_chain(tmp_path, config):
    m = rp.run(config)
    run = tmp_path / "runs" / "test-run"
    assert [s["stage"] for s in m["stages"]] == [s for s in rp.STAGES if s not in rp.OPTIONAL]
    c = {s["stage"]: s["counts"] for s in m["stages"]}
    assert c["clean"]["rows"] == 13 and c["overlap"]["documents_all"] == 13 and c["dedup"]["remove_list_rows"] == 2
    assert (c["apply"]["rows"], c["apply"]["removed"], c["apply"]["kept"]) == (13, 2, 11)
    assert (c["f2"]["rows"], c["f2"]["dropped_by_f2"], c["f2"]["kept"]) == (11, 2, 9)
    assert c["f2"]["by_split"]["heldout"] == {"rows": 2, "kept": 1, "dropped_by_f2": 1, "errors": 0}
    assert c["survivor_loss"]["lost"] == 1 and c["survivor_loss"]["partly_hit"] == 1
    assert m["totals"] == {"cleaned": 13, "removed_by_dedup": 2, "dropped_by_f2": 2, "final": 9}
    names = {ch["check"] for ch in m["checks"]}
    assert {"overlap read these cleaned parts", "dedup used this overlap run", "F2 read what apply wrote in train",
            "survivor loss saw every dedup group"} <= names and all(ch["ok"] for ch in m["checks"])
    assert final_ids(run) == sorted(["g1", "g2", "g3", "g4", "g5", "g6", "e0", "e1", "h0"])
    assert (run / "logs" / "f2_train.log").is_file()
    on_disk = json.loads((run / "pipeline_manifest.json").read_text(encoding="utf-8"))
    assert on_disk["totals"] == m["totals"] and "synthetic text" not in json.dumps(on_disk)


def test_digests_repeat_across_identical_runs(tmp_path, config, tsai_outputs):
    a = rp.run(config)
    b = rp.run(write_config(tmp_path / "again.json", tsai_outputs, run_id="test-run-2"))
    assert [s["digest"] for s in a["stages"]] == [s["digest"] for s in b["stages"]]


def test_from_keeps_earlier_checks(config):
    full = len(rp.run(config, to="apply")["checks"])
    m = rp.run(config, start="f2")
    assert [s["stage"] for s in m["stages"]] == [s for s in rp.STAGES if s not in rp.OPTIONAL] and m["totals"]["final"] == 9
    assert len(m["checks"]) > full and {ch["stage"] for ch in m["checks"]} >= {"overlap", "dedup", "apply", "f2"}


def test_adopted_output_changed_after_recording_stops(config, tsai_outputs):
    rp.run(config, to="apply")
    with (tsai_outputs["dedup"] / "remove_list.csv").open("a", encoding="utf-8") as f:
        f.write("en-dclm,train,en-dclm/part-00000.parquet,1,e1\n")
    with pytest.raises(rp.Stop, match="changed"):
        rp.run(config, start="f2")


def test_from_a_stage_whose_input_was_never_run_stops(config):
    with pytest.raises(rp.Stop, match="no record .* run it first"):
        rp.run(config, start="f2")


def test_dedup_from_another_overlap_run_stops(tmp_path, config, tsai_outputs):
    other = overlap_folder(tmp_path / "other_overlap")
    (other / "overlap_matches.csv").write_text("row_a,row_b\n0,2\n", encoding="utf-8")
    dedup_folder(tsai_outputs["dedup"], other)
    with pytest.raises(rp.Stop, match="dedup used this overlap run"):
        rp.run(config)


def test_overlap_of_other_parts_stops(tmp_path, config, tsai_outputs):
    parts = dict(PARTS)
    parts[("train", "en-dclm/part-00009.parquet")] = parts.pop(("train", "en-dclm/part-00000.parquet"))
    overlap_folder(tsai_outputs["overlap"], parts)
    dedup_folder(tsai_outputs["dedup"], tsai_outputs["overlap"])
    with pytest.raises(rp.Stop, match="overlap read these cleaned parts"):
        rp.run(config)


def test_count_mismatch_stops(tmp_path, config, tsai_outputs):
    overlap_folder(tsai_outputs["overlap"], docs_all=12)
    with pytest.raises(rp.Stop, match="overlap read every cleaned row"):
        rp.run(config)


def test_dedup_removing_heldout_stops(config, tsai_outputs):
    dedup_folder(tsai_outputs["dedup"], tsai_outputs["overlap"], heldout_removed=1)
    with pytest.raises(rp.Stop, match="held-out"):
        rp.run(config)


def test_f2_errors_stop(config, monkeypatch):
    monkeypatch.setenv("FAKE_F2_ERROR", "g3")
    with pytest.raises(rp.Stop, match="F2 reported no errors on train"):
        rp.run(config)


def test_f2_that_read_something_else_stops(config, monkeypatch):
    monkeypatch.setenv("FAKE_F2_BAD_SHA", "1")
    with pytest.raises(rp.Stop, match="F2 read what apply wrote"):
        rp.run(config)


def test_stale_final_output_stops(tmp_path, config):
    stale = tmp_path / "runs" / "test-run" / "final" / "train" / "old-pack" / "part-00000.parquet"
    stale.parent.mkdir(parents=True)
    shutil.copyfile(next((tmp_path / "cleaned" / "train").rglob("*.parquet")), stale)
    with pytest.raises(rp.Stop, match="stale F2 output"):
        rp.run(config)


def test_train_only_run(tmp_path, cleaned, monkeypatch):
    shutil.rmtree(cleaned / "heldout")
    train = {k: v for k, v in PARTS.items() if k[0] == "train"}
    overlap = overlap_folder(tmp_path / "overlap1", train, docs_all=11)
    dedup = dedup_folder(tmp_path / "dedup1", overlap)
    rows = list(csv.reader((dedup / "dedup_groups.csv").open(encoding="utf-8")))
    write_csv(dedup / "dedup_groups.csv", rows[0], [r for r in rows[1:] if r[5] == "train"])
    s = json.loads((dedup / "dedup_summary.json").read_text(encoding="utf-8"))
    s.update(documents_all=11)
    (dedup / "dedup_summary.json").write_text(json.dumps(s), encoding="utf-8")
    monkeypatch.setenv("FAKE_F2_DROP", "g0")
    cfg = write_config(tmp_path / "p1.json", {"cleaned": cleaned, "overlap": overlap, "dedup": dedup}, run_id="train-only")
    m = rp.run(cfg)
    assert m["totals"] == {"cleaned": 11, "removed_by_dedup": 2, "dropped_by_f2": 1, "final": 8}


def test_run_mode_calls_the_script(tmp_path, config, tsai_outputs):
    maker = tmp_path / "make_overlap.py"
    src = tsai_outputs["overlap"]
    maker.write_text(f"import shutil, sys\nshutil.copytree({str(src)!r}, sys.argv[1], dirs_exist_ok=True)\n", encoding="utf-8")
    out = tmp_path / "overlap_run"
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["stages"]["overlap"] = {"mode": "run", "output": str(out), "command": [str(maker), str(out)]}
    config.write_text(json.dumps(cfg), encoding="utf-8")
    m = rp.run(config)
    rec = next(s for s in m["stages"] if s["stage"] == "overlap")
    assert rec["mode"] == "run" and rec["code_sha256"] == sha(maker)
    assert (tmp_path / "runs" / "test-run" / "logs" / "overlap.log").is_file()


def test_run_mode_failure_stops(tmp_path, config):
    bad = tmp_path / "bad_overlap.py"
    bad.write_text("import sys; print('boom'); sys.exit(3)\n", encoding="utf-8")
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["stages"]["overlap"] = {"mode": "run", "output": cfg["stages"]["overlap"]["output"], "command": [str(bad)]}
    config.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(rp.Stop, match="exit code 3.*boom"):
        rp.run(config)


def test_bad_config_stops_before_anything_runs(tmp_path, config):
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["stages"]["f2"] = {"script": str(tmp_path / "missing_run_f2.py")}
    config.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(rp.Stop, match="f2 script .* not found"):
        rp.run(config)
    assert not (tmp_path / "runs").exists()


def set_f2(config, **kw):
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["stages"]["f2"].update(kw)
    config.write_text(json.dumps(cfg), encoding="utf-8")


def test_parallel_f2_matches_one_process(tmp_path, config, tsai_outputs):
    one = rp.run(config)
    par_cfg = write_config(tmp_path / "par.json", tsai_outputs, run_id="parallel")
    set_f2(par_cfg, workers=3)
    par = rp.run(par_cfg)
    run = tmp_path / "runs" / "parallel"
    f2 = next(s for s in par["stages"] if s["stage"] == "f2")
    assert (f2["workers"], f2["units"]) == (3, 3)  # train/code-go, train/en-dclm, heldout/code-go
    assert par["totals"] == one["totals"] and final_ids(run) == final_ids(tmp_path / "runs" / "test-run")
    assert {p.name for p in (run / "logs").glob("f2_*.log")} == {"f2_train_code-go.log", "f2_train_en-dclm.log",
                                                                  "f2_heldout_code-go.log"}
    loss = {s["stage"]: s["counts"] for s in par["stages"]}["survivor_loss"]
    assert (loss["lost"], loss["partly_hit"]) == (1, 1)


def test_parallel_f2_crash_names_the_pack_and_rerun_recovers(config, monkeypatch):
    set_f2(config, workers=2)
    monkeypatch.setenv("FAKE_F2_CRASH", "en-dclm")
    with pytest.raises(rp.Stop, match=r"1 of 3 unit\(s\) failed.*train/en-dclm"):
        rp.run(config)
    monkeypatch.delenv("FAKE_F2_CRASH")
    assert rp.run(config, start="f2")["totals"]["final"] == 9


@pytest.mark.parametrize("workers", [0, "4", 1.5, True])
def test_bad_workers_stop(config, workers):
    set_f2(config, workers=workers)
    with pytest.raises(rp.Stop, match="workers"):
        rp.run(config)


def test_cli(tmp_path, config):
    env = {**os.environ, "FAKE_F2_DROP": "g0,h1"}
    p = subprocess.run([sys.executable, "-I", str(PIPELINE / "run_pipeline.py"), "--config", str(config)],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout.strip().splitlines()[-1])["final"] == 9


# --- the shard stage (stand-in run_shards.py; the real one is tested in shards/tests) -----------------------------------
@pytest.fixture
def shard_config(tmp_path, tsai_outputs, config, monkeypatch):
    """A config with stages.shards, and the clean job's job_summary.json the shard stage needs. Returns the config path."""
    for k in ("FAKE_SHARDS_FAIL", "FAKE_SHARDS_NONE", "FAKE_SHARDS_BAD_RUN"):
        monkeypatch.delenv(k, raising=False)
    (tsai_outputs["cleaned"] / "job_summary.json").write_text(json.dumps({"clean_sha256": "c" * 64, "parts": []}), encoding="utf-8")
    tokenizer = tmp_path / "tokenizer.json"
    tokenizer.write_text("{}", encoding="utf-8")
    return write_config(tmp_path / "pipeline.json", tsai_outputs,
                        shards={"script": str(FAKE_SHARDS), "tokenizer": str(tokenizer), "packs": ["code-go"], "tokens": 100})


def test_shards_run_after_f2_and_are_recorded(tmp_path, shard_config):
    m = rp.run(shard_config)
    run = tmp_path / "runs" / "test-run"
    assert [s["stage"] for s in m["stages"]] == list(rp.STAGES)
    s = m["stages"][-1]
    assert s["counts"] == {"written": 2, "failed": 0, "skipped": 0, "not_sharded": 1, "truncated": 0, "parts": 3}
    assert m["totals"]["shards_written"] == 2 and all(ch["ok"] for ch in m["checks"])
    record = json.loads((run / "cleaning_pipeline.json").read_text(encoding="utf-8"))
    assert sorted(record) == ["clean_py_sha256", "dedup", "f2_set_sha256"] and record["clean_py_sha256"] == "c" * 64
    assert s["cleaning_pipeline_sha256"] == rp.sha256(run / "cleaning_pipeline.json")
    assert json.loads((run / "pipeline_manifest.json").read_text(encoding="utf-8"))["stages"][-1]["stage"] == "shards"
    assert json.loads((run / "shards" / "args.json").read_text(encoding="utf-8"))["packs"] == ["code-go"]
    assert json.loads((run / "shards" / "args.json").read_text(encoding="utf-8"))["tokens"] == 100
    assert (run / "logs" / "shards.log").is_file() and s["digest"] and s["code_sha256"]


def test_without_stages_shards_the_run_stops_after_survivor_loss(tmp_path, config):
    m = rp.run(config)
    assert [s["stage"] for s in m["stages"]][-1] == "survivor_loss" and "shards_written" not in m["totals"]
    assert not (tmp_path / "runs" / "test-run" / "cleaning_pipeline.json").exists()
    with pytest.raises(rp.Stop, match="stages.shards is not configured"):
        rp.run(config, to="shards")


def test_from_shards_adds_the_stage_to_a_finished_run(tmp_path, shard_config):
    rp.run(shard_config, to="survivor_loss")
    m = rp.run(shard_config, start="shards")
    assert [s["stage"] for s in m["stages"]] == list(rp.STAGES) and m["totals"]["final"] == 9 and m["totals"]["shards_written"] == 2


def test_a_second_shard_run_into_the_same_out_stops(shard_config):
    rp.run(shard_config)
    with pytest.raises(rp.Stop, match="run_shards.py exited 0"):  # the stand-in refuses, as the real one does
        rp.run(shard_config, start="shards")


def test_a_failed_part_stops_the_run_before_the_stage_is_recorded(tmp_path, shard_config, monkeypatch):
    monkeypatch.setenv("FAKE_SHARDS_FAIL", "1")
    with pytest.raises(rp.Stop, match="no part failed or was skipped"):
        rp.run(shard_config)
    stages = [s["stage"] for s in json.loads((tmp_path / "runs" / "test-run" / "pipeline_manifest.json").read_text(encoding="utf-8"))["stages"]]
    assert stages[-1] == "survivor_loss"


def test_a_shard_process_that_wrote_no_summary_stops_the_run(shard_config, monkeypatch):
    monkeypatch.setenv("FAKE_SHARDS_NONE", "1")
    with pytest.raises(rp.Stop, match="wrote no shards_summary.json"):
        rp.run(shard_config)


def test_a_summary_of_another_run_stops_the_run(shard_config, monkeypatch):
    monkeypatch.setenv("FAKE_SHARDS_BAD_RUN", "1")
    with pytest.raises(rp.Stop, match="the summary is this run's"):
        rp.run(shard_config)


def test_no_clean_job_summary_means_no_shard_stage(tmp_path, shard_config, tsai_outputs):
    (tsai_outputs["cleaned"] / "job_summary.json").unlink()
    with pytest.raises(rp.Stop, match="shards: .*no job_summary.json"):
        rp.run(shard_config)


@pytest.mark.parametrize("change, message", [({"tokenizer": "/no/such/tokenizer.json"}, "stages.shards.tokenizer"),
                                             ({"tokens": 0}, "stages.shards.tokens"), ({"packs": "code-go"}, "stages.shards.packs"),
                                             ({"script": "/no/such/run_shards.py"}, "shards script")])
def test_the_shards_config_is_checked_before_anything_runs(tmp_path, shard_config, change, message):
    cfg = json.loads(shard_config.read_text(encoding="utf-8"))
    cfg["stages"]["shards"].update(change)
    shard_config.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(rp.Stop, match=message):
        rp.run(shard_config)
    assert not (tmp_path / "runs").exists()

