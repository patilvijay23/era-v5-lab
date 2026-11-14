"""Stand-in for run_tokenizer_sample.py, overlap.py and dedup.py in the runner's tests.

It takes the command line the runner gives them (--config, and for clean --out and --input-root), copies the folder named
by "fixture" in the settings file to the output folder, and prints what it was given (the runner's log keeps it). The output
is --out when given, else the config's "out" (relative to the working directory, the repository root, as overlap.py reads it).
Like the real clean job it refuses an output folder that already exists.
"""
import argparse, json, shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--config", type=Path, required=True)
ap.add_argument("--out", type=Path)
ap.add_argument("--input-root", type=Path)
a = ap.parse_args()
cfg = json.loads(a.config.read_text(encoding="utf-8"))
out = a.out or Path(cfg["out"])
shutil.copytree(cfg["fixture"], out)
print(json.dumps({"config": a.config.as_posix(), "out": out.as_posix(), "input_root": a.input_root.as_posix() if a.input_root else None,
                  "keys": {k: cfg.get(k) for k in ("inputs", "out", "results")}}))
