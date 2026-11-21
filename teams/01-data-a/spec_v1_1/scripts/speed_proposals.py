"""Speed of the rules in sheets/proposals_english.md, against the spec v1.1 rules they replace, on the English packs.

Two timings per pack, best of --repeat passes, one process, CPU only:
  1. each rule alone, ms/doc: the proposal and the rule it replaces (DA-B3-002 is new, so it is timed alone), on the raw
     text of every doc of the pack;
  2. the whole English clean() of spec v1.1 (clean.py), docs/s, as it is and with every proposal in place of the rule it
     replaces (DA-B3-002 added after DA-B4-012), shared F1 included. It also counts the docs whose output differs.

From teams/01-data-a, with a spec_v1_1/clean.py built from spec v1.1 as on TSAI main:
  python3 -I spec_v1_1/scripts/speed_proposals.py --clean spec_v1_1/clean.py --packs <dir of the 500-doc sample packs>

Prints counts and timings only, never document text.
"""
import argparse
import importlib.util
import sys
import time
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent / "harmtest"))
import harm_test  # noqa: E402  (only its loader is used)

PACKS = ("en-dclm", "en-fineweb-edu", "en-nemotroncc", "en-nemotroncc-synth")
SWAPS = {"DA-A2-009": "DA-A2-008", "DA-C2-005": "DA-C2-003", "DA-B4-014": "DA-B4-010", "DA-F1-007": "DA-F1-005",
         "DA-B3-002": None}
AFTER = "DA-B4-012"  # DA-B3-002 runs after this rule


def load_clean(path):
    spec = importlib.util.spec_from_file_location("clean_v1_1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(doc, steps, scope, shared):
    d = dict(doc)
    for rid, f in steps:
        if doc.get("pack_id") not in scope.get(rid, {doc.get("pack_id")}):
            continue
        action, text = f(d)
        if action == "drop":
            return ("drop", doc["text"])
        d["text"] = text
    action, text = shared(d) if doc.get("pack_id") in scope["f1_rule.py"] else ("keep", d["text"])
    if action == "drop":
        return ("drop", doc["text"])
    return ("fix" if text != doc["text"] else "keep", text)


def best(fn, repeat):
    times = []
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t)
    return min(times), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True, help="spec_v1_1/clean.py")
    ap.add_argument("--packs", required=True, help="folder with <pack>.parquet")
    ap.add_argument("--sheet", default=str(HERE / "sheets" / "proposals_english.md"))
    ap.add_argument("--repeat", type=int, default=3)
    a = ap.parse_args()

    c = load_clean(a.clean)
    new = harm_test.load_rules(Path(a.sheet))[0]["RULES_BY_ID"]
    pipe = [(c._ID[m], m()) for m in c._PIPELINES["english"]]
    old = dict(pipe)
    scope = dict(c.SCOPE)
    for nid, oid in SWAPS.items():
        scope[nid] = scope[oid or AFTER]
    swapped = []
    for rid, f in pipe:
        swapped.append((rid, f))
        for nid, oid in SWAPS.items():
            if oid == rid:
                swapped[-1] = (nid, new[nid])
            elif oid is None and rid == AFTER:
                swapped.append((nid, new[nid]))
    shared = c._shared_f1_rule()

    total = {"docs": 0, "before": 0.0, "after": 0.0, "differ": 0, "errors": 0}
    for pack in PACKS:
        docs = pq.read_table(Path(a.packs) / f"{pack}.parquet").to_pylist()
        for d in docs:
            d.setdefault("pack_id", pack)
        n = len(docs)
        print(f"== {pack}: {n} docs")
        for nid, oid in SWAPS.items():
            row = [f"  {nid:<10}"]
            if oid:
                t_old, _ = best(lambda: [old[oid](d) for d in docs], a.repeat)
                row.append(f"{oid} {1000 * t_old / n:.3f}")
            t_new, _ = best(lambda: [new[nid](d) for d in docs], a.repeat)
            row.append(f"{nid} {1000 * t_new / n:.3f} ms/doc")
            print("  ".join(row))
        t_b, out_b = best(lambda: [run(d, pipe, c.SCOPE, shared) for d in docs], a.repeat)
        t_a, out_a = best(lambda: [run(d, swapped, scope, shared) for d in docs], a.repeat)
        differ = sum(x != y for x, y in zip(out_b, out_a))
        print(f"  clean()    spec v1.1 {n / t_b:.1f} docs/s, with proposals {n / t_a:.1f} docs/s "
              f"({t_b / t_a:.2f}x), {t_a:.2f} s; output differs on {differ} docs")
        total["docs"] += n
        total["before"] += t_b
        total["after"] += t_a
        total["differ"] += differ
    print(f"ALL: {total['docs']} docs, spec v1.1 {total['before']:.2f} s, with proposals {total['after']:.2f} s "
          f"({total['before'] / total['after']:.2f}x), output differs on {total['differ']} docs")


if __name__ == "__main__":
    main()
