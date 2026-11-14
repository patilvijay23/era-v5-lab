"""How run_pipeline.py hands paths to the three stage scripts it can run (clean, overlap, dedup).

A stage's folders are decided once, in the run config, and never typed again: a stage reads the previous stage's folder and
writes its own. This module turns that into the command each script needs. Two styles, because the scripts differ:

  flags    the script takes its paths on the command line. clean (run_tokenizer_sample.py):
             --config <settings> --out <clean folder> [--input-root <raw sample>]
  config   the script only reads paths from its JSON config (overlap.py, dedup.py). The settings file is copied to
           <cfg_dir>/<stage>.json with the path keys filled in (repo-relative, as those scripts require), and the script is
           run with --config on that copy:
             overlap   inputs = <clean folder>, out = <overlap folder>
             dedup     results = <overlap folder>, inputs = <clean folder>, out = <dedup folder>

When dedup.py and overlap.py take --input/--out flags, change their entries in STAGES to style "flags" and delete
generated_config(): nothing else changes. The settings file holds settings only (k, floor, pack order, pins); its sha256 is
returned so the manifest can record it, and a "settings_sha256" in the stage's run config is checked when present.

  build("overlap", spec, folders=..., cfg_dir=..., repo=...) -> {"command", "settings", "settings_sha256", "config", "config_sha256"}
"""
import hashlib
import json
from pathlib import Path

DEFAULT_SCRIPT = {"clean": "teams/01-data-a/spec_v1/run_tokenizer_sample.py",
                  "overlap": "teams/01-data-a/dedup/overlap.py",
                  "dedup": "teams/01-data-a/dedup/dedup.py"}
STAGES = {  # style, and for "config" style: {config key: the stage whose folder it names}
    "clean": {"style": "flags"},
    "overlap": {"style": "config", "keys": {"inputs": "clean", "out": "overlap"}},
    "dedup": {"style": "config", "keys": {"results": "overlap", "inputs": "clean", "out": "dedup"}},
}


class ConfigError(Exception):
    """The run config cannot be turned into a command: the message says which stage and why."""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(folder, repo):
    """The folder as a repo-relative POSIX path, which overlap.py and dedup.py require (they reject absolute paths)."""
    try:
        return Path(folder).resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        raise ConfigError(f"{folder} is outside the repository {repo}")


def under_out(folder, repo, stage):
    """The stage scripts only write below <repo>/out (and clean needs a named subfolder of it)."""
    out = (Path(repo) / "out").resolve()
    f = Path(folder).resolve()
    if f == out or not f.is_relative_to(out):
        raise ConfigError(f"{stage}: its output {folder} must be a named subfolder of {out}: the {stage} script writes only there")


def generated_values(stage, folders, repo):
    """The path keys a generated config gets: {key: repo-relative folder}. {} for a stage that takes flags."""
    return {key: relative(folders[owner], repo) for key, owner in STAGES[stage].get("keys", {}).items()}


def generated_config(stage, settings, folders, cfg_dir, repo, write=True):
    """<cfg_dir>/<stage>.json: the settings with the path keys filled in from `folders`. Written unless write=False
    (a plan or a check of the run config). Returns its path."""
    data = {**json.loads(Path(settings).read_text(encoding="utf-8")), **generated_values(stage, folders, repo)}
    path = Path(cfg_dir) / f"{stage}.json"
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def build(stage, spec, folders, cfg_dir, repo, write=True):
    """The command for a run-mode stage from its run-config entry `spec` ("settings", optional "script", "input",
    "settings_sha256"), the stage folders {"clean", "overlap", "dedup"} (absolute) and where generated configs go.
    write=False checks everything and names the generated config without writing it (its config_sha256 is then None)."""
    if stage not in STAGES:
        raise ConfigError(f"{stage}: no script of the runner takes paths this way; give an explicit stages.{stage}.command")
    if not spec.get("settings"):
        raise ConfigError(f"stages.{stage}.settings (the settings file) is missing; or give an explicit stages.{stage}.command")
    settings = Path(spec["settings"])
    settings = settings if settings.is_absolute() else Path(repo) / settings
    if not settings.is_file():
        raise ConfigError(f"stages.{stage}.settings {spec['settings']} not found")
    settings_sha = sha256(settings)
    if spec.get("settings_sha256") and spec["settings_sha256"] != settings_sha:
        raise ConfigError(f"stages.{stage}.settings {spec['settings']} has sha256 {settings_sha[:12]}…, the run config pins "
                          f"{spec['settings_sha256'][:12]}…")
    script = spec.get("script", DEFAULT_SCRIPT[stage])
    under_out(folders[stage], repo, stage)
    out = {"settings": spec["settings"], "settings_sha256": settings_sha, "config": None, "config_sha256": None}
    if STAGES[stage]["style"] == "flags":
        command = [script, "--config", str(settings), "--out", str(folders[stage])]
        if spec.get("input"):
            command += ["--input-root", str(spec["input"])]
    else:
        config = generated_config(stage, settings, folders, cfg_dir, repo, write)
        command = [script, "--config", str(config)]
        out.update(config=config.as_posix(), config_sha256=sha256(config) if write else None)
    return {"command": command, **out}
