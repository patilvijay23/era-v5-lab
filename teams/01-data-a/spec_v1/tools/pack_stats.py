"""Per-pack stats pages from run_clean.py summaries: what clean.py and F2 did, and how many docs each medicine fixed or dropped.

  python spec_v1/tools/pack_stats.py --label sample --out spec_v1/results/pack_stats <out>/*_summary.json
  python spec_v1/tools/pack_stats.py --label train --out spec_v1/results/pack_stats <out>/code-go_part-*_summary.json

Summaries of one pack (parts of a split) are added up into one page, <label>_<pack>.md, and README.md lists every page in
--out. IDs, counts and benchmark item IDs only: no document or benchmark text (eval firewall, G9 #269).
"""
import argparse, json, re
from collections import Counter
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("summaries", nargs="+", type=Path)
ap.add_argument("--label", required=True, help="where the input came from, for example sample or train")
ap.add_argument("--out", type=Path, required=True)
args = ap.parse_args()
args.out.mkdir(parents=True, exist_ok=True)

packs = {}
for path in args.summaries:
    s = json.loads(path.read_text(encoding="utf-8"))
    packs.setdefault(s["pack_id"], []).append(s)

for pack, runs in sorted(packs.items()):
    rows = sum(s["rows"] for s in runs)
    fixed = sum(s["actions"].get("fix", 0) for s in runs)
    by_clean = sum(len(s["dropped"]) for s in runs)
    f2_drops = [d for s in runs for d in s.get("f2", {}).get("dropped", [])]
    errors = sum(len(s["errors"]) for s in runs)
    kept = rows - by_clean - len(f2_drops) - errors
    by_rule, seconds = {}, Counter()
    for s in runs:
        for rid, n in s.get("by_rule", {}).items():
            by_rule.setdefault(rid, Counter()).update(n)
        for rid, v in s.get("rule_seconds", {}).items():
            seconds[rid] += v["seconds"]
    sets = sorted({s["f2"]["set_sha256"] for s in runs if "f2" in s})
    lines = [f"# {pack} ({args.label})\n\n",
             f"{len(runs)} file(s): " + ", ".join(f"`{s['pack']}` ({s['rows']:,} docs, input `{s['input_sha256'][:12]}`)" for s in runs) + ".\n",
             f"`clean.py` `{'`, `'.join(sorted({s['clean_py_sha256'][:12] for s in runs}))}`; "
             + (f"F2 set `{'`, `'.join(sets)}` (full set)." if sets else "F2 not run.") + "\n\n",
             "| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |\n|---:|---:|---:|---:|---:|---:|\n",
             f"| {rows:,} | {fixed:,} | {by_clean:,} | {len(f2_drops):,} | {errors:,} | {kept:,} |\n\n",
             "## What each medicine did\n\nDocs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to "
             "more than the docs fixed.\n\n| rule | fixed | dropped | seconds |\n|---|---:|---:|---:|\n"]
    for rid, n in sorted(by_rule.items(), key=lambda kv: -sum(kv[1].values())):
        lines.append(f"| `{rid}` | {n['fix']:,} | {n['drop']:,} | {seconds[rid]:.1f} |\n" if rid != "F2" else f"| **F2** (G9 fingerprints) | | {n['drop']:,} | |\n")
    if f2_drops:
        bench = Counter(d["items"][0].split(":")[0] for d in f2_drops)
        items = Counter(d["items"][0] for d in f2_drops)
        lines += ["\n## F2 drops by benchmark\n\nBy the first benchmark item each dropped doc matched. Item IDs only.\n\n| benchmark | docs |\n|---|---:|\n",
                  *(f"| `{b}` | {n} |\n" for b, n in bench.most_common()),
                  "\nItems that dropped the most docs:\n\n| item | docs |\n|---|---:|\n",
                  *(f"| `{re.sub(r'[`|]', '', i)[:90]}` | {n} |\n" for i, n in items.most_common(10))]
    (args.out / f"{args.label}_{pack}.md").write_text("".join(lines), encoding="utf-8", newline="\n")

index = ["# Pack stats\n\nOne page per pack: made by `tools/pack_stats.py` from `run_clean.py --f2` summaries.\n\n",
         "| page | docs | fixed | dropped by `clean.py` | dropped by F2 | kept |\n|---|---:|---:|---:|---:|---:|\n"]
for page in sorted(args.out.glob("*_*.md")):
    t = page.read_text(encoding="utf-8")
    m = re.search(r"\|---:\|---:\|---:\|---:\|---:\|---:\|\n\| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \| [\d,]+ \| ([\d,]+) \|", t)
    if m:
        index.append(f"| [{page.stem}]({page.name}) | {' | '.join(m.groups())} |\n")
(args.out / "README.md").write_text("".join(index), encoding="utf-8", newline="\n")
print(f"{len(packs)} page(s) and README.md in {args.out}")
