"""Reconcile the shards with the ledger: every kept document is in exactly one shard, or left out for a stated reason.

  python -I teams/01-data-a/pipeline/reconcile_shards.py --ledger <run>/ledger --shards <run>/shards --out <dir>
         [--pack code-go ...]

The ledger (ledger.py) says what happened to every document and where each kept one is: final/<split>/<final_part>, row
<final_row>. The shard writer (shards/shard_writer.py, via run_shards.py) records, for every document in a shard, its
input_part (<split>/<pack>/<part>.parquet of the final folder) and input_row in <shard_id>.docs.parquet, and in
<shard_id>.quality_report.json the documents it left out and why. So the two meet on (input_part, input_row): one join.
It decides nothing and changes nothing. Built with pyarrow joins: no Python loop over documents.

INPUT
=====
--ledger   ledger.py's folder: <split>/<pack>.parquet (and ledger_summary.json)
--shards   run_shards.py's --out: shards_summary.json, <shard_id>.docs.parquet, <shard_id>.json, <shard_id>.quality_report.json
--pack     the packs the shard stage was asked for (stages.shards.packs). Default: the packs in shards_summary.json. Kept
           documents of other packs are "not_selected", which is not an error

EVERY KEPT DOCUMENT GETS ONE STATUS (column shard_status)
========================================================
  in_shard          in <shard_id>.docs.parquet at its ledger position (input_part, input_row), with its doc_id
  left_out:<why>    the writer left it out and says why in the quality report: secret (it matches pr-guard's email or
                    secret patterns), empty (no tokens), special (it holds a special token), roundtrip (decode(encode(text))
                    differs from the text)
  not_sharded       its part's status is not_sharded: a held-out part (the shard format has train and validation only)
  not_selected      its pack is not among --pack
  not_reached       its part was written but cut short ("truncated": rows after rows_read did not fit in the shard). This
                    is data loss, so it fails (Vijay on #39, point 1)
  part_<status>     its part failed or was skipped by run_shards.py: fails
  missing           none of the above: its part was written and reached its row, but it is in no shard: fails

CHECKS (any failure: exit code 1, after writing the outputs, so they show what failed)
=====================================================================================
  - every document in a shard is a kept document of the ledger, at the same (input_part, input_row), with the same doc_id:
    no dropped, removed or unknown document reached a shard
  - no (input_part, input_row) is in two shards
  - every document the writer left out is a kept document of that part, and none is also in a shard
  - each shard manifest's doc_count = its docs.parquet rows
  - no kept document of a selected pack is not_reached, part_failed, part_skipped or missing

OUTPUT (in --out)
=================
  reconcile_docs.parquet    one row per kept document: pack_id, split, input_part, input_row, doc_id, shard_id, shard_status
  reconcile_summary.json    per pack and split: kept, and the count of each status; the checks; the sha256 of every input
IDs and counts only, never text.
"""
import sys
sys.dont_write_bytecode = True

import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

SUMMARY = "shards_summary.json"
REASONS = ("secret", "empty", "special", "roundtrip")  # shard_writer.py's left_out keys
FAILING = ("not_reached", "part_failed", "part_skipped", "missing")


class Stop(Exception):
    """The inputs cannot be read, or the reconciliation failed: the message says why."""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def const(value, n, typ):
    import pyarrow as pa
    return pa.repeat(pa.scalar(value, typ), n)


def read_ledger(folder):
    """The ledger's kept documents: pack_id, split, input_part, input_row, doc_id."""
    import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq
    files = sorted(Path(folder).glob("*/*.parquet"))
    if not files:
        raise Stop(f"--ledger {folder}: no <split>/<pack>.parquet files")
    t = pa.concat_tables(pq.read_table(f, columns=["pack_id", "split", "doc_id", "final", "final_part", "final_row"])
                         for f in files)
    kept = t.filter(pc.equal(t["final"], "kept"))
    return pa.table({"pack_id": kept["pack_id"], "split": kept["split"],
                     "input_part": pc.binary_join_element_wise(kept["split"], kept["final_part"], "/"),
                     "input_row": kept["final_row"], "doc_id": kept["doc_id"]}), [f for f in files], t.num_rows


