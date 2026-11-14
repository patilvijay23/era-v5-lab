"""Tests for run_pipeline.py: the whole chain on synthetic data, with clean, overlap and dedup adopted (as when TSAI ran
them) and apply, F2 (a stand-in, fake_run_f2.py), survivor_loss and the ledger run by the runner.

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
    log = [{"removed_pack_id": "code-go", "removed_split": "train", "removed_part": "code-go/part-00001.parquet",
            "removed_row_in_part": 0, "removed_id": "g0", "kept_pack_id": "code-go", "kept_split": "train",
            "kept_part": "code-go/part-00000.parquet", "kept_row_in_part": 0, "kept_id": "g0", "rule": "H1",
            "similarity": 1.0, "priority_rule": 4, "stage": "within_pack", "direct": True},
           {"removed_pack_id": "en-dclm", "removed_split": "train", "removed_part": "en-dclm/part-00000.parquet",
            "removed_row_in_part": 2, "removed_id": "e2", "kept_pack_id": "code-go", "kept_split": "heldout",
            "kept_part": "code-go/part-00000.parquet", "kept_row_in_part": 0, "kept_id": "h0", "rule": "H2",
            "similarity": 0.91, "priority_rule": 0, "stage": "cross_pack", "direct": True}]
    (folder / "dedup_log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in log), encoding="utf-8")
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
    assert [s["stage"] for s in m["stages"]] == list(rp.STAGES)
    c = {s["stage"]: s["counts"] for s in m["stages"]}
    assert c["clean"]["rows"] == 13 and c["overlap"]["documents_all"] == 13 and c["dedup"]["remove_list_rows"] == 2
    assert (c["apply"]["rows"], c["apply"]["removed"], c["apply"]["kept"]) == (13, 2, 11)
    assert (c["f2"]["rows"], c["f2"]["dropped_by_f2"], c["f2"]["kept"]) == (11, 2, 9)
    assert c["f2"]["by_split"]["heldout"] == {"rows": 2, "kept": 1, "dropped_by_f2": 1, "errors": 0}
    assert c["survivor_loss"]["lost"] == 1 and c["survivor_loss"]["partly_hit"] == 1
    assert m["totals"] == {"cleaned": 13, "removed_by_dedup": 2, "dropped_by_f2": 2, "final": 9}
    assert c["ledger"] == {"rows": 13, "rows_cleaned": 13, "kept": 9, "dropped_by_clean": 0, "removed_by_dedup": 2,
                           "dropped_by_f2": 2, "f2_error": 0}
    assert sorted(p.relative_to(run / "ledger").as_posix() for p in (run / "ledger").rglob("*.parquet")) == [
        "heldout/code-go.parquet", "train/code-go.parquet", "train/en-dclm.parquet"]
    names = {ch["check"] for ch in m["checks"]}
    assert {"overlap read these cleaned parts", "dedup used this overlap run", "F2 read what apply wrote in train",
            "survivor loss saw every dedup group", "ledger kept = F2's kept"} <= names and all(ch["ok"] for ch in m["checks"])
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
    assert [s["stage"] for s in m["stages"]] == list(rp.STAGES) and m["totals"]["final"] == 9
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
    c = {s["stage"]: s["counts"] for s in par["stages"]}
    assert (c["survivor_loss"]["lost"], c["survivor_loss"]["partly_hit"]) == (1, 1)
    assert c["ledger"] == {s["stage"]: s["counts"] for s in one["stages"]}["ledger"]


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


def test_ledger_mode_b_adds_the_cleaners_drops(tmp_path, config, cleaned):
    raw = tmp_path / "raw"
    for f in cleaned.rglob("*.parquet"):
        t = pq.read_table(f)
        dst = raw / f.relative_to(cleaned)
        dst.parent.mkdir(parents=True, exist_ok=True)
        extra = t.slice(0, 1).to_pylist()
        extra[0]["doc_id"] = "x-" + extra[0]["doc_id"]
        pq.write_table(pa_concat(t, extra), dst)
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["stages"]["ledger"] = {"raw": str(raw)}
    config.write_text(json.dumps(cfg), encoding="utf-8")
    m = rp.run(config)
    assert m["totals"] == {"raw": 17, "dropped_by_clean": 4, "cleaned": 13, "removed_by_dedup": 2, "dropped_by_f2": 2,
                           "final": 9}
    rec = next(s for s in m["stages"] if s["stage"] == "ledger")
    assert rec["clean_mode"] == "B" and rec["counts"]["clean_fix_by_text"] == 0


def pa_concat(t, rows):
    import pyarrow as pa
    return pa.concat_tables([t, pa.Table.from_pylist(rows, schema=t.schema)])


def test_ledger_raw_must_be_a_folder(tmp_path, config):
    cfg = json.loads(config.read_text(encoding="utf-8"))
    cfg["stages"]["ledger"] = {"raw": str(tmp_path / "no-such-raw")}
    config.write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(rp.Stop, match="stages.ledger.raw"):
        rp.run(config)
    assert not (tmp_path / "runs").exists()


def test_from_ledger_reuses_earlier_stages(config):
    first = rp.run(config)
    again = rp.run(config, start="ledger")
    assert again["totals"] == first["totals"]
    assert [s["digest"] for s in again["stages"]] == [s["digest"] for s in first["stages"]]
