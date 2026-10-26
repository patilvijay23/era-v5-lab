"""Read a sample pack one document at a time, with hidden characters made visible.

Usage:
    python view_pack.py <pack.parquet> [--start N] [--hex]

Keys: Enter = next document, b = back, h = toggle hex dump, q = quit.
"""
import sys, unicodedata, argparse
import pyarrow.parquet as pq

VISIBLE = {
    "​": "⟦ZWSP⟧", "‌": "⟦ZWNJ⟧", "‍": "⟦ZWJ⟧", "﻿": "⟦BOM⟧", "­": "⟦SHY⟧",
    "‪": "⟦LRE⟧", "‫": "⟦RLE⟧", "‬": "⟦PDF⟧", "‭": "⟦LRO⟧", "‮": "⟦RLO⟧",
    "⁦": "⟦LRI⟧", "⁧": "⟦RLI⟧", "⁨": "⟦FSI⟧", "⁩": "⟦PDI⟧", "�": "⟦U+FFFD⟧",
    "\t": "⟦TAB⟧",
}

def show(text: str) -> str:
    out = []
    for ch in text:
        if ch in VISIBLE:
            out.append(VISIBLE[ch])
        elif ch != "\n" and unicodedata.category(ch) == "Cc":
            out.append(f"⟦U+{ord(ch):04X}⟧")
        else:
            out.append(ch)
    return "".join(out)

def hexdump(text: str, limit: int = 2000) -> str:
    rows = []
    for i, ch in enumerate(text[:limit]):
        if ord(ch) > 127 or unicodedata.category(ch)[0] in "CZ":
            rows.append(f"{i:6d}  U+{ord(ch):04X}  {unicodedata.name(ch, '?')}")
    return "\n".join(rows) or "(no non-ASCII characters in the first part)"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack"); ap.add_argument("--start", type=int, default=0); ap.add_argument("--hex", action="store_true")
    a = ap.parse_args()
    t = pq.read_table(a.pack).to_pylist()
    i, hx = a.start, a.hex
    while 0 <= i < len(t):
        d = t[i]
        print("\n" + "=" * 100)
        print(f"[{i + 1}/{len(t)}] doc_id={d['doc_id']}  source={d['source']}  lang_label={d['lang_label']}  chars={len(d['text'])}")
        if d.get("url"): print("url:", d["url"])
        print("-" * 100); print(show(d["text"]))
        if hx: print("-" * 100); print(hexdump(d["text"]))
        k = input("\n[Enter]=next  b=back  h=hex  q=quit > ").strip().lower()
        if k == "q": break
        elif k == "b": i -= 1
        elif k == "h": hx = not hx
        else: i += 1

if __name__ == "__main__":
    main()