def read_shards(folder):
    """(summary, docs in shards: shard_id, doc_id, input_part, input_row; left-out docs: input_part, doc_id, reason;
    the manifests' doc_count per shard; the files read)."""
    import pyarrow as pa, pyarrow.parquet as pq
    folder = Path(folder)
    if not (folder / SUMMARY).is_file():
        raise Stop(f"--shards {folder}: no {SUMMARY}")
    summary = json.loads((folder / SUMMARY).read_text(encoding="utf-8"))
    docs, left, counts, files = [], [], {}, [folder / SUMMARY]
    for name, e in sorted(summary.get("parts", {}).items()):
        if e.get("status") != "written":
            continue
        sid = e["shard_id"]
        meta, man, rep = (folder / f"{sid}{x}" for x in (".docs.parquet", ".json", ".quality_report.json"))
        for f in (meta, man, rep):
            if not f.is_file():
                raise Stop(f"{name}: written as {sid}, but {f.name} is not in --shards")
        files += [meta, man, rep]
        t = pq.read_table(meta, columns=["doc_id", "input_part", "input_row"])
        docs.append(t.append_column("shard_id", const(sid, t.num_rows, pa.string())))
        counts[sid] = (json.loads(man.read_text(encoding="utf-8")).get("doc_count"), t.num_rows)
        r = json.loads(rep.read_text(encoding="utf-8"))
        part = r.get("upstream", {}).get("input_part", name)
        for why in REASONS:
            ids = [d["doc_id"] if isinstance(d, dict) else d for d in r.get("left_out_docs", {}).get(why, [])]
            if ids:
                left.append(pa.table({"input_part": const(part, len(ids), pa.string()), "doc_id": pa.array(ids, pa.string()),
                                      "reason": const(why, len(ids), pa.string())}))
    empty_docs = pa.table({"doc_id": pa.array([], pa.string()), "input_part": pa.array([], pa.string()),
                           "input_row": pa.array([], pa.int64()), "shard_id": pa.array([], pa.string())})
    empty_left = pa.table({"input_part": pa.array([], pa.string()), "doc_id": pa.array([], pa.string()),
                           "reason": pa.array([], pa.string())})
    docs_t = pa.concat_tables([t.cast(empty_docs.schema) for t in docs]) if docs else empty_docs
    left_t = pa.concat_tables(left) if left else empty_left
    return summary, docs_t, left_t, counts, files


