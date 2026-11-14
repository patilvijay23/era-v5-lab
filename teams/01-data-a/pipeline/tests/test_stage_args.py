"""Tests for stage_args.py: the command and generated config the runner gives each stage script. Made-up settings files and
a made-up repository folder; nothing is run.

  python -m pytest teams/01-data-a/pipeline/tests/test_stage_args.py
"""
import json

import pytest

import stage_args as sa

OVERLAP = {"_comment": "settings only", "inputs": "old/clean", "splits": ["train", "heldout"], "out": "old/overlap", "floor": 0.5, "k": 5,
           "expected_packs": ["code-go"]}
DEDUP = {"results": "old/overlap", "inputs": "old/clean", "out": "old/dedup", "cross_pack": True, "pack_order": ["code-go", "en-dclm"],
         "licence_usable": {}, "default_licence_usable": True, "gold_dirs": []}


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "repo" / "out" / "run1").mkdir(parents=True)
    return tmp_path / "repo"


@pytest.fixture
def folders(repo):
    return {s: repo / "out" / "run1" / s for s in ("clean", "overlap", "dedup")}


def settings(repo, name, data):
    p = repo / f"{name}.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_clean_gets_flags_and_no_generated_config(repo, folders):
    s = settings(repo, "job", {"clean_sha256": "c" * 64})
    r = sa.build("clean", {"settings": "job.json", "input": "inputs/sample"}, folders, repo / "out/run1/cfg", repo)
    assert r["command"] == [sa.DEFAULT_SCRIPT["clean"], "--config", str(s), "--out", str(folders["clean"]), "--input-root", "inputs/sample"]
    assert r["config"] is None and r["settings_sha256"] == sa.sha256(s)
    assert not (repo / "out/run1/cfg").exists()


def test_clean_without_input_leaves_the_job_configs_own_input_root(repo, folders):
    settings(repo, "job", {})
    command = sa.build("clean", {"settings": "job.json"}, folders, repo / "cfg", repo)["command"]
    assert "--input-root" not in command and command[-2:] == ["--out", str(folders["clean"])]


def test_overlap_config_gets_the_paths_and_keeps_every_setting(repo, folders):
    settings(repo, "overlap", OVERLAP)
    cfg = repo / "out/run1/cfg"
    r = sa.build("overlap", {"settings": "overlap.json"}, folders, cfg, repo)
    made = json.loads((cfg / "overlap.json").read_text(encoding="utf-8"))
    assert made["inputs"] == "out/run1/clean" and made["out"] == "out/run1/overlap"
    assert {k: v for k, v in made.items() if k not in ("inputs", "out")} == {k: v for k, v in OVERLAP.items() if k not in ("inputs", "out")}
    assert r["command"] == [sa.DEFAULT_SCRIPT["overlap"], "--config", (cfg / "overlap.json").as_posix()]
    assert r["config_sha256"] == sa.sha256(cfg / "overlap.json") and r["config"] == (cfg / "overlap.json").as_posix()


def test_dedup_config_names_the_overlap_folder_as_results(repo, folders):
    settings(repo, "dedup", DEDUP)
    r = sa.build("dedup", {"settings": "dedup.json"}, folders, repo / "cfg", repo)
    made = json.loads((repo / "cfg" / "dedup.json").read_text(encoding="utf-8"))
    assert (made["results"], made["inputs"], made["out"]) == ("out/run1/overlap", "out/run1/clean", "out/run1/dedup")
    assert made["pack_order"] == DEDUP["pack_order"] and made["gold_dirs"] == [] and r["command"][1] == "--config"


def test_the_settings_file_is_not_touched_and_the_result_repeats(repo, folders):
    s = settings(repo, "dedup", DEDUP)
    before = s.read_bytes()
    a = sa.build("dedup", {"settings": "dedup.json"}, folders, repo / "cfg", repo)
    b = sa.build("dedup", {"settings": "dedup.json"}, folders, repo / "cfg", repo)
    assert s.read_bytes() == before and a == b


def test_generated_config_has_no_absolute_path(repo, folders):
    settings(repo, "overlap", OVERLAP)
    sa.build("overlap", {"settings": "overlap.json"}, folders, repo / "cfg", repo)
    text = (repo / "cfg" / "overlap.json").read_text(encoding="utf-8")
    assert str(repo) not in text and "\\" not in text and text.endswith("}\n")


def test_a_pinned_settings_file_that_changed_is_refused(repo, folders):
    s = settings(repo, "overlap", OVERLAP)
    spec = {"settings": "overlap.json", "settings_sha256": sa.sha256(s)}
    sa.build("overlap", spec, folders, repo / "cfg", repo)  # the right pin is fine
    s.write_text(json.dumps({**OVERLAP, "k": 6}), encoding="utf-8")
    with pytest.raises(sa.ConfigError, match="pins"):
        sa.build("overlap", spec, folders, repo / "cfg", repo)


def test_a_missing_or_absent_settings_file_is_refused(repo, folders):
    with pytest.raises(sa.ConfigError, match="settings .* not found"):
        sa.build("overlap", {"settings": "nope.json"}, folders, repo / "cfg", repo)
    with pytest.raises(sa.ConfigError, match="settings .* is missing"):
        sa.build("overlap", {}, folders, repo / "cfg", repo)


@pytest.mark.parametrize("stage", ["clean", "overlap", "dedup"])
def test_an_output_outside_out_is_refused(repo, folders, stage, tmp_path):
    settings(repo, "s", {})
    for bad in (repo / "elsewhere" / stage, repo / "out"):
        with pytest.raises(sa.ConfigError, match="named subfolder"):
            sa.build(stage, {"settings": "s.json"}, {**folders, stage: bad}, repo / "cfg", repo)


def test_a_folder_outside_the_repo_is_refused_for_a_generated_config(repo, folders, tmp_path):
    settings(repo, "overlap", OVERLAP)
    with pytest.raises(sa.ConfigError, match="outside the repository"):
        sa.build("overlap", {"settings": "overlap.json"}, {**folders, "clean": tmp_path / "elsewhere"}, repo / "cfg", repo)


def test_a_stage_without_this_style_asks_for_a_command(repo, folders):
    with pytest.raises(sa.ConfigError, match="explicit stages.apply.command"):
        sa.build("apply", {"settings": "x"}, folders, repo / "cfg", repo)


def test_a_script_override_is_used(repo, folders):
    settings(repo, "overlap", OVERLAP)
    command = sa.build("overlap", {"settings": "overlap.json", "script": "other/overlap.py"}, folders, repo / "cfg", repo)["command"]
    assert command[0] == "other/overlap.py"
