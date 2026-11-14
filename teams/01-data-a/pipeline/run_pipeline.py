"""One command for Data A's pipeline: clean -> overlap -> dedup -> apply the remove list -> F2 -> survivor loss -> shards.

  python -I teams/01-data-a/pipeline/run_pipeline.py --config teams/01-data-a/pipeline/pipeline.json [--from STAGE] [--to STAGE]

It runs or adopts each stage in order, checks that each stage follows from the one before (counts and sha256 links), and
writes <out>/<run_id>/pipeline_manifest.json. It never reimplements a stage: clean (#244), overlap and dedup (#255) and F2
(run_f2.py, #35) are the team's scripts, called as they are; apply_dedup.py and survivor_loss.py are in this folder.

STAGES
======
  clean          cleaned parts: <output>/train/**.parquet and/or <output>/heldout/**.parquet              (TSAI job, #244)
  overlap        overlap_summary.json, overlap_matches.csv, overlap_docs.parquet                          (TSAI job, #255)
  dedup          remove_list.csv, dedup_groups.csv, dedup_summary.json                                    (TSAI job, #255)
  apply          apply_dedup.py on clean's output with dedup's remove list  -> <run>/deduped
  f2             run_f2.py on <run>/deduped/<split>                           -> <run>/final/<split>
                 (one process per split; with "workers": N, up to N processes at once, one per pack folder)
  survivor_loss  survivor_loss.py on dedup_groups.csv and F2's reports        -> <run>/report
  shards         optional, only with stages.shards: writes <run>/cleaning_pipeline.json (clean.py sha256, F2 set, dedup remove
                 list: the processing behind the shards), then shards/run_shards.py on <run>/final   -> <run>/shards (or "out")
                 It runs after the manifest holds every earlier stage, which is what the shard writer reads; its own record is
                 added to the manifest afterwards. The stage stops the run if a part failed or was skipped, if no shard was
                 written, or if the summary is not this run's. --from shards runs only this stage, into an out folder without shards.

clean, overlap and dedup take "mode": "adopt" (TSAI ran the job; "output" names the folder it returned) or "mode": "run"
("command": the script and its arguments, run with this Python from the repository root; "output": where that script writes).
apply, f2 and survivor_loss always run. f2 takes "script" (default teams/01-data-a/spec_v1/run_f2.py) and "workers"
(default 1; each run_f2.py process loads G9's full set, about 1.1 GB of memory, so N workers need about N × 1.1 GB plus the
documents in flight). shards takes "tokenizer" (required: G3's C3 tokenizer.json), and optionally "script" (default
teams/01-data-a/shards/run_shards.py), "out" (default <run>/shards), "tokens", "packs" (only these packs), "pack_table" and
"any_tokenizer" (tests only). apply takes "link" (default true: untouched parts are hard-linked, not copied). Scripts run with
python -I, which ignores user site-packages and PYTHONPATH: install pyarrow and the rest into the environment itself.
Each script's output streams to <run>/logs/<stage>.log (F2: logs/f2_<split>[_<pack>].log).
Without stages.shards the run stops after survivor_loss, and --to shards is an error.

CONFIG (JSON; keys starting with "_" are comments; paths relative to the repository root, or absolute)
=====================================================================================================
  run_id   name of this run;   out   folder for runs (default out/pipeline);   stages   as above
The whole config is checked before the first stage runs.

CHECKS (any failure stops the run; exit code 1)
==============================================
  overlap   status complete; documents_all = the cleaned rows; for every part it lists, its documents = that cleaned part's rows
  dedup     status complete; the overlap_matches.csv and overlap_docs.parquet it checked (overlap_run.checked_sha256) are
            the adopted overlap's files; documents_all = overlap's; removed = remove_list.csv rows; heldout_removed = 0
  apply     rows = the cleaned rows; removed = the remove list (apply_dedup.py also checks every listed row)
  f2        per split: its rows = apply's kept rows; every part's report names, as input_sha256, the sha256 apply wrote;
            one fingerprint set; kept + dropped + errors = rows; no errors; no stale Parquet under final/<split>
  survivor  groups = the groups in dedup_groups.csv
  --from    every earlier stage's output still has the digest the manifest recorded for it

MANIFEST
========
<out>/<run_id>/pipeline_manifest.json: the git commit, Python and pyarrow versions; per stage its mode, command, the script's
sha256, its output folder's digest and file count, its counts, its checks and its seconds; all checks; totals (cleaned, removed
by dedup, dropped by F2, final, and shards_written when the shard stage ran). A digest is the sha256 over the sorted relative path and sha256 of every file in the folder;
JSON summaries are hashed without the fields that change between identical runs (timings, absolute paths, skip flags), so two
runs on the same inputs give the same digests. IDs, counts and hashes only.
"""
import sys
sys.dont_write_bytecode = True