def reconcile(ledger, shards, out, packs=None):
    """Write the outputs; return the summary. Raises Stop when a check fails (after writing) or an input is unreadable."""
    import pyarrow as pa, pyarrow.compute as pc, pyarrow.parquet as pq
    kept, ledger_files, ledger_rows = read_ledger(ledger)
    summary, docs, left, counts, shard_files = read_shards(shards)
    parts = summary.get("parts", {})
    scope = set(packs) if packs else {e.get("pack_id") for e in parts.values()}
    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    # 1. every document in a shard is a kept document at its ledger position
    j = docs.join(kept.rename_columns(["pack_id", "split", "input_part", "input_row", "ledger_doc"]),
                  ["input_part", "input_row"], join_type="left outer")
    unknown = j.filter(pc.is_null(j["ledger_doc"]))
    other = j.filter(pc.and_(pc.is_valid(j["ledger_doc"]), pc.not_equal(j["ledger_doc"], j["doc_id"])))
    check("every document in a shard is a kept document at its ledger position", unknown.num_rows == 0 and other.num_rows == 0,
          f"{unknown.num_rows} shard row(s) at no kept ledger position, {other.num_rows} with another doc_id"
          + (f", e.g. {unknown['shard_id'][0]} {unknown['input_part'][0]} row {unknown['input_row'][0]}" if unknown.num_rows else ""))
    # 2. no position twice
    dup = docs.group_by(["input_part", "input_row"]).aggregate([("shard_id", "count")])
    dup = dup.filter(pc.greater(dup["shard_id_count"], 1))
    check("no document is in two shards", dup.num_rows == 0, f"{dup.num_rows} position(s) in more than one shard")
    # 3. left-out documents are kept documents of their part
    left = left.group_by(["input_part", "doc_id"]).aggregate([("reason", "min")]).rename_columns(
        ["input_part", "doc_id", "reason"])  # one row per document, even if a report lists it twice
    lj = left.join(kept.select(["input_part", "doc_id", "input_row"]), ["input_part", "doc_id"], join_type="left outer")
    stray = lj.filter(pc.is_null(lj["input_row"])).num_rows
    both = left.join(docs.select(["input_part", "doc_id", "shard_id"]), ["input_part", "doc_id"], join_type="inner").num_rows
    check("every document the writer left out is a kept document of that part, and none is also in a shard",
          stray == 0 and both == 0, f"{stray} left-out doc_id(s) not kept there, {both} both left out and in a shard")
    # 4. manifests agree with their docs.parquet
    bad = sorted(sid for sid, (want, got) in counts.items() if want != got)
    check("each shard manifest's doc_count = its docs.parquet rows", not bad, f"{len(bad)} shard(s) differ, e.g. {bad[0] if bad else ''}")

    # the status of every kept document
    n = kept.num_rows
    placed = docs.group_by(["input_part", "input_row"]).aggregate([("shard_id", "min")]).rename_columns(
        ["input_part", "input_row", "shard_id"])  # one row per position, even when check 2 found it in two shards
    k = kept.join(placed, ["input_part", "input_row"], join_type="left outer")
    k = k.join(lj.select(["input_part", "doc_id", "reason"]), ["input_part", "doc_id"], join_type="left outer")
    part_rows = [(name, e.get("status"), e.get("rows_read")) for name, e in parts.items()]
    pt = pa.table({"input_part": pa.array([p[0] for p in part_rows], pa.string()),
                   "part_status": pa.array([p[1] for p in part_rows], pa.string()),
                   "rows_read": pa.array([p[2] for p in part_rows], pa.int64())})  # one row per part, not per document
    k = k.join(pt, "input_part", join_type="left outer").sort_by([("input_part", "ascending"), ("input_row", "ascending")])
    in_scope = pc.is_in(k["pack_id"], value_set=pa.array(sorted(scope), pa.string()))
    ps = k["part_status"]
    beyond = pc.fill_null(pc.greater_equal(k["input_row"], k["rows_read"]), False)
    status = pc.if_else(pc.is_valid(k["shard_id"]), "in_shard",
             pc.if_else(pc.is_valid(k["reason"]), pc.binary_join_element_wise("left_out", k["reason"], ":"),
             pc.if_else(pc.invert(in_scope), "not_selected",
             pc.if_else(pc.fill_null(pc.equal(ps, "not_sharded"), False), "not_sharded",
             pc.if_else(pc.fill_null(pc.equal(ps, "failed"), False), "part_failed",
             pc.if_else(pc.fill_null(pc.equal(ps, "skipped"), False), "part_skipped",
             pc.if_else(pc.and_(pc.fill_null(pc.equal(ps, "written"), False), beyond), "not_reached", "missing")))))))
    rows = pa.table({"pack_id": k["pack_id"], "split": k["split"], "input_part": k["input_part"], "input_row": k["input_row"],
                     "doc_id": k["doc_id"], "shard_id": k["shard_id"], "shard_status": status})
    if rows.num_rows != n:  # the ledger refuses a doc_id twice in a part, so this means inputs that are not the ledger's
        raise Stop(f"{rows.num_rows} statuses for {n} kept documents: a doc_id appears twice in a part of --ledger")

    by = defaultdict(lambda: defaultdict(Counter))
    for g in rows.group_by(["pack_id", "split", "shard_status"]).aggregate([("doc_id", "count")]).to_pylist():
        by[g["pack_id"]][g["split"]][g["shard_status"]] += g["doc_id_count"]
    totals = Counter()
    for pack in by:
        for split in by[pack]:
            totals.update(by[pack][split])
    failing = {s: totals[s] for s in FAILING if totals[s]}
    check("every kept document of a selected pack is in a shard or left out for a stated reason", not failing,
          f"{failing}" if failing else "all accounted")

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pq.write_table(rows, out / "reconcile_docs.parquet")
    result = {"tool": "reconcile_shards.py", "code_sha256": sha256(Path(__file__)),
              "inputs": {"ledger_files": {f.relative_to(Path(ledger)).as_posix(): sha256(f) for f in ledger_files},
                         "shard_files": {f.name: sha256(f) for f in shard_files}},
              "packs": sorted(scope), "ledger_rows": ledger_rows, "kept": n, "in_shards": docs.num_rows,
              "totals": dict(sorted(totals.items())),
              "by_pack": {p: {s: dict(sorted(c.items())) for s, c in sorted(by[p].items())} for p in sorted(by)},
              "checks": checks, "ok": all(c["ok"] for c in checks)}
    (out / "reconcile_summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not result["ok"]:
        failed = [c for c in checks if not c["ok"]]
        raise Stop(f"{len(failed)} check(s) failed, e.g. {failed[0]['check']}: {failed[0]['detail']}")
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", type=Path, required=True, help="ledger.py's folder")
    ap.add_argument("--shards", type=Path, required=True, help="run_shards.py's --out folder")
    ap.add_argument("--out", type=Path, required=True, help="where reconcile_docs.parquet and reconcile_summary.json go")
    ap.add_argument("--pack", action="append", default=[], help="a pack the shard stage was asked for (repeatable)")
    args = ap.parse_args()
    try:
        r = reconcile(args.ledger, args.shards, args.out, args.pack or None)
    except Stop as e:
        sys.exit(f"reconcile_shards: {e}")
    print(json.dumps({"kept": r["kept"], "in_shards": r["in_shards"], **r["totals"]}))


if __name__ == "__main__":
    main()