import argparse, hashlib, json, platform, subprocess, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
STAGES = ("clean", "overlap", "dedup", "apply", "f2", "survivor_loss", "shards")
OPTIONAL = ("shards",)  # runs only when stages.shards is configured
EXTERNAL = ("clean", "overlap", "dedup")
NEEDED = {"overlap": ("overlap_summary.json", "overlap_matches.csv", "overlap_docs.parquet"),
          "dedup": ("remove_list.csv", "dedup_groups.csv", "dedup_summary.json")}
DEFAULT_F2 = "teams/01-data-a/spec_v1/run_f2.py"
DEFAULT_SHARDS = "teams/01-data-a/shards/run_shards.py"
SPLITS = ("train", "heldout")
VOLATILE = {"seconds", "input", "path", "cleaned", "skipped"}  # JSON fields that differ between identical runs


class Stop(Exception):
    """A check failed: the message says which and where."""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stable(obj):
    if isinstance(obj, dict):
        return {k: stable(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [stable(v) for v in obj]
    return obj


def file_hash(p):
    """sha256 of a file; for JSON, of its content without the volatile fields."""
    if p.suffix == ".json":
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return hashlib.sha256(json.dumps(stable(data), sort_keys=True).encode("utf-8")).hexdigest()
        except (ValueError, UnicodeDecodeError):
            pass
    return sha256(p)


def digest(folder):
    """(digest over every file's relative path and hash, file count)."""
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.name.endswith(".tmp"))
    h = hashlib.sha256()
    for p in files:
        h.update(f"{p.relative_to(folder).as_posix()}\t{file_hash(p)}\n".encode("utf-8"))
    return h.hexdigest(), len(files)


def path(p):
    p = Path(p)
    return p if p.is_absolute() else REPO / p


def run_script(script, args, stage, log):
    """Run a script with this Python from the repository root, its output streamed to log. Returns the exit code."""
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-I", str(path(script)), *map(str, args)]
    with open(log, "w", encoding="utf-8", errors="replace") as f:
        f.write("$ " + " ".join(cmd) + "\n")
        f.flush()
        return subprocess.run(cmd, cwd=REPO, stdout=f, stderr=subprocess.STDOUT).returncode


def tail(log, n=5):
    try:
        return " | ".join(Path(log).read_text(encoding="utf-8", errors="replace").strip().splitlines()[-n:])
    except OSError:
        return ""


def parquet_rows(folder):
    """{"rows", "by_split", "by_part" ({"<split>/<part>": rows})} from the Parquet footers."""
    import pyarrow.parquet as pq
    by_split, by_part = {}, {}
    for split in SPLITS:
        if (folder / split).is_dir():
            for f in sorted((folder / split).rglob("*.parquet")):
                n = pq.ParquetFile(f).metadata.num_rows
                by_part[f"{split}/{f.relative_to(folder / split).as_posix()}"] = n
                by_split[split] = by_split.get(split, 0) + n
    if not by_split:
        raise Stop(f"clean: {folder} has no Parquet parts under train/ or heldout/")
    return {"rows": sum(by_split.values()), "by_split": by_split, "by_part": by_part}


def csv_rows(file):
    with open(file, encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in f) - 1, 0)


def load_json(file):
    return json.loads(Path(file).read_text(encoding="utf-8"))


class Run:
    def __init__(self, cfg_path):
        self.cfg_path = Path(cfg_path)
        self.cfg = load_json(self.cfg_path)
        if not self.cfg.get("run_id"):
            raise Stop(f"{cfg_path}: run_id is missing")
        self.dir = path(self.cfg.get("out", "out/pipeline")) / self.cfg["run_id"]
        self.manifest_path = self.dir / "pipeline_manifest.json"
        self.stages = self.cfg.get("stages", {})
        self.done, self.checks = {}, []

    def output(self, stage):
        if stage in EXTERNAL:
            return path(self.stages[stage]["output"])
        if stage == "shards":
            return path(self.stages["shards"]["out"]) if self.stages.get("shards", {}).get("out") else self.dir / "shards"
        return self.dir / {"apply": "deduped", "f2": "final", "survivor_loss": "report"}[stage]

    def validate(self, upto):
        """The whole config, before anything runs."""
        for stage in EXTERNAL:
            spec = self.stages.get(stage)
            if not isinstance(spec, dict) or not spec.get("output"):
                raise Stop(f"config: stages.{stage}.output is missing")
            mode = spec.get("mode", "adopt")
            if mode not in ("adopt", "run"):
                raise Stop(f"config: stages.{stage}.mode is {mode!r}, expected adopt or run")
            if mode == "run":
                cmd = spec.get("command")
                if not cmd or not isinstance(cmd, list):
                    raise Stop(f"config: stages.{stage}.command (a list: script, then arguments) is missing for mode run")
                if not path(cmd[0]).is_file():
                    raise Stop(f"config: stages.{stage}.command script {cmd[0]} not found")
        workers = self.stages.get("f2", {}).get("workers", 1)
        if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
            raise Stop(f"config: stages.f2.workers is {workers!r}, expected a whole number >= 1")
        if STAGES.index(upto) >= STAGES.index("f2"):
            script = self.stages.get("f2", {}).get("script", DEFAULT_F2)
            if not path(script).is_file():
                raise Stop(f"config: f2 script {script} not found (run_f2.py is in PR #35; set stages.f2.script)")
        if "shards" in self.stages or upto == "shards":
            self.validate_shards(upto)
        for stage in EXTERNAL:
            o, r = self.output(stage).resolve(), self.dir.resolve()
            if o == r or r in o.parents or o in r.parents:
                raise Stop(f"config: stages.{stage}.output and the run folder {self.dir} overlap")

    def validate_shards(self, upto):
        spec = self.stages.get("shards")
        if STAGES.index(upto) < STAGES.index("shards"):
            return
        if not isinstance(spec, dict):
            raise Stop("config: stages.shards is not configured (it needs at least a tokenizer); the run stops after survivor_loss without it")
        if not spec.get("tokenizer") or not path(spec["tokenizer"]).is_file():
            raise Stop(f"config: stages.shards.tokenizer {spec.get('tokenizer')!r} is missing or not a file")
        script = spec.get("script", DEFAULT_SHARDS)
        if not path(script).is_file():
            raise Stop(f"config: shards script {script} not found")
        tokens = spec.get("tokens")
        if tokens is not None and (not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 1):
            raise Stop(f"config: stages.shards.tokens is {tokens!r}, expected a whole number >= 1")
        packs = spec.get("packs", [])
        if not isinstance(packs, list) or not all(isinstance(p, str) for p in packs):
            raise Stop("config: stages.shards.packs must be a list of pack ids")
        if spec.get("pack_table") and not path(spec["pack_table"]).is_file():
            raise Stop(f"config: stages.shards.pack_table {spec['pack_table']} not found")

    def check(self, name, ok, detail):
        self.checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            raise Stop(f"check failed: {name}: {detail}")

    # --- the stages -------------------------------------------------------------------------------------------------
    def stage_external(self, stage):
        spec = self.stages[stage]
        mode = spec.get("mode", "adopt")
        command = spec.get("command") if mode == "run" else None
        if command:
            log = self.dir / "logs" / f"{stage}.log"
            rc = run_script(command[0], command[1:], stage, log)
            if rc != 0:
                raise Stop(f"{stage}: {Path(command[0]).name} failed with exit code {rc}: {tail(log)}")
        out = self.output(stage)
        for name in NEEDED.get(stage, ()):
            if not (out / name).is_file():
                raise Stop(f"{stage}: {out} has no {name}")
        counts = getattr(self, f"counts_{stage}")(out)
        return {"mode": mode, "command": command, "code_sha256": sha256(path(command[0])) if command else None,
                "output": spec["output"], "counts": counts}

    def counts_clean(self, out):
        return parquet_rows(out)

    def counts_overlap(self, out):
        s = load_json(out / "overlap_summary.json")
        clean = self.done["clean"]["counts"]
        self.check("overlap finished", s.get("status") == "complete", f"status {s.get('status')!r}")
        self.check("overlap read every cleaned row", s.get("documents_all") == clean["rows"],
                   f"overlap documents_all {s.get('documents_all')}, cleaned rows {clean['rows']}")
        listed = {p["part"].replace("\\", "/"): p["documents"] for p in s.get("inputs", {}).get("parts", [])}
        if listed:
            diff = sorted(p for p in set(listed) | set(clean["by_part"]) if listed.get(p) != clean["by_part"].get(p))
            self.check("overlap read these cleaned parts", not diff,
                       f"{len(diff)} part(s) differ in name or row count, e.g. {diff[0] if diff else ''}")
        files = {}
        for name in ("overlap_matches.csv", "overlap_docs.parquet"):
            files[name] = sha256(out / name)
            want = s.get("outputs", {}).get(name, {}).get("sha256")
            if want:
                self.check(f"{name} matches overlap's summary", files[name] == want, f"{files[name][:12]}… vs {want[:12]}…")
        return {"documents_all": s.get("documents_all"), "parts": len(listed), "files_sha256": files}

    def counts_dedup(self, out):
        s = load_json(out / "dedup_summary.json")
        ov = self.done["overlap"]["counts"]
        groups = set()
        with open(out / "dedup_groups.csv", encoding="utf-8", newline="") as f:
            next(f, None)
            groups = {line.split(",", 1)[0] for line in f if line.strip()}
        counts = {"remove_list_rows": csv_rows(out / "remove_list.csv"), "removed": s.get("removed"),
                  "heldout_removed": s.get("heldout_removed"), "groups": len(groups)}
        self.check("dedup finished", s.get("status") == "complete", f"status {s.get('status')!r}")
        checked = s.get("overlap_run", {}).get("checked_sha256", {})
        self.check("dedup used this overlap run", checked == ov["files_sha256"],
                   f"dedup checked {sorted((k, v[:12]) for k, v in checked.items())}, "
                   f"the adopted overlap has {sorted((k, v[:12]) for k, v in ov['files_sha256'].items())}")
        self.check("dedup saw overlap's documents", s.get("documents_all") == ov["documents_all"],
                   f"dedup documents_all {s.get('documents_all')}, overlap {ov['documents_all']}")
        self.check("dedup summary matches its remove list", counts["removed"] == counts["remove_list_rows"],
                   f"summary removed {counts['removed']}, remove_list.csv rows {counts['remove_list_rows']}")
        self.check("dedup removed no held-out doc", counts["heldout_removed"] == 0,
                   f"heldout_removed {counts['heldout_removed']} (rule 0)")
        return counts

    def stage_apply(self):
        import apply_dedup
        out, clean = self.output("apply"), self.done["clean"]["counts"]
        try:
            s = apply_dedup.apply(self.output("clean"), self.output("dedup") / "remove_list.csv", out,
                                  splits=tuple(sp for sp in SPLITS if sp in clean["by_split"]),
                                  link=bool(self.stages.get("apply", {}).get("link", True)))
        except apply_dedup.Stop as e:
            raise Stop(f"apply: {e}")
        counts = dict(s["totals"])
        counts["kept_by_split"] = {}
        for p in s["parts"]:
            counts["kept_by_split"][p["split"]] = counts["kept_by_split"].get(p["split"], 0) + p["kept"]
        self.check("apply read every cleaned row", counts["rows"] == clean["rows"],
                   f"apply rows {counts['rows']}, cleaned rows {clean['rows']}")
        self.check("apply removed the remove list", counts["removed"] == self.done["dedup"]["counts"]["remove_list_rows"],
                   f"apply removed {counts['removed']}, remove list {self.done['dedup']['counts']['remove_list_rows']}")
        self.apply_parts = {(p["split"], p["part"]): p["output_sha256"] for p in s["parts"]}
        return {"mode": "run", "command": ["teams/01-data-a/pipeline/apply_dedup.py"],
                "code_sha256": s["code_sha256"], "output": "deduped", "counts": counts}

    def f2_units(self, src, split, workers):
        """The F2 work units of one split: the whole split with one worker, else one unit per pack folder (plus one
        for Parquet files sitting directly in the split folder). Each unit: (name, inputs, out)."""
        out = self.output("f2") / split
        if workers <= 1:
            return [(split, [src / split], out)]
        units = [(f"{split}/{d.name}", [d], out / d.name) for d in sorted((src / split).iterdir())
                 if d.is_dir() and any(d.rglob("*.parquet"))]
        loose = sorted(f for f in (src / split).glob("*.parquet") if f.is_file())
        if loose:
            units.append((f"{split}/(files)", loose, out))
        return units

    def stage_f2(self):
        from concurrent.futures import ThreadPoolExecutor
        spec = self.stages.get("f2", {})
        script, workers = spec.get("script", DEFAULT_F2), int(spec.get("workers", 1))
        src, out = self.output("apply"), self.output("f2")
        parts = getattr(self, "apply_parts", None)
        if parts is None:  # apply was recorded by an earlier run
            s = load_json(src / "apply_dedup_summary.json")
            parts = {(p["split"], p["part"]): p["output_sha256"] for p in s["parts"]}
        kept_by_split = self.done["apply"]["counts"]["kept_by_split"]
        splits = [sp for sp in SPLITS if (src / sp).is_dir()]
        for split in splits:  # before any F2 runs
            mine = {p for (sp, p) in parts if sp == split}
            if (out / split).is_dir():
                stale = sorted(f.relative_to(out / split).as_posix() for f in (out / split).rglob("*.parquet")
                               if f.relative_to(out / split).as_posix() not in mine)
                self.check(f"no stale F2 output in final/{split}", not stale,
                           f"{len(stale)} Parquet file(s) from an earlier run, e.g. {stale[0] if stale else ''}")
        units = [u for sp in splits for u in self.f2_units(src, sp, workers)]

        def one(unit):
            name, inputs, dst = unit
            log = self.dir / "logs" / ("f2_" + name.replace("/", "_").replace("(", "").replace(")", "") + ".log")
            rc = run_script(script, ["--inputs", *inputs, "--out", dst], "f2", log)
            return name, dst, rc, log

        t0 = time.time()
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:  # each thread waits on its own run_f2 process
            results = list(pool.map(one, units))
        failed = [(n, rc, log) for n, dst, rc, log in results if rc != 0 and not (dst / "f2_summary.json").is_file()]
        if failed:
            n, rc, log = failed[0]
            raise Stop(f"f2: {len(failed)} of {len(units)} unit(s) failed without a summary, e.g. {n} "
                       f"(exit code {rc}): {tail(log)}. Rerun --from f2: finished files are skipped")

        totals = {"rows": 0, "kept": 0, "dropped_by_f2": 0, "errors": 0}
        by_split, sets = {sp: dict.fromkeys(totals, 0) for sp in splits}, set()
        for name, dst, rc, log in results:
            s = load_json(dst / "f2_summary.json")
            sets.add(s.get("set_sha256"))
            errors = s.get("errors", 0)
            errors = len(errors) if isinstance(errors, list) else errors
            split = name.split("/")[0]
            for k, v in (("rows", s.get("rows", 0)), ("kept", s.get("kept", 0)),
                         ("dropped_by_f2", s.get("dropped_by_f2", 0)), ("errors", errors)):
                by_split[split][k] += v
                totals[k] += v
            self.check(f"F2 reported no errors on {name}", errors == 0 and rc == 0,
                       f"{errors} docs raised during the check, exit code {rc}; see {log.name}")
        for split in splits:
            self.check(f"F2 read every deduplicated row of {split}", by_split[split]["rows"] == kept_by_split.get(split),
                       f"F2 rows {by_split[split]['rows']}, apply kept {kept_by_split.get(split)}")
            wrong = []
            for part in sorted(p for (sp, p) in parts if sp == split):
                rep = out / split / (part + ".f2.json")
                got = load_json(rep).get("input_sha256") if rep.is_file() else None
                if got != parts[(split, part)]:
                    wrong.append(part)
            self.check(f"F2 read what apply wrote in {split}", not wrong,
                       f"{len(wrong)} part(s) without a matching F2 report, e.g. {wrong[0] if wrong else ''}")
        self.check("F2 used one fingerprint set", len(sets) == 1 and None not in sets, f"set_sha256 values {sorted(map(str, sets))}")
        self.check("F2 counts add up", totals["kept"] + totals["dropped_by_f2"] + totals["errors"] == totals["rows"], f"{totals}")
        return {"mode": "run", "command": [script, "--inputs", "<run>/deduped/<split>[/<pack>]", "--out", "<run>/final/<split>[/<pack>]"],
                "code_sha256": sha256(path(script)), "output": "final", "set_sha256": sets.pop(),
                "workers": workers, "units": len(units), "wall_seconds": round(time.time() - t0, 1),
                "counts": {**totals, "by_split": by_split}}

    def stage_survivor_loss(self):
        import survivor_loss
        out = self.output("survivor_loss")
        try:
            s = survivor_loss.report(self.output("dedup") / "dedup_groups.csv", self.output("f2"), out)
        except survivor_loss.Stop as e:
            raise Stop(f"survivor_loss: {e}")
        self.check("survivor loss saw every dedup group", s["groups"]["total"] == self.done["dedup"]["counts"]["groups"],
                   f"report {s['groups']['total']}, dedup_groups.csv {self.done['dedup']['counts']['groups']}")
        return {"mode": "run", "command": ["teams/01-data-a/pipeline/survivor_loss.py"], "code_sha256": s["code_sha256"],
                "output": "report", "counts": {**s["groups"], "survivors_dropped_by_f2": s["survivors_dropped_by_f2"]}}

    def stage_shards(self):
        """The cleaning_pipeline.json of the run, then run_shards.py on final/. The manifest on disk (written after the earlier
        stages) is what the shard writer reads; this stage's own record is added to the manifest afterwards."""
        spec = self.stages["shards"]
        script, out = spec.get("script", DEFAULT_SHARDS), self.output("shards")
        sys.path.insert(0, str(HERE.parent / "shards"))
        import provenance
        try:
            record_path, record = provenance.write_record(self.manifest_path, REPO)
        except provenance.Stop as e:
            raise Stop(f"shards: {e}")
        args = ["--input", self.output("f2"), "--manifest", self.manifest_path, "--tokenizer", path(spec["tokenizer"]), "--out", out]
        if spec.get("tokens"):
            args += ["--tokens", spec["tokens"]]
        for pack in spec.get("packs", []):
            args += ["--pack", pack]
        if spec.get("pack_table"):
            args += ["--pack-table", path(spec["pack_table"])]
        if spec.get("any_tokenizer"):
            args.append("--any-tokenizer")
        log = self.dir / "logs" / "shards.log"
        rc = run_script(script, args, "shards", log)
        summary_path = out / "shards_summary.json"
        if not summary_path.is_file():
            raise Stop(f"shards: {Path(script).name} failed with exit code {rc} and wrote no shards_summary.json: {tail(log)}")
        s = load_json(summary_path)
        counts, record_sha = s["counts"], sha256(record_path)
        self.check("shards: no part failed or was skipped", counts["failed"] == 0 and counts["skipped"] == 0,
                   f"{counts}; see logs/shards.log")
        self.check("shards: run_shards.py exited 0", rc == 0, f"exit code {rc}; see logs/shards.log")
        self.check("shards: at least one shard written", counts["written"] > 0, f"{counts}")
        self.check("shards: the summary is this run's, made with this run's cleaning_pipeline.json",
                   s.get("run_id") == self.cfg["run_id"] and s.get("cleaning_pipeline_sha256") == record_sha,
                   f"summary run_id {s.get('run_id')}, cleaning_pipeline_sha256 {str(s.get('cleaning_pipeline_sha256'))[:12]}…")
        return {"mode": "run", "command": [script, "--input", "<run>/final", "--manifest", "<run>/pipeline_manifest.json", "--out", "<out>"],
                "code_sha256": sha256(path(script)), "output": spec.get("out") or "shards", "cleaning_pipeline_sha256": record_sha,
                "counts": {**counts, "parts": len(s["parts"])}}

    # --- the run ----------------------------------------------------------------------------------------------------
    def execute(self, start=None, to=None):
        start, to = start or STAGES[0], to or (STAGES[-1] if "shards" in self.stages else "survivor_loss")
        for s in (start, to):
            if s not in STAGES:
                raise Stop(f"unknown stage {s!r}; stages are {', '.join(STAGES)}")
        if STAGES.index(start) > STAGES.index(to):
            raise Stop(f"--from {start} comes after --to {to}")
        self.validate(to)
        old = {s["stage"]: s for s in load_json(self.manifest_path)["stages"]} if self.manifest_path.is_file() else {}
        sys.path.insert(0, str(HERE))
        for stage in STAGES[: STAGES.index(to) + 1]:
            out = self.output(stage)
            if STAGES.index(stage) < STAGES.index(start):
                if stage not in old:
                    raise Stop(f"--from {start}: stage {stage} has no record in {self.manifest_path}; run it first")
                if not out.exists() or digest(out)[0] != old[stage]["digest"]:
                    raise Stop(f"{stage}: {out} changed after the manifest recorded it; rerun from {stage}")
                self.done[stage] = old[stage]
                continue
            t0, self.checks = time.time(), []
            rec = self.stage_external(stage) if stage in EXTERNAL else getattr(self, f"stage_{stage}")()
            rec["digest"], rec["files"] = digest(out)
            self.done[stage] = {"stage": stage, **rec, "checks": self.checks, "seconds": round(time.time() - t0, 1)}
            self.write()
            print(f"{stage}: {json.dumps({k: v for k, v in self.done[stage]['counts'].items() if k != 'by_part'})}",
                  file=sys.stderr, flush=True)
        return self.write()

    def write(self):
        c = {s: self.done[s]["counts"] for s in self.done}
        totals = {}
        if "clean" in c:
            totals["cleaned"] = c["clean"]["rows"]
        if "apply" in c:
            totals["removed_by_dedup"] = c["apply"]["removed"]
        if "f2" in c:
            totals["dropped_by_f2"] = c["f2"]["dropped_by_f2"]
            totals["final"] = c["f2"]["kept"]
        if "shards" in c:
            totals["shards_written"] = c["shards"]["written"]
        stages = [self.done[s] for s in STAGES if s in self.done]
        manifest = {"tool": "run_pipeline.py", "run_id": self.cfg["run_id"], "config": self.cfg,
                    "code_sha256": sha256(Path(__file__)), "git_commit": git_commit(),
                    "python": platform.python_version(), "pyarrow": pyarrow_version(), "stages": stages,
                    "checks": [dict(ch, stage=s["stage"]) for s in stages for ch in s.get("checks", [])], "totals": totals}
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_name(self.manifest_path.name + ".tmp")
        tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        tmp.replace(self.manifest_path)
        return manifest


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True).stdout.strip() or None
    except OSError:
        return None


def pyarrow_version():
    try:
        import pyarrow
        return pyarrow.__version__
    except ImportError:
        return None


def run(config, start=None, to=None):
    return Run(config).execute(start, to)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, required=True, help="pipeline JSON config")
    ap.add_argument("--from", dest="start", choices=STAGES, help="first stage to run (earlier ones must be recorded)")
    ap.add_argument("--to", choices=STAGES, help="last stage to run")
    args = ap.parse_args()
    try:
        m = run(args.config, args.start, args.to)
    except Stop as e:
        sys.exit(f"run_pipeline: {e}")
    print(json.dumps(m["totals"]))


if __name__ == "__main__":
    main()
