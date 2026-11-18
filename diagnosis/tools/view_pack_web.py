"""Web viewer for a sample pack. Same logic as view_pack.py, in the browser.

Replaces the terminal viewer with a single-page web app (Python standard
library only -- http.server, no web framework). It reuses the exact
invisible-character and hex-dump logic from view_pack.py so the diagnostic
view is byte-for-byte faithful to the script.

Features
  * Diagnostic pane: each document rendered with hidden characters made
    visible (same VISIBLE map and control-char rule as view_pack.py).
  * Character offset on cursor: click or move the cursor in the diagnostic
    pane and the status bar shows the CODE-POINT offset into the raw text
    (identical to Python text[offset]) plus the code point and Unicode name.
  * Selection -> evidence + hex: select a span to auto-fill the evidence text
    (with "at offset N") and the space-separated "U+XXXX U+XXXX" hex string,
    in the exact format of labels_TEMPLATE.csv.
  * Markdown preview: a rendered preview of the document (toggle).
  * Hex dump pane: offset / code-point / Unicode-name list, initially the first
    100 code points, then 25 before + selected character + 75 after the cursor.
  * Disease highlights: candidates for DISEASES.md sections A (characters) and
    B (markup and ghost tokens) are highlighted in the diagnostic pane and
    listed with one-click "+" to tick the code and append evidence/hex.
    B3 ghost markers get a red banner. Toggle highlights with "g".
  * Per-row annotation: textboxes for every CSV column (read, verdict,
    diseases, evidence, hex, note). Save writes a server-side CSV matching
    labels_TEMPLATE.csv exactly.
  * Optional pre/post comparison: the first pack controls navigation and
    annotations; the second is left-joined by doc_id and shown alongside it.
    Removed text is red, added text is green; document headers show SHA-256
    of the exact raw UTF-8 text, with no normalization.

Usage
    python view_pack_web.py <pack.parquet> [--start N] [--port 8000]
    python view_pack_web.py <pack.parquet> --out labels.csv   # server-side save
    python view_pack_web.py <pre.parquet> <post.parquet> --out audit.csv
    python view_pack_web.py <pre.parquet> <post.parquet> --changed-only --random

Then open http://127.0.0.1:8000 in a browser.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import tempfile
import threading
import unicodedata
from contextlib import contextmanager
from collections import Counter
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import pyarrow.parquet as pq

# ---------------------------------------------------------------------------
# Shared logic (identical to view_pack.py).
# ---------------------------------------------------------------------------
VISIBLE = {
    "\u200b": "\u27e6ZWSP\u27e7", "\u200c": "\u27e6ZWNJ\u27e7",
    "\u200d": "\u27e6ZWJ\u27e7", "\ufeff": "\u27e6BOM\u27e7",
    "\u00ad": "\u27e6SHY\u27e7", "\u202a": "\u27e6LRE\u27e7",
    "\u202b": "\u27e6RLE\u27e7", "\u202c": "\u27e6PDF\u27e7",
    "\u202d": "\u27e6LRO\u27e7", "\u202e": "\u27e6RLO\u27e7",
    "\u2066": "\u27e6LRI\u27e7", "\u2067": "\u27e6RLI\u27e7",
    "\u2068": "\u27e6FSI\u27e7", "\u2069": "\u27e6PDI\u27e7",
    "\ufffd": "\u27e6U+FFFD\u27e7", "\t": "\u27e6TAB\u27e7",
}


def token_for(ch: str):
    """Return the visible token for ch, or None if ch is shown as-is.

    Mirrors view_pack.py show(): mapped specials, then non-newline control
    chars as U+XXXX, else the character itself (including newline).
    """
    if ch in VISIBLE:
        return VISIBLE[ch]
    if ch != "\n" and unicodedata.category(ch) == "Cc":
        return f"\u27e6U+{ord(ch):04X}\u27e7"
    return None


def show(text: str) -> str:
    """Identical to view_pack.py show()."""
    out = []
    for ch in text:
        tok = token_for(ch)
        out.append(tok if tok is not None else ch)
    return "".join(out)


def hexdump_rows(text: str, limit: int = 100, start: int = 0):
    """Same format as view_pack.py hexdump(), as structured rows, but listing
    every character (ASCII letters included), not just non-ASCII/control/separator.

    Each row: {offset, cp (U+XXXX), name}. Offsets are code-point indices.
    """
    rows = []
    for i, ch in enumerate(text[start:start + limit], start=start):
        rows.append({
            "offset": i,
            "cp": f"U+{ord(ch):04X}",
            "name": unicodedata.name(ch, "?"),
        })
    return rows


def hexdump_window(text: str, offset=None):
    """First 100 code points, or selected code point + 25 before + 75 after.

    Bounds clamp to the document edges; row offsets remain absolute.
    """
    count = len(text)
    if offset is None:
        start, end = 0, min(count, 100)
    else:
        offset = max(0, min(offset, count))
        start, end = max(0, offset - 25), min(count, offset + 76)
    return {"start": start, "end": end, "offset": offset, "chars": count,
            "rows": hexdump_rows(text, limit=end - start, start=start)}


def segments(text: str, marks=None):
    """Split text into display segments carrying raw code-point offsets.

    Each segment is one of:
      {"t": "text", "s": "...", "off": start_offset}            normal run
      {"t": "tok",  "s": "token", "raw": ch, "cp": "U+XXXX",
       "name": "...", "off": offset}                            invisible/ctrl

    A newline is emitted as its own text segment so the frontend can break
    lines while keeping exact offsets. Offsets are code-point indices into the
    raw text (what Python text[off] returns).

    marks (optional, from detect()) is a per-character list of finding dicts or
    None; a run is split wherever the finding changes, and segments inside a
    finding carry "dx" (disease code) and "dxl" (label) for highlighting.
    """
    segs = []
    buf = []
    buf_start = 0

    def mark_of(i):
        return marks[i] if marks else None

    def flush():
        if buf:
            seg = {"t": "text", "s": "".join(buf), "off": buf_start}
            m = mark_of(buf_start)
            if m:
                seg["dx"], seg["dxl"] = m["code"], m["label"]
            segs.append(seg)
            buf.clear()

    for i, ch in enumerate(text):
        tok = token_for(ch)
        if tok is None and ch != "\n":
            if buf and mark_of(i) is not mark_of(i - 1):
                flush()
            if not buf:
                buf_start = i
            buf.append(ch)
            continue
        flush()
        if ch == "\n":
            segs.append({"t": "text", "s": "\n", "off": i})
        else:
            seg = {
                "t": "tok", "s": tok, "raw": ch, "off": i,
                "cp": f"U+{ord(ch):04X}",
                "name": unicodedata.name(ch, "?"),
            }
            m = mark_of(i)
            if m:
                seg["dx"], seg["dxl"] = m["code"], m["label"]
            segs.append(seg)
    flush()
    return segs


# ---------------------------------------------------------------------------
# Disease detectors for sections A (characters) and B (markup and ghost
# tokens) of DISEASES.md. They only highlight candidates; the reader decides.
# ---------------------------------------------------------------------------
# A1: invisible junk. ZWJ U+200D / ZWNJ U+200C are deliberately absent: they
# are part of Indic script, not a disease.
A1_CHARS = {
    "\u200b": "zero-width space", "\ufeff": "BOM / zero-width no-break space",
    "\u00ad": "soft hyphen", "\u2060": "word joiner",
    "\u200e": "bidi mark (LRM)", "\u200f": "bidi mark (RLM)", "\u061c": "bidi mark (ALM)",
    **{chr(c): "bidi control" for c in range(0x202A, 0x202F)},
    **{chr(c): "bidi isolate" for c in range(0x2066, 0x206A)},
}


def _is_a2(ch):
    o = ord(ch)
    return (o < 0x20 and ch not in "\t\n") or 0x7F <= o <= 0x9F


# A3: UTF-8 bytes shown as cp1252/latin-1, e.g. "â€™", "Ã¤", "à¤¹". A
# continuation byte 0x80-0xBF appears as its cp1252 char (or raw latin-1 for
# the bytes cp1252 leaves undefined).
def _cp1252_char(b):
    try:
        return bytes([b]).decode("cp1252")
    except UnicodeDecodeError:
        return bytes([b]).decode("latin-1")


_BYTE_OF = {_cp1252_char(b): b for b in range(0x80, 0x100)}
_CONT = "[" + "".join(sorted({_cp1252_char(b) for b in range(0x80, 0xC0)}
                             | {chr(b) for b in range(0x80, 0xC0)})) + "]"
MOJIBAKE_RE = re.compile(
    "(?:[\u00c2-\u00df]" + _CONT + "|[\u00e0-\u00ef]" + _CONT + "{2}"
    "|[\u00f0-\u00f4]" + _CONT + "{3})+")


def _unmojibake(s):
    """Return the intended text if s is UTF-8 decoded as cp1252, else None."""
    try:
        return bytes(_BYTE_OF.get(c, ord(c)) for c in s).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


_HTML_TAGS = (
    "a|abbr|article|aside|audio|b|blockquote|body|br|button|center|code|div|em|"
    "figcaption|figure|font|footer|form|h[1-6]|head|header|hr|html|i|iframe|img|"
    "input|label|li|link|main|meta|nav|noscript|ol|option|p|path|pre|script|"
    "section|select|small|source|span|strong|style|sub|sup|svg|table|tbody|td|"
    "th|thead|title|tr|u|ul|video")

# (code, regex, label). B3 first: it is the most dangerous disease.
PATTERNS = [
    ("B3", re.compile(r"<\|[A-Za-z0-9_.\- ]{1,40}\|>"), "ghost special token"),
    ("B3", re.compile(r"\[/?INST\]|<</?SYS>>"), "ghost chat marker"),
    ("B3", re.compile(r"</?s>"), "ghost BOS/EOS marker <s>"),
    ("B3", re.compile(r"</?think(?:ing)?>"), "ghost reasoning tag"),
    ("B3", re.compile(r"<(?:bos|eos|unk|pad|mask|start_of_turn|end_of_turn)>"
                      r"|\[(?:CLS|SEP|MASK|PAD|UNK)\]"), "ghost special token"),
    ("B3", re.compile(r"(?mi)^[ \t]*#{1,4}[ \t]*(?:assistant|user|human|system|"
                      r"instruction|response)[ \t]*:"), "ghost role header"),
    ("B3", re.compile(r"(?m)^[ \t]*(?:Human|Assistant)[ \t]*:"), "ghost role prefix"),
    ("B2", re.compile(r"<!--.{0,500}?-->|<!DOCTYPE[^>]{0,200}>|<\?xml[^>]{0,200}\?>",
                      re.S | re.I), "HTML/XML comment or declaration"),
    # attributes must have values, so math like "a<b and c>d" is not a tag
    ("B2", re.compile(r"</?(?:" + _HTML_TAGS + r")(?:\s+[\w:-]+\s*=\s*(?:\"[^\"<>]*\"|'[^'<>]*'|[^\s<>]+))*"
                      r"\s*/?>", re.I), "HTML tag"),
    ("B1", re.compile(r"&(?:#\d{1,7};?|#[xX][0-9A-Fa-f]{1,6};?|[A-Za-z][A-Za-z0-9]{1,31};"
                      r"|(?:nbsp|amp|lt|gt|quot|apos)\b)"), "HTML entity"),
    ("B4", re.compile(r"\{\{.{0,200}?\}\}|\{%.{0,200}?%\}"), "template placeholder"),
    ("B4", re.compile(r"\$\{[^}\n]{0,100}\}"), "template placeholder ${...}"),
    ("B4", re.compile(r"\b(?:undefined|NaN)\b|\[object Object\]"), "code junk value"),
]

# lang_label script suffix (e.g. kan_Knda) -> Unicode name prefix
SCRIPT_OF_LABEL = {
    "Knda": "KANNADA", "Deva": "DEVANAGARI", "Beng": "BENGALI", "Taml": "TAMIL",
    "Telu": "TELUGU", "Mlym": "MALAYALAM", "Gujr": "GUJARATI", "Guru": "GURMUKHI",
    "Orya": "ORIYA", "Latn": "LATIN", "Arab": "ARABIC", "Cyrl": "CYRILLIC",
}
# A code's priority when findings overlap: earlier wins the highlight.
PRIORITY = ["B3", "A4", "A1", "A3", "A2", "B5", "B2", "B1", "B4", "A5", "A6"]


def _script(ch):
    """Unicode script name prefix for a letter or mark, else None."""
    cat = unicodedata.category(ch)
    if cat[0] not in "LM" or cat == "Lm":   # Lm: modifier letters act like punctuation
        return None
    first = unicodedata.name(ch, "").split(" ")[0]
    return None if first in ("", "COMBINING") else first


def _char_runs(text, classify):
    """Yield (start, end, label) for runs of consecutive chars with the same label."""
    start, label = None, None
    for i, ch in enumerate(text):
        lab = classify(ch)
        if lab != label:
            if label is not None:
                yield start, i, label
            start, label = i, lab
    if label is not None:
        yield start, len(text), label


def _unclosed_latex(text):
    """B5: \\cmd{ whose brace never closes (any of its {..}{..} arguments),
    \\begin{env} with no \\end{env}, odd $$."""
    out = []
    for m in re.finditer(r"\\[A-Za-z]+\s*\{", text):
        depth, j = 1, m.end()
        while j < len(text) and depth:
            if text[j] == "\\":
                j += 2
                continue
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
            if depth == 0 and j < len(text) and text[j] == "{":   # next argument group
                depth, j = 1, j + 1
        if depth:
            out.append((m.start(), m.end(), "unclosed " + m.group(0).strip()))
    for env in set(re.findall(r"\\begin\{([^}\n]{1,40})\}", text)):
        begins = list(re.finditer(r"\\begin\{" + re.escape(env) + r"\}", text))
        extra = len(begins) - len(re.findall(r"\\end\{" + re.escape(env) + r"\}", text))
        for m in begins[len(begins) - extra:] if extra > 0 else []:
            out.append((m.start(), m.end(), f"\\begin{{{env}}} with no \\end"))
    dd = [m.start() for m in re.finditer(r"\$\$", text)]
    if len(dd) % 2:
        out.append((dd[-1], dd[-1] + 2, "unpaired $$"))
    return out


def _unclosed_fence(text):
    """B5: a ``` / ~~~ code fence that is opened but never closed."""
    open_at = None
    for m in re.finditer(r"(?m)^[ \t]*(```|~~~)", text):
        open_at = None if open_at is not None else (m.start(1), m.end(1))
    return [(*open_at, "unclosed code fence")] if open_at else []


def _hex(s, cap=64):
    cps = [f"U+{ord(c):04X}" for c in s[:cap]]
    return " ".join(cps) + (" …" if len(s) > cap else "")


def detect(text, lang_label=""):
    """Find section A/B disease candidates in text.

    Returns (findings, marks): findings is a list of
    {code, start, end, label, evidence, hex} sorted by offset (hex only for the
    A group, as the label sheet asks); marks is a per-character list holding the
    finding that highlights that character (or None).
    """
    raw = []
    for s, e, lab in _char_runs(text, lambda ch: A1_CHARS.get(ch)):
        raw.append(("A1", s, e, lab))
    for s, e, lab in _char_runs(text, lambda ch: "control character" if _is_a2(ch) else None):
        raw.append(("A2", s, e, lab))
    for s, e, lab in _char_runs(text, lambda ch: "replacement character" if ch == "\ufffd" else None):
        raw.append(("A4", s, e, f"{lab} x{e - s}" if e - s > 1 else lab))
    for m in MOJIBAKE_RE.finditer(text):
        fixed = _unmojibake(m.group(0))
        if fixed is not None:
            raw.append(("A3", m.start(), m.end(), f"mojibake, should be {fixed!r}"))
    for code, rx, lab in PATTERNS:
        for m in rx.finditer(text):
            raw.append((code, m.start(), m.end(), lab))
    for s, e, lab in _unclosed_fence(text) + _unclosed_latex(text):
        raw.append(("B5", s, e, lab))

    expected = SCRIPT_OF_LABEL.get(lang_label.rpartition("_")[2])
    nfc_ok = unicodedata.is_normalized("NFC", text)
    if not nfc_ok:
        for m in re.finditer(r"\S+", text):
            tok = m.group(0)
            if not unicodedata.is_normalized("NFC", tok):
                raw.append(("A5", m.start(), m.end(),
                            f"not NFC; NFC form is {unicodedata.normalize('NFC', tok)!r}"))
    # A6 words: runs of letters/marks (ZWJ/ZWNJ included), so punctuation splits words
    is_wordch = lambda ch: "w" if ch in "\u200c\u200d" or _script(ch) else None
    for s, e, _ in _char_runs(text, is_wordch):
        scripts = {sc for sc in map(_script, text[s:e]) if sc}
        if len(scripts) > 1:
            raw.append(("A6", s, e, "mixed scripts in one word: " + "+".join(sorted(scripts))))
        elif expected and scripts and scripts - {expected, "LATIN"}:
            raw.append(("A6", s, e, f"{scripts.pop()} word in {lang_label} text"))

    # keep a finding unless higher-priority findings already cover all of it
    raw.sort(key=lambda f: (PRIORITY.index(f[0]), f[1]))
    marks = [None] * len(text)
    findings = []
    for code, s, e, lab in raw:
        if all(marks[i] is not None for i in range(s, e)):
            continue
        seg = text[s:e]
        ev = show(seg)
        f = {
            "code": code, "start": s, "end": e, "label": lab,
            "evidence": (ev if len(ev) <= 60 else ev[:57] + "…") + f" at offset {s}",
            "hex": _hex(seg) if code.startswith("A") else "",
        }
        findings.append(f)
        for i in range(s, e):
            if marks[i] is None:
                marks[i] = f
    findings.sort(key=lambda f: (f["start"], PRIORITY.index(f["code"])))
    return findings, marks


# ---------------------------------------------------------------------------
# Server.
# ---------------------------------------------------------------------------
def text_diff(before, after):
    """Return removed/added ranges in each text's Python code-point offsets.

    Match complete lines first, refining small replacements by character.
    Bound character matching work for large/repetitive replacement blocks;
    those blocks are highlighted in full, as in a coarse split diff.
    """
    result = {"removed": [], "added": [], "coarse": False}
    if before == after:
        return result
    prefix = 0
    while prefix < min(len(before), len(after)) and before[prefix] == after[prefix]:
        prefix += 1
    end_before, end_after = len(before), len(after)
    while (end_before > prefix and end_after > prefix
           and before[end_before - 1] == after[end_after - 1]):
        end_before -= 1
        end_after -= 1
    left = before[prefix:end_before].splitlines(keepends=True)
    right = after[prefix:end_after].splitlines(keepends=True)

    def offsets(lines):
        out = [prefix]
        for line in lines:
            out.append(out[-1] + len(line))
        return out

    left_offsets, right_offsets = offsets(left), offsets(right)

    def add(kind, start, end):
        if start == end:
            return
        ranges = result[kind]
        if ranges and ranges[-1][1] == start:
            ranges[-1][1] = end
        else:
            ranges.append([start, end])

    for tag, i, j, k, l in SequenceMatcher(None, left, right).get_opcodes():
        if tag == "equal":
            continue
        start_a, end_a = left_offsets[i], left_offsets[j]
        start_b, end_b = right_offsets[k], right_offsets[l]
        if tag == "replace" and (end_a - start_a) * (end_b - start_b) <= 1_000_000:
            for change, a, b, c, d in SequenceMatcher(
                    None, before[start_a:end_a], after[start_b:end_b], autojunk=False).get_opcodes():
                if change != "equal":
                    add("removed", start_a + a, start_a + b)
                    add("added", start_b + c, start_b + d)
        else:
            result["coarse"] |= tag == "replace"
            add("removed", start_a, end_a)
            add("added", start_b, end_b)
    return result


def diff_segments(segs, ranges, kind):
    """Split display runs at diff boundaries without changing text or offsets."""
    if not ranges:
        return segs
    out, change = [], 0
    for seg in segs:
        start = pos = seg["off"]
        end = start + (1 if seg["t"] == "tok" else len(seg["s"]))
        while pos < end:
            while change < len(ranges) and ranges[change][1] <= pos:
                change += 1
            changed = change < len(ranges) and ranges[change][0] <= pos
            stop = min(end, ranges[change][1] if changed else
                       ranges[change][0] if change < len(ranges) else end)
            part = dict(seg, off=pos)
            if seg["t"] == "text":
                part["s"] = seg["s"][pos - start:stop - start]
            if changed:
                part["diff"] = kind
            out.append(part)
            pos = stop
    return out


class State:
    docs = []          # list of row dicts
    out_path = None    # CSV save path (default labels.csv in CWD)
    doc_index = {}     # doc_id -> pack position, for stable CSV ordering
    comparison = None  # optional doc_id -> secondary row; never drives navigation
    primary_name = ""
    comparison_name = ""
    total_docs = 0  # primary rows before any --changed-only filtering


def read_pack(path):
    """Validate audit keys before constructing an unambiguous left join."""
    table = pq.read_table(path)
    missing = {"doc_id", "text"} - set(table.column_names)
    if missing:
        raise ValueError(f"{path}: missing required columns: {', '.join(sorted(missing))}")
    docs, seen = table.to_pylist(), set()
    for i, d in enumerate(docs):
        did = d["doc_id"]
        if not isinstance(did, str) or not did.strip():
            raise ValueError(f"{path}: row {i + 1} needs a nonempty string doc_id")
        if did in seen:
            raise ValueError(f"{path}: duplicate doc_id {did!r}")
        seen.add(did)
        if d["text"] is not None and not isinstance(d["text"], str):
            raise ValueError(f"{path}: row {i + 1} text must be a string or null")
    return docs


class NoChangedDocs(ValueError):
    """changed_only was asked for, but every primary document is unchanged."""


def load_packs(primary_path, comparison_path=None, changed_only=False):
    """Keep primary order/count intact, including rows missing from secondary.

    With changed_only (requires a comparison pack), drop primary rows whose
    text is byte-identical in the comparison pack. Rows missing from the
    comparison pack are kept (they count as changed).
    """
    docs = read_pack(primary_path)
    if not docs:
        raise ValueError(f"{primary_path}: primary pack is empty")
    comparison = None
    State.total_docs = len(docs)
    if comparison_path is not None:
        comparison = {d["doc_id"]: d for d in read_pack(comparison_path)}
        if changed_only:
            docs = [d for d in docs
                    if d["doc_id"] not in comparison
                    or (comparison[d["doc_id"]]["text"] or "") != (d["text"] or "")]
            if not docs:
                raise NoChangedDocs(
                    f"all {State.total_docs} documents in {primary_path} are unchanged in "
                    f"{comparison_path}; nothing to show with --changed-only")
    elif changed_only:
        raise ValueError("--changed-only needs a comparison pack")
    State.docs = docs
    State.doc_index = {d["doc_id"]: i for i, d in enumerate(docs)}
    State.comparison = comparison
    State.primary_name = os.path.basename(primary_path)
    State.comparison_name = os.path.basename(comparison_path) if comparison_path else ""


def document_payload(d):
    text = d.get("text", "") or ""
    findings, marks = detect(text, d.get("lang_label", "") or "")
    return {
        "doc_id": d.get("doc_id", ""),
        "source": d.get("source", ""),
        "lang_label": d.get("lang_label", ""),
        "url": d.get("url", "") or "",
        "chars": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "raw_text": text,
        "segments": segments(text, marks),
        "hexdump": hexdump_rows(text),
        "dx_counts": dict(Counter(f["code"] for f in findings)),
        "findings": findings[:MAX_FINDINGS],
    }


def doc_payload(i: int):
    d = State.docs[i]
    payload = document_payload(d)
    payload.update(i=i, count=len(State.docs))
    if State.comparison is not None:
        other = State.comparison.get(d["doc_id"])
        comparison = document_payload(other) if other is not None else None
        differences = None
        if comparison is not None:
            differences = text_diff(payload["raw_text"], comparison["raw_text"])
            payload["segments"] = diff_segments(payload["segments"], differences["removed"], "removed")
            comparison["segments"] = diff_segments(comparison["segments"], differences["added"], "added")
        payload.update(
            primary_name=State.primary_name,
            comparison_name=State.comparison_name,
            comparison=comparison,
            diff=differences,
        )
    return payload


MAX_FINDINGS = 1000  # rows sent to the browser per document; counts are always complete


FIELDNAMES = ["doc_id", "read", "verdict", "diseases", "evidence", "hex", "note"]


def rows_to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDNAMES, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: (r.get(k, "") or "") for k in FIELDNAMES})
    return buf.getvalue()


def read_csv_rows(path):
    """Read labels.csv into {doc_id: rowdict}. Missing/empty file -> {}."""
    if not path or not os.path.exists(path):
        return {}
    out = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            did = (row.get("doc_id") or "").strip()
            if did:
                out[did] = {k: (row.get(k, "") or "") for k in FIELDNAMES}
    return out


def ordered_rows(rowmap):
    """Rows sorted by pack position; unknown doc_ids go last, stable."""
    def key(did):
        return (0, State.doc_index[did]) if did in State.doc_index else (1, 0)
    return [rowmap[d] for d in sorted(rowmap, key=lambda d: key(d))]


SAVE_LOCK = threading.Lock()


@contextmanager
def csv_write_lock(path):
    """Serialize threads and cooperating processes using a stable sidecar file."""
    with SAVE_LOCK, open(path + ".lock", "a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if os.fstat(lock.fileno()).st_size == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def merge_save(incoming, include_rows=False):
    """Upsert incoming rows into the on-disk CSV by doc_id; a row whose fields
    are all empty removes that doc_id. Rows not sent are never touched.

    Re-reads the current file so rows the browser never touched are preserved.
    Returns (abs_path, total_rows).
    """
    if not isinstance(incoming, list) or any(
        not isinstance(r, dict) or not isinstance(r.get("doc_id"), str)
        or not r["doc_id"].strip()
        or any(not isinstance(r.get(k, ""), str) for k in FIELDNAMES)
        for r in incoming
    ):
        raise ValueError("rows must be a list of annotation objects with string fields and nonempty doc_id")
    path = os.path.realpath(State.out_path)
    with csv_write_lock(path):
        disk = read_csv_rows(path)
        for r in incoming:
            did = r["doc_id"].strip()
            row = {k: r.get(k, "") for k in FIELDNAMES}
            if any(row[k] for k in FIELDNAMES if k != "doc_id"):
                disk[did] = row
            else:
                disk.pop(did, None)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                             dir=os.path.dirname(path), delete=False) as f:
                temporary = f.name
                if os.path.exists(path):
                    os.chmod(temporary, os.stat(path).st_mode & 0o777)
                f.write(rows_to_csv(ordered_rows(disk)))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    result = (path, len(disk))
    return (*result, disk) if include_rows else result


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quieter console
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def do_GET(self):
        path, _, query = self.path.partition("?")
        params = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}
        if path == "/":
            self._send(200, PAGE, "text/html; charset=utf-8")
        elif path == "/api/count":
            self._json({"count": len(State.docs)})
        elif path == "/api/rows":
            # current on-disk labels.csv, keyed by doc_id (source of truth)
            self._json({"rows": read_csv_rows(State.out_path)})
        elif path == "/api/hex":
            try:
                i = int(params.get("i", "0"))
                offset = int(params["offset"]) if "offset" in params else None
            except ValueError:
                return self._json({"error": "bad index or offset"}, 400)
            if not (0 <= i < len(State.docs)):
                return self._json({"error": "out of range"}, 404)
            side = params.get("side", "primary")
            if side not in ("primary", "comparison"):
                return self._json({"error": "bad document side"}, 400)
            doc = State.docs[i]
            if side == "comparison":
                doc = State.comparison.get(doc["doc_id"]) if State.comparison is not None else None
            if doc is None:
                return self._json({"error": "no matching comparison document"}, 404)
            self._json(dict(hexdump_window(doc.get("text") or "", offset), i=i, side=side))
        elif path == "/api/doc":
            if "doc_id" in params:
                i = State.doc_index.get(params["doc_id"])
                if i is None:
                    return self._json({"error": "doc_id not found in primary pack"}, 404)
                return self._json(doc_payload(i))
            try:
                i = int(params.get("i", "0"))
            except ValueError:
                return self._json({"error": "bad index"}, 400)
            if not (0 <= i < len(State.docs)):
                return self._json({"error": "out of range"}, 404)
            self._json(doc_payload(i))
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        path, _, _ = self.path.partition("?")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 <= length <= 16 * 1024 * 1024:
                raise ValueError("invalid request length")
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
            if not isinstance(data, dict):
                raise ValueError("expected an object")
        except (ValueError, UnicodeDecodeError):
            return self._json({"error": "bad json"}, 400)
        if path in ("/api/save", "/api/export"):
            rows = data.get("rows", [])
            try:
                saved_path, total, baseline = merge_save(rows, include_rows=True)
            except ValueError as exc:
                return self._json({"error": str(exc)}, 400)
            except OSError:
                return self._json({"error": "Could not write labels CSV; browser drafts are retained"}, 500)
            self._json({"saved": saved_path, "rows": total, "baseline": baseline})
        else:
            self._json({"error": "not found"}, 404)


def main():
    ap = argparse.ArgumentParser(
        description="Inspect a Parquet pack, optionally comparing a second pack by doc_id.")
    ap.add_argument("pack", help="Primary Parquet pack (controls navigation and annotations)")
    ap.add_argument("comparison_pack", nargs="?",
                    help="Optional post-cleaning pack, left-joined to the primary by doc_id")
    ap.add_argument("--changed-only", action="store_true",
                    help="With a comparison pack, show only documents whose text changed "
                         "(or that are missing from the comparison pack)")
    ap.add_argument("--random", action="store_true",
                    help="'next' jumps to a random unvisited document; 'back' retraces visited ones")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1",
                    help="Bind address (default: 127.0.0.1; use 0.0.0.0 for LAN access)")
    ap.add_argument("--out", default="labels.csv",
                    help="CSV save path (default: labels.csv in the current directory)")
    a = ap.parse_args()

    try:
        load_packs(a.pack, a.comparison_pack, a.changed_only)
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    State.out_path = a.out
    start = max(0, min(a.start, len(State.docs) - 1)) if State.docs else 0

    global PAGE
    # Keep unsaved annotations from different packs/output files separate.
    storage_id = hashlib.sha256(json.dumps([
        os.path.realpath(a.pack), os.path.realpath(a.out),
    ]).encode("utf-8")).hexdigest()
    PAGE = (PAGE.replace("__START__", str(start))
            .replace("__VISIBLE__", json.dumps(VISIBLE))
            .replace("__STORAGE_ID__", storage_id)
            .replace("__RANDOM_NAV__", "true" if a.random else "false"))

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    shown_host = "127.0.0.1" if a.host == "0.0.0.0" else a.host
    url = f"http://{shown_host}:{a.port}"
    print(f"Loaded {len(State.docs)} documents from {a.pack}")
    if a.changed_only:
        print(f"--changed-only: showing {len(State.docs)} changed of {State.total_docs} "
              f"({State.total_docs - len(State.docs)} unchanged hidden)")
    if State.comparison is not None:
        matched = sum(d["doc_id"] in State.comparison for d in State.docs)
        print(f"Comparison: {a.comparison_pack}; {matched}/{len(State.docs)} primary IDs matched")
    print(f"Serving on {a.host}:{a.port}  ->  open {url}  (Ctrl-C to stop)")
    if State.out_path:
        print(f"Save button writes: {os.path.abspath(State.out_path)}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        srv.server_close()


# ---------------------------------------------------------------------------
# Frontend (single inlined page, offline, no external assets).
# ---------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pack viewer</title>
<style>
  :root { --bg:#1e1e1e; --panel:#252526; --fg:#d4d4d4; --muted:#888;
          --accent:#4ec9b0; --tok:#f0a500; --tokbg:#4a3a00; --border:#3a3a3a; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, sans-serif; background:var(--bg);
         color:var(--fg); font-size:14px; }
  header { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
           padding:8px 12px; background:var(--panel);
           border-bottom:1px solid var(--border); position:sticky; top:0; z-index:5; }
  header .meta { color:var(--muted); font-size:12px; }
  button, input, select, textarea { font-family:inherit; font-size:13px; }
  button { background:#333; color:var(--fg); border:1px solid var(--border);
           border-radius:4px; padding:4px 10px; cursor:pointer; }
  button:hover { background:#3d3d3d; }
  button:disabled { opacity:.5; cursor:default; }
  button.active { background:var(--accent); color:#000; }
  #exportBtn.unsaved { background:#d18616; color:#000; border-color:#d18616; font-weight:bold; }
  #exportBtn.unsaved:hover { background:#e89a2a; }
  #exportBtn.clean { background:#2a2a2a; color:var(--muted); }
  .wrap { display:flex; height:calc(100vh - 100px); }
  .left { flex:1 1 60%; overflow:auto; padding:12px; }
  .doc-pane { min-width:0; }
  .doc-body { min-width:0; min-height:0; }
  /* Shared grid rows give both headers the same height, even if one wraps or
     includes a warning. The document bodies always start on the same baseline. */
  .left.comparing { display:grid; grid-template-columns:repeat(2,minmax(0,1fr));
                    grid-template-rows:auto minmax(0,1fr); gap:8px 12px;
                    overflow:hidden; min-width:0; }
  .comparing .doc-pane { display:contents; }
  .comparing .doc-header { grid-row:1; min-width:0; }
  .comparing .doc-body { grid-row:2; overflow:auto; }
  .comparing #primaryHeader, .comparing #primaryBody { grid-column:1; }
  .comparing #comparisonHeader, .comparing #comparisonBody { grid-column:2;
                    border-left:1px solid var(--border); padding-left:12px; }
  .pane-title { margin-top:0; color:var(--accent); overflow-wrap:anywhere; }
  .pane-meta { color:var(--muted); font-size:12px; margin-bottom:8px; overflow-wrap:anywhere; }
  .doc-hash { font:11px/1.5 monospace; color:var(--muted); overflow-wrap:anywhere;
              margin-bottom:8px; user-select:all; }
  #comparisonMessage { padding:10px; border:1px solid var(--border); }
  .right { flex:0 0 360px; overflow:auto; padding:12px; background:var(--panel);
           border-left:1px solid var(--border); }
  .diagnostic { white-space:pre-wrap; word-break:break-word; line-height:1.55;
          font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
          font-size:13px; }
  .diagnostic span { background:var(--diff-bg,var(--dx-bg,var(--token-bg,transparent))); }
  .tok { color:var(--tok); background:var(--tokbg); border-radius:3px;
         --token-bg:var(--tokbg); padding:0 2px; cursor:help; }
  /* disease highlights: A = characters (orange), B = markup (purple), B3 = ghost markers (red) */
  .dx { border-bottom:2px solid; cursor:pointer; }
  .dxA { background:rgba(255,165,0,.22); --dx-bg:rgba(255,165,0,.22); border-color:#ffa500; }
  .dxB { background:rgba(170,120,255,.25); --dx-bg:rgba(170,120,255,.25); border-color:#aa78ff; }
  .dxB3 { background:rgba(255,70,70,.45); --dx-bg:rgba(255,70,70,.45); border-color:#ff4646; font-weight:bold; }
  .diagnostic.nohl .dx { --dx-bg:var(--token-bg,transparent); border-bottom:none; font-weight:inherit; }
  .diff-removed { --diff-bg:#672c32; }
  .diff-added { --diff-bg:#174f32; }
  .diff-newline::before { content:"↵"; }
  .diagnostic.no-diff .diff-newline::before { content:none; }
  .diagnostic.no-diff .diff-removed, .diagnostic.no-diff .diff-added {
    --diff-bg:var(--dx-bg,var(--token-bg,transparent)); }
  #diffLegend { color:var(--muted); font-size:12px; }
  #diffLegend span { padding:2px 5px; border-radius:3px; color:var(--fg); }
  #diffLegend .diff-removed { background:#672c32; }
  #diffLegend .diff-added { background:#174f32; }
  #dxBanner { display:none; background:#5a1a1a; color:#ffd0d0; padding:6px 10px;
              border-radius:4px; margin-bottom:8px; font-size:12px; }
  #dxList { max-height:280px; overflow:auto; font-size:12px; }
  .dxrow { display:flex; gap:6px; align-items:baseline; padding:3px 2px; cursor:pointer;
           border-bottom:1px solid #2c2c2c; }
  .dxrow:hover { background:#2d2d2d; }
  .dxrow.added { opacity:.5; }
  .dxrow .dxev { font-family:monospace; word-break:break-all; }
  .dxrow small { color:var(--muted); }
  .dxc { font-family:monospace; padding:0 3px; border-radius:3px; border-bottom:none; }
  .dxadd { padding:0 7px; }
  .chip { display:inline-block; margin:0 4px 4px 0; padding:1px 7px; border-radius:10px;
          font-size:11px; cursor:pointer; border:1px solid var(--border); }
  .chip.on { outline:1px solid var(--accent); }
  .preview { line-height:1.6; max-width:52em; overflow-wrap:anywhere; }
  .preview pre { background:#111; padding:10px; overflow:auto; border-radius:4px; }
  .preview code { background:#111; padding:1px 4px; border-radius:3px; }
  .preview table { border-collapse:collapse; } .preview td,.preview th { border:1px solid var(--border); padding:4px 8px; }
  .preview blockquote { border-left:3px solid var(--border); margin:0; padding-left:10px; color:var(--muted); }
  footer { position:sticky; bottom:0; background:var(--panel);
           border-top:1px solid var(--border); padding:6px 12px; font-size:12px;
           display:flex; gap:16px; align-items:center; z-index:5; }
  .status b { color:var(--accent); }
  .hexrow { font-family:monospace; font-size:12px; white-space:pre; }
  .hexrow.hex-selected { background:#254b43; color:#fff; font-weight:bold; }
  .field { margin-bottom:8px; }
  .field label { display:block; color:var(--muted); font-size:11px;
                 text-transform:uppercase; letter-spacing:.04em; margin-bottom:2px; }
  .field input, .field textarea, .field select { width:100%; background:#1b1b1b;
     color:var(--fg); border:1px solid var(--border); border-radius:4px; padding:5px; }
  .field textarea { resize:vertical; min-height:38px; }
  .row-actions { display:flex; gap:8px; margin:8px 0; }
  #dxPicked { width:100%; background:#1b1b1b; color:var(--accent); border:1px solid var(--border);
              border-radius:4px; padding:5px; font-family:monospace; }
  .dxsections { border:1px solid var(--border); border-radius:4px; margin-top:4px; }
  details.dxsec { border-bottom:1px solid var(--border); }
  details.dxsec:last-child { border-bottom:none; }
  details.dxsec > summary { cursor:pointer; padding:5px 8px; font-size:12px; color:var(--fg);
                            list-style:none; user-select:none; background:#1b1b1b; }
  details.dxsec > summary::-webkit-details-marker { display:none; }
  details.dxsec > summary:hover { background:#262626; }
  details.dxsec[open] > summary { color:var(--accent); }
  .dxitems { padding:4px 8px 6px; }
  .dxitem { display:flex; align-items:flex-start; gap:6px; padding:2px 0; font-size:12px; }
  .dxitem input { width:auto; margin-top:2px; }
  .dxitem .code { color:var(--tok); font-family:monospace; min-width:26px; }
  .dxitem .desc { color:var(--fg); }
  .dxitem .desc small { color:var(--muted); }
  h3 { margin:14px 0 6px; font-size:12px; color:var(--muted);
       text-transform:uppercase; letter-spacing:.05em; }
  .hint { color:var(--muted); font-size:11px; margin-top:2px; }
  .warn { color:#e0a0a0; font-size:11px; }
  #exportBox { width:100%; height:120px; background:#111; color:var(--fg);
               border:1px solid var(--border); font-family:monospace; font-size:11px; }
  .saved { color:var(--accent); }
</style>
</head>
<body>
<header>
  <button id="prev">◀ back</button>
  <button id="next">next ▶</button>
  <span>#<input id="jump" type="number" min="1" style="width:70px"> </span>
  <input id="jumpId" placeholder="jump to doc_id" style="width:160px">
  <button id="goId">go</button>
  <button id="toggleMd">markdown preview</button>
  <button id="toggleHex" class="active">hex dump</button>
  <button id="toggleDx" class="active">highlights</button>
  <button id="toggleDiff" class="active" hidden>differences</button>
  <span id="diffLegend" hidden><span class="diff-removed">− removed</span>
    <span class="diff-added">+ added</span></span>
  <span class="meta" id="meta"></span>
</header>

<div class="wrap">
  <div class="left" id="docPanes">
    <section class="doc-pane" aria-label="Primary document">
      <div id="primaryHeader" class="doc-header">
        <h3 id="primaryTitle" class="pane-title" hidden></h3>
        <div id="primaryHash" class="doc-hash" aria-label="Primary text SHA-256"></div>
        <div id="dxBanner"></div>
      </div>
      <div id="primaryBody" class="doc-body">
        <div id="diag" class="diagnostic" tabindex="0" aria-label="Primary diagnostic text"></div>
        <div id="md" class="preview" style="display:none"></div>
      </div>
    </section>
    <section id="comparisonPane" class="doc-pane" aria-label="Comparison document" hidden>
      <div id="comparisonHeader" class="doc-header">
        <h3 id="comparisonTitle" class="pane-title"></h3>
        <div id="comparisonHash" class="doc-hash" aria-label="Comparison text SHA-256"></div>
        <div id="comparisonMeta" class="pane-meta"></div>
        <div id="comparisonMessage" role="status" hidden></div>
      </div>
      <div id="comparisonBody" class="doc-body">
        <div id="comparisonDiag" class="diagnostic" tabindex="0" aria-label="Comparison diagnostic text"></div>
        <div id="comparisonMd" class="preview" style="display:none"></div>
      </div>
    </section>
  </div>
  <div class="right">
    <h3>Annotation (this document)</h3>
    <div class="field"><label>doc_id</label><input id="f_doc_id" readonly></div>
    <div class="field"><label>read</label>
      <select id="f_read"><option value=""></option><option>full</option><option>partial</option></select></div>
    <div class="field"><label>verdict</label>
      <select id="f_verdict"><option value=""></option><option>clean</option><option>fix</option><option>drop</option></select></div>
    <div class="field"><label>diseases (tick below &rarr; e.g. A1;B3)</label>
      <input id="f_diseases" placeholder="codes appear here; you can also type">
      <div class="dxsections" id="dxSections"></div></div>
    <div class="field"><label>evidence</label><textarea id="f_evidence"></textarea>
      <div class="hint">Select primary text to auto-fill "chars at offset N". Annotations use primary offsets.</div></div>
    <div class="field"><label>hex (U+XXXX ...)</label><input id="f_hex">
      <div class="warn" id="hexWarn" style="display:none">F1/E3: leave hex empty. Never paste the value.</div></div>
    <div class="field"><label>note</label><input id="f_note"></div>
    <div class="row-actions">
      <button id="clearRow">clear this row</button>
      <span id="rowState" class="hint"></span>
    </div>

    <h3>Save (<span id="savedCount">0</span> rows in file)</h3>
    <div class="row-actions">
      <button id="exportBtn" class="clean">save labels.csv</button>
    </div>
    <textarea id="exportBox" readonly placeholder="current row (CSV) appears here"></textarea>
    <div class="hint" id="exportMsg"></div>

    <h3>Detected A/B candidates <span id="dxTotal"></span></h3>
    <div class="hint" style="margin-bottom:6px">Click a row to select it in the text; + ticks the code and appends evidence (and hex for A).</div>
    <div id="dxCounts"></div>
    <div id="dxList"></div>

    <h3 id="hexHead">Hex dump (first 100 characters)</h3>
    <div id="hexList"></div>
  </div>
</div>

<footer>
  <span class="status" id="status">offset: –</span>
  <span class="status" id="selstatus"></span>
</footer>

<script>
// ---- tiny markdown renderer (bundled JS, no deps) ----
function escapeHtml(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function mdInline(s){
  s = escapeHtml(s);
  s = s.replace(/`([^`]+)`/g,'<code>$1</code>');
  s = s.replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  s = s.replace(/(^|[^*])\*([^*]+)\*/g,'$1<em>$2</em>');
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, label, url)=>
    /^(https?:\/\/|mailto:)/i.test(url)
      ? '<a href="'+url+'" target="_blank" rel="noopener noreferrer">'+label+'</a>'
      : label);
  return s;
}
function renderMarkdown(text){
  const lines = text.split('\n');
  let out = [], i = 0;
  while(i < lines.length){
    let line = lines[i];
    if(/^```/.test(line)){
      let code=[]; i++;
      while(i<lines.length && !/^```/.test(lines[i])){ code.push(lines[i]); i++; }
      i++;
      out.push('<pre><code>'+escapeHtml(code.join('\n'))+'</code></pre>'); continue;
    }
    // [^]* not .*: JS '.' stops at \r / U+2028, so "# x\r" (CRLF files) failed here
    let h = line.match(/^(#{1,6})\s+([^]*)$/);
    if(h){ const n=h[1].length; out.push('<h'+n+'>'+mdInline(h[2])+'</h'+n+'>'); i++; continue; }
    if(/^\s*>/.test(line)){
      let q=[]; while(i<lines.length && /^\s*>/.test(lines[i])){ q.push(lines[i].replace(/^\s*>\s?/,'')); i++; }
      out.push('<blockquote>'+mdInline(q.join('<br>'))+'</blockquote>'); continue;
    }
    if(/^\s*([-*+]|\d+\.)\s+/.test(line)){
      const ordered=/^\s*\d+\./.test(line); let items=[];
      while(i<lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[i])){
        items.push('<li>'+mdInline(lines[i].replace(/^\s*([-*+]|\d+\.)\s+/,''))+'</li>'); i++; }
      out.push((ordered?'<ol>':'<ul>')+items.join('')+(ordered?'</ol>':'</ul>')); continue;
    }
    if(/^\s*\|.*\|\s*$/.test(line) && i+1<lines.length && /^\s*\|[-:\s|]+\|\s*$/.test(lines[i+1])){
      const parse=r=>r.trim().replace(/^\||\|$/g,'').split('|').map(c=>c.trim());
      const head=parse(line); i+=2; let body=[];
      while(i<lines.length && /^\s*\|.*\|\s*$/.test(lines[i])){ body.push(parse(lines[i])); i++; }
      let t='<table><thead><tr>'+head.map(c=>'<th>'+mdInline(c)+'</th>').join('')+'</tr></thead><tbody>';
      t+=body.map(r=>'<tr>'+r.map(c=>'<td>'+mdInline(c)+'</td>').join('')+'</tr>').join('');
      out.push(t+'</tbody></table>'); continue;
    }
    if(line.trim()===''){ i++; continue; }
    let para=[]; while(i<lines.length && lines[i].trim()!=='' && !/^(#{1,6}\s|```|\s*>|\s*([-*+]|\d+\.)\s)/.test(lines[i])){ para.push(lines[i]); i++; }
    if(!para.length){ para.push(lines[i]); i++; }   // always advance: never loop forever on an odd line
    out.push('<p>'+mdInline(para.join(' '))+'</p>');
  }
  return out.join('\n');
}

// ---- state ----
let cur = null;           // current doc payload
let idx = parseInt("__START__",10) || 0;
let loadVersion = 0;      // discard stale responses from rapid navigation/search
let hexVersion = 0;
let hexKey = null;
const VISIBLE = __VISIBLE__;   // same hidden-char tokens as the Python show()
const saved = {};         // doc_id -> row object (what the UI shows)
const clearedRows = new Set();
let saveInFlight = false;
let disk = {};            // doc_id -> row as last read from labels.csv
const LS_KEY = 'view_pack_web_rows:__STORAGE_ID__';
// NOTE: seeding happens in bootstrap(): CSV (source of truth) first, then
// localStorage overlaid on top. localStorage holds ONLY unsaved edits (rows that
// differ from the CSV), and save sends only those rows, so rows changed in
// labels.csv by someone else are never overwritten by a stale browser copy.
const ROW_KEYS = ['doc_id','read','verdict','diseases','evidence','hex','note'];
function sameRow(a, b){ return !!a && !!b && ROW_KEYS.every(k=>(a[k]||'')===(b[k]||'')); }
function isEmptyRow(r){ return ROW_KEYS.every(k=>k==='doc_id' || !(r[k]||'')); }
function dirtyRows(){
  const out = {};
  for(const [k, r] of Object.entries(saved)) if(!sameRow(r, disk[k])) out[k] = r;
  return out;
}
function persistLocal(){
  try { localStorage.setItem(LS_KEY, JSON.stringify(dirtyRows())); } catch(e){}
}

const $ = id => document.getElementById(id);

// ---- disease catalog (verbatim from DISEASES.md) ----
const DISEASES = [
 ["A","Characters",[
   ["A1","invisible junk characters","ZWSP U+200B, BOM U+FEFF, bidi marks, soft hyphen (ZWJ/ZWNJ are NOT diseases in Indic)"],
   ["A2","control characters","U+0000-U+001F except tab/newline, U+007F-U+009F"],
   ["A3","mojibake","UTF-8 decoded twice, e.g. Ã¤ à¤¹ â€™"],
   ["A4","replacement characters","U+FFFD \ufffd ; count them"],
   ["A5","wrong normal form","same word in two byte forms; nukta two ways (we use NFC)"],
   ["A6","wrong or mixed script","Hindi with Latin look-alikes; Bengali word in Assamese letters"]]],
 ["B","Markup and ghost tokens",[
   ["B1","HTML entities","&amp; &nbsp; &#2361;"],
   ["B2","HTML or XML tags","<div> <br/> </p>"],
   ["B3","ghost chat markers","<|im_start|> <|endoftext|> [INST] <s> ### Assistant: <think> (most dangerous)"],
   ["B4","template/code junk in prose","{{ variable }} ${...} undefined NaN"],
   ["B5","broken markdown or LaTeX","unclosed code fence, \\frac{ with no end"]]],
 ["C","Document structure",[
   ["C1","boilerplate","menus, cookie banners, Share on WhatsApp, footer links"],
   ["C2","repeated lines","same line many times in one document"],
   ["C3","truncated document","text stops mid-sentence or mid-code-block"],
   ["C4","two documents joined","two unrelated texts, no boundary"],
   ["C5","lists of keywords or links","SEO spam, tag clouds"]]],
 ["D","Language",[
   ["D1","wrong language label","label says Marathi, text is Hindi"],
   ["D2","romanised Indic","Hindi written in Latin letters"],
   ["D3","mixed language","Hindi + English in one sentence (can be natural; label, do not judge)"],
   ["D4","bad machine translation","wrong meaning, broken grammar, untranslated words"],
   ["D5","translationese","grammatical, but no native speaker writes like this"]]],
 ["E","Code",[
   ["E1","minified or generated code","one very long line; auto-generated do not edit"],
   ["E2","data blobs","base64, long number arrays, embedded images"],
   ["E3","secrets","API keys, passwords, tokens, private keys (hex empty, position only)"],
   ["E4","repeated licence headers","same 30-line licence at top of many files"],
   ["E5","broken encoding in code","mojibake inside strings or comments"],
   ["E6","not code","README, log file or CSV labelled as code"]]],
 ["F","Safety, privacy and contamination",[
   ["F1","personal data","emails, phones, addresses, IDs of private people (hex empty, position only)"],
   ["F2","benchmark leak","a question/solution from a benchmark test set"],
   ["F3","harmful content","content we must not train on"]]],
 ["G","Damage from earlier cleaning",[
   ["G1","cut at the vowel sign","word split before a matra or virama, e.g. \u0915 \u093f"],
   ["G2","lost ZWJ or ZWNJ","a conjunct that renders wrong"],
   ["G3","Indic dropped by an English rule","good doc with low quality score; sections missing"],
   ["G4","over-normalised","NFKC changed chars; Indic digits changed to Latin"]]],
 ["H","Duplicates",[
   ["H1","exact duplicate in the pack",""],
   ["H2","near duplicate","same text with small changes"],
   ["H3","same content in another source or language","translation of a doc seen in English"]]],
];
// all catalog codes, to tell ticked codes from typed-in unknown ones
const DX_KNOWN = new Set();
DISEASES.forEach(([,,items])=>items.forEach(([code])=>DX_KNOWN.add(code)));

function buildDiseasePicker(){
  const box = $('dxSections'); box.innerHTML='';
  for(const [sec, title, items] of DISEASES){
    const det=document.createElement('details'); det.className='dxsec';
    const sum=document.createElement('summary'); sum.textContent=sec+'. '+title;
    det.appendChild(sum);
    const wrap=document.createElement('div'); wrap.className='dxitems';
    for(const [code, name, how] of items){
      const row=document.createElement('label'); row.className='dxitem';
      const cb=document.createElement('input'); cb.type='checkbox'; cb.value=code;
      cb.dataset.dx='1'; cb.addEventListener('change', onDxCheck);
      const desc=document.createElement('span'); desc.className='desc';
      desc.innerHTML='<span class="code">'+code+'</span> '+name + (how?' <small>\u2014 '+how.replace(/</g,'&lt;')+'</small>':'');
      row.appendChild(cb); row.appendChild(desc);
      if(how) row.title=how;
      wrap.appendChild(row);
    }
    det.appendChild(wrap); box.appendChild(det);
  }
}
function dxCheckboxes(){ return Array.from($('dxSections').querySelectorAll('input[data-dx]')); }
// checkboxes -> diseases string in the order picked (so it lines up with evidence/hex):
// existing codes keep their place, unticked ones drop out, newly ticked ones go last;
// typed-in unknown codes are preserved
function onDxCheck(){
  const ticked = new Set(dxCheckboxes().filter(c=>c.checked).map(c=>c.value));
  const existing = ($('f_diseases').value||'').split(';').map(s=>s.trim()).filter(Boolean);
  const kept = existing.map(c=>DX_KNOWN.has(c.toUpperCase()) ? c.toUpperCase() : c)
                       .filter(c=>!DX_KNOWN.has(c) || ticked.has(c));
  const all = [...new Set([...kept, ...ticked])];
  $('f_diseases').value = all.join(';');
  updateHexWarn();
  renderRowPreview();
}
// diseases string -> checkbox states (for load / manual typing)
function syncDiseaseChecks(){
  const codes = new Set(($('f_diseases').value||'').toUpperCase().split(';').map(s=>s.trim()).filter(Boolean));
  dxCheckboxes().forEach(c=>{ c.checked = codes.has(c.value); });
}

function cpLen(s){ return Array.from(s).length; }           // code-point length
function cpAt(s, n){ return Array.from(s)[n]; }

// Build diagnostic DOM; each node carries data-off (code-point offset of its
// first char) and data-len (code-point length of its raw content).
function renderDiag(payload, target='diag'){
  const diag = $(target); diag.innerHTML='';
  for(const seg of payload.segments){
    const span=document.createElement('span');
    if(seg.t==='text'){
      span.textContent=seg.s; span.dataset.off=seg.off; span.dataset.len=cpLen(seg.s);
      span.dataset.kind='text';
    } else {
      span.className='tok'; span.textContent=seg.s;
      span.dataset.off=seg.off; span.dataset.len=1; span.dataset.kind='tok';
      span.dataset.raw=seg.raw; span.dataset.cp=seg.cp; span.dataset.name=seg.name;
      span.title=seg.cp+' '+seg.name+'  (offset '+seg.off+')';
    }
    markDx(span, seg);
    if(seg.diff){
      span.classList.add('diff-'+seg.diff);
      if(seg.s==='\n') span.classList.add('diff-newline');
      const label=seg.diff==='removed' ? 'Removed from primary' : 'Added in comparison';
      span.title=label+' (offset '+seg.off+')'+(span.title?' | '+span.title:'');
    }
    diag.appendChild(span);
  }
}

function dxClass(code){ return 'dx'+code[0]+' dx'+code; }
function markDx(span, seg){
  if(!seg.dx) return;
  span.className += ' dx '+dxClass(seg.dx);
  span.title = seg.dx+': '+seg.dxl + (span.title ? '  |  '+span.title : '  (offset '+seg.off+')');
}

// DOM position for a raw code-point offset; isEnd places it just after char off-1.
function domPos(off, isEnd){
  const target = isEnd ? off-1 : off;
  for(const span of $('diag').querySelectorAll('span[data-off]')){
    const o=+span.dataset.off, n=+span.dataset.len;
    if(target>=o && target<o+n){
      const k = target-o + (isEnd?1:0);
      if(span.dataset.kind==='tok') return [span, k];
      return [span.firstChild, Array.from(span.textContent).slice(0,k).join('').length];
    }
  }
  return null;
}
// Select raw range [s,e) in the diagnostic pane, as if the reader had dragged over it.
function selectRange(s, e){
  if($('diag').style.display==='none') $('toggleMd').click();
  const a=domPos(s,false), b=domPos(e,true); if(!a||!b) return;
  const r=document.createRange(); r.setStart(a[0],a[1]); r.setEnd(b[0],b[1]);
  const sel=window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
  (a[0].nodeType===3?a[0].parentElement:a[0]).scrollIntoView({block:'center'});
  onCursor();
}

// ---- detected A/B candidates panel ----
let dxFilter = null;
function markFinding(f){
  const cb = dxCheckboxes().find(c=>c.value===f.code);
  if(cb && !cb.checked){ cb.checked=true; onDxCheck(); }
  appendValue('f_evidence', f.evidence);
  if(f.hex) appendValue('f_hex', f.hex);
  renderRowPreview();
}
function renderFindings(){
  const counts = cur.dx_counts||{}, codes = Object.keys(counts).sort();
  const total = codes.reduce((a,c)=>a+counts[c],0);
  $('dxTotal').textContent = total ? '('+total+')' : '';
  const banner=$('dxBanner');
  banner.style.display = counts.B3 ? 'block' : 'none';
  banner.textContent = counts.B3 ? '\u26a0 B3 ghost chat markers: '+counts.B3+'. Most dangerous disease: a ghost marker teaches the model to write our special tokens as plain text.' : '';
  const cbox=$('dxCounts'); cbox.innerHTML='';
  for(const c of codes){
    const chip=document.createElement('span');
    chip.className='chip '+dxClass(c)+(dxFilter===c?' on':'');
    chip.textContent=c+' \u00d7'+counts[c]; chip.title='show only '+c+' (click again for all)';
    chip.onclick=()=>{ dxFilter = dxFilter===c ? null : c; renderFindings(); };
    cbox.appendChild(chip);
  }
  const list=$('dxList'); list.innerHTML='';
  if(!total){ list.innerHTML='<div class="hint">(none found)</div>'; return; }
  const have = new Set(($('f_evidence').value||'').split('; '));
  for(const f of cur.findings.filter(f=>!dxFilter||f.code===dxFilter)){
    const row=document.createElement('div'); row.className='dxrow'+(have.has(f.evidence)?' added':'');
    const add=document.createElement('button'); add.className='dxadd'; add.textContent='+';
    add.title='tick '+f.code+', append evidence'+(f.hex?' and hex':'');
    add.onclick=ev=>{ ev.stopPropagation(); markFinding(f); row.classList.add('added'); };
    const code=document.createElement('span'); code.className='dxc '+dxClass(f.code); code.textContent=f.code;
    const body=document.createElement('div');
    const evs=document.createElement('span'); evs.className='dxev'; evs.textContent=f.evidence;
    const lab=document.createElement('small'); lab.textContent=f.label;
    body.append(evs, document.createElement('br'), lab);
    row.append(add, code, body);
    row.onclick=()=>selectRange(f.start, f.end);
    list.appendChild(row);
  }
  if(cur.findings.length < total){
    const more=document.createElement('div'); more.className='hint';
    more.textContent='(list shows the first '+cur.findings.length+' of '+total+')';
    list.appendChild(more);
  }
}

// Map a DOM (node, domOffset) to a raw code-point offset in the text.
function rawOffsetOf(node, domOffset){
  let span = node.nodeType===3 ? node.parentElement : node;
  if(!span || span.id==='diag' || span.id==='comparisonDiag'){
    // A cursor between spans follows the previous span's final raw character.
    const el = node.childNodes && node.childNodes[domOffset-1];
    if(el && el.dataset) return parseInt(el.dataset.off)+parseInt(el.dataset.len);
    return domOffset===0 ? 0 : null;
  }
  if(span.dataset.off===undefined) return null;
  const base = parseInt(span.dataset.off);
  if(span.dataset.kind==='tok') return base + (domOffset>0?1:0);
  // Text-node offsets count UTF-16 units; element offsets count child nodes.
  const txt = node.nodeType===3 ? span.textContent.slice(0, domOffset)
    : domOffset>0 ? span.textContent : '';
  return base + cpLen(txt);
}

function describeOffset(off, doc=cur){
  if(off===null || off===undefined || !doc) return 'offset: \u2013';
  const ch = cpAt(doc.raw_text, off);
  if(ch===undefined) return 'offset: '+off+' (end)';
  const cp = ch.codePointAt(0);
  const hex = 'U+'+cp.toString(16).toUpperCase().padStart(4,'0');
  let name=''; // name not shipped per-char; show cp. Tokens carry names via title.
  return 'offset: <b>'+off+'</b> \u00b7 '+hex;
}

function renderHexWindow(data, side){
  const label=side==='comparison' ? 'comparison / post' : 'primary / pre';
  $('hexHead').textContent='Hex dump · '+label+' · ['+data.start+'–'+data.end+') of '+data.chars
    +(data.offset===null ? ' · first 100' : ' · offset '+data.offset);
  const list=$('hexList'); list.innerHTML='';
  if(!data.rows.length){ list.textContent='(empty document)'; return; }
  for(const h of data.rows){
    const row=document.createElement('div');
    const selected=h.offset===data.offset;
    row.className='hexrow'+(selected?' hex-selected':''); row.dataset.off=h.offset;
    row.textContent=(selected?'▶ ':'  ')+String(h.offset).padStart(6)+'  '+h.cp+'  '+h.name;
    list.appendChild(row);
  }
}

async function updateHex(offset=null, side='primary'){
  if(!cur) return;
  const doc=side==='comparison' ? cur.comparison : cur;
  if(!doc) return;
  const key=cur.i+':'+side+':'+offset;
  if(key===hexKey) return;
  hexKey=key;
  const version=++hexVersion;
  if(offset===null){
    renderHexWindow({start:0, end:doc.hexdump.length, offset:null, chars:doc.chars, rows:doc.hexdump}, side);
    return;
  }
  try {
    const res=await fetch('/api/hex?i='+cur.i+'&offset='+offset+'&side='+side);
    if(version!==hexVersion) return;
    if(!res.ok) throw new Error('Could not load hex context');
    const data=await res.json();
    if(version!==hexVersion) return;
    renderHexWindow(data, side);
  } catch(error){
    if(version!==hexVersion) return;
    hexKey=null;
    $('hexList').textContent=error.message;
  }
}

function onCursor(){
  const sel = window.getSelection();
  if(!sel.rangeCount){ return; }
  const r = sel.getRangeAt(0);
  const primary=$('diag').contains(r.startContainer) && $('diag').contains(r.endContainer);
  const comparison=!!cur && !!cur.comparison && $('comparisonDiag').contains(r.startContainer)
    && $('comparisonDiag').contains(r.endContainer);
  if(!cur || (!primary && !comparison)){
    window._selFill=null;
    $('status').textContent='offset: –'; $('selstatus').textContent='';
    return;
  }
  const doc=primary ? cur : cur.comparison;
  const side=primary ? 'primary' : 'comparison';
  const off = rawOffsetOf(r.startContainer, r.startOffset);
  $('status').innerHTML = (primary?'':'comparison · ')+describeOffset(off, doc);
  if(off!==null && Number.isFinite(off)) updateHex(off, side);
  // Inspect secondary code points without filling primary annotation evidence.
  if(!primary){ window._selFill=null; $('selstatus').textContent=''; return; }

  if(!sel.isCollapsed){
    const startOff = rawOffsetOf(r.startContainer, r.startOffset);
    const endOff = rawOffsetOf(r.endContainer, r.endOffset);
    if(startOff!==null && endOff!==null && endOff>startOff){
      const arr = Array.from(cur.raw_text).slice(startOff, endOff);
      const raw = arr.join('');
      const hex = arr.map(c=>'U+'+c.codePointAt(0).toString(16).toUpperCase().padStart(4,'0')).join(' ');
      // visible form of selection for evidence
      const vis = arr.map(c=>{ if(VISIBLE[c]) return VISIBLE[c]; const n=c.codePointAt(0); return (n<32||(n>=127&&n<=159))?('\u27e6U+'+n.toString(16).toUpperCase().padStart(4,'0')+'\u27e7'):c; }).join('');
      $('selstatus').innerHTML = 'selected ['+startOff+'\u2013'+endOff+'] \u00b7 '+hex;
      window._selFill = { evidence: vis+' at offset '+startOff, hex: hex };
    }
  } else {
    $('selstatus').innerHTML=''; window._selFill=null;
    if(off!==null && off!==undefined){
      navigator.clipboard && navigator.clipboard.writeText(String(off)).then(()=>{
        $('status').innerHTML = describeOffset(off) + ' <span class="saved">\u2713 copied</span>';
      }).catch(()=>{});
    }
  }
}

function fillFields(docId){
  const row = saved[docId] || {};
  if(saved[docId] && isEmptyRow(row)) clearedRows.add(docId);
  $('f_doc_id').value = docId;
  $('f_read').value = row.read||'';
  $('f_verdict').value = row.verdict||'';
  $('f_diseases').value = row.diseases||'';
  $('f_evidence').value = row.evidence||'';
  $('f_hex').value = row.hex||'';
  $('f_note').value = row.note||'';
  applySelectDefaults();
  $('rowState').textContent = saved[docId] ? 'saved' : '';
  syncDiseaseChecks();
  updateHexWarn();
  renderRowPreview();
}

function updateHexWarn(){
  const dis=($('f_diseases').value||'').toUpperCase();
  $('hexWarn').style.display = (dis.includes('F1')||dis.includes('E3')) ? 'block':'none';
}

// CSV-quote one field to match Python csv (quote if it has , " or newline; double quotes)
function csvField(s){
  s = (s==null)?'':String(s);
  return /[",\n\r]/.test(s) ? '"'+s.replace(/"/g,'""')+'"' : s;
}
const CSV_HEADER = 'doc_id,read,verdict,diseases,evidence,hex,note';
// read/verdict dropdowns show their first value when the row has none. Such a
// value is only a display default ("auto"): it is not kept in memory or
// localStorage, and reaches labels.csv only when Save is clicked on this doc
// or the row gets a real label (then what is on screen is what is stored).
const SELECT_DEFAULTS = {f_read:'full', f_verdict:'clean'};
function isAuto(id){ return $(id).dataset.auto === '1'; }
function applySelectDefaults(){
  for(const [id, v] of Object.entries(SELECT_DEFAULTS)){
    const el = $(id);
    if(el.value){ delete el.dataset.auto; } else { el.value = v; el.dataset.auto = '1'; }
  }
}
function currentRowValues(withDefaults){
  const r = {
    doc_id: $('f_doc_id').value,
    read: isAuto('f_read') ? '' : $('f_read').value,
    verdict: isAuto('f_verdict') ? '' : $('f_verdict').value,
    diseases: $('f_diseases').value, evidence: $('f_evidence').value,
    hex: $('f_hex').value, note: $('f_note').value,
  };
  if(!isEmptyRow(r)) clearedRows.delete(r.doc_id);
  if((withDefaults && !clearedRows.has(r.doc_id)) || !isEmptyRow(r)){
    if(isAuto('f_read')) r.read = $('f_read').value;
    if(isAuto('f_verdict')) r.verdict = $('f_verdict').value;
  }
  return r;
}
// Live preview of the row being built, in the CSV box below the save button.
// Save button: orange while anything differs from labels.csv (the form on screen
// or rows edited on other documents), grey once everything is saved.
function updateSaveBtn(){
  if(!cur) return;
  const r = currentRowValues(), base = disk[cur.doc_id];
  const curDirty = base ? !sameRow(r, base)
                        : ['read','verdict','diseases','evidence','hex','note'].some(k=>r[k]);
  const n = Object.keys(dirtyRows()).filter(k=>k!==cur.doc_id).length + (curDirty?1:0);
  const btn = $('exportBtn');
  btn.classList.toggle('unsaved', n>0); btn.classList.toggle('clean', n===0);
  btn.textContent = n ? 'save labels.csv \u25cf '+n+' unsaved' : 'save labels.csv (saved)';
}
function renderRowPreview(){
  const r = currentRowValues(true);   // what Save would write for this doc
  const line = ['doc_id','read','verdict','diseases','evidence','hex','note']
                 .map(k=>csvField(r[k])).join(',');
  $('exportBox').value = CSV_HEADER + '\n' + line;
  // Buffer each edit, including the current document, before a refresh/close.
  if(cur) commitCurrent();
  updateSaveBtn();
}

function updateDiffControls(){
  const enabled = !!cur && Object.hasOwn(cur, 'comparison');
  const preview = $('md').style.display!=='none';
  const on = $('toggleDiff').classList.contains('active');
  $('toggleDiff').hidden = !enabled;
  $('toggleDiff').disabled = !enabled || !cur.comparison || preview;
  $('toggleDiff').title = preview ? 'Switch off markdown preview to see raw text differences' : 'Highlight removed and added text';
  $('diffLegend').hidden = !enabled || !cur.comparison || preview || !on;
  for(const id of ['diag', 'comparisonDiag']) $(id).classList.toggle('no-diff', !on);
}

function renderComparison(){
  const enabled = Object.hasOwn(cur, 'comparison');
  $('docPanes').classList.toggle('comparing', enabled);
  $('primaryTitle').hidden = !enabled;
  $('comparisonPane').hidden = !enabled;
  $('primaryHash').textContent = 'SHA-256 (UTF-8): '+cur.sha256;
  updateDiffControls();
  if(!enabled) return;
  $('primaryTitle').textContent = 'Primary / pre · '+cur.primary_name;
  $('comparisonTitle').textContent = 'Comparison / post · '+cur.comparison_name;
  const other = cur.comparison;
  $('comparisonHash').textContent = other ? 'SHA-256 (UTF-8): '+other.sha256 : 'SHA-256: — (no matching document)';
  $('comparisonMessage').hidden = !!other;
  $('comparisonMessage').textContent = other ? '' : 'No matching doc_id in comparison pack. This primary document is retained in the audit.';
  $('comparisonMeta').textContent = other
    ? (cur.raw_text===other.raw_text ? 'Text unchanged' : 'Text changed')
      +' · doc_id='+other.doc_id+' · chars='+other.chars
      +' · source='+other.source+' · lang='+other.lang_label
      +(cur.diff && cur.diff.coarse ? ' · Large replacement blocks highlighted in full' : '')
    : '';
  // Clear stale text when the next primary row has no secondary match.
  renderDiag(other || {segments:[]}, 'comparisonDiag');
  $('comparisonMd').innerHTML = other ? renderMarkdown(other.raw_text) : '';
}

async function load(i, docId=null){
  const version = ++loadVersion;
  try {
    const query = docId===null ? 'i='+i : 'doc_id='+encodeURIComponent(docId);
    const res = await fetch('/api/doc?'+query);
    if(version!==loadVersion) return;
    if(!res.ok){
      const error = await res.json();
      if(version===loadVersion) alert(error.error || 'Could not load document');
      return;
    }
    const payload = await res.json();
    if(version!==loadVersion) return;
    // Capture even edits made while the request was in flight.
    commitCurrent();
    cur = payload; idx = cur.i;
  } catch(error){
    if(version===loadVersion) alert('Could not load document: '+error.message);
    return;
  }
  window.getSelection().removeAllRanges(); window._selFill=null;
  $('meta').textContent = '['+(cur.i+1)+'/'+cur.count+']  doc_id='+cur.doc_id
     +'  source='+cur.source+'  lang='+cur.lang_label+'  chars='+cur.chars
     + (cur.url? '  '+cur.url : '');
  $('jump').value = cur.i+1;
  $('jump').max = cur.count;
  seen.add(cur.i);
  if(RANDOM_NAV){
    $('prev').disabled = navHistory.length===0;
    $('next').disabled = cur.count<=1;
  } else {
    $('prev').disabled = idx===0;
    $('next').disabled = idx===cur.count-1;
  }
  renderDiag(cur);
  // markdown
  $('md').innerHTML = renderMarkdown(cur.raw_text);
  renderComparison();
  $('primaryBody').scrollTop=0; $('comparisonBody').scrollTop=0;
  // Each navigation resets to the first 100 code points and invalidates pending context requests.
  hexKey=null; updateHex();
  fillFields(cur.doc_id);
  dxFilter = null; renderFindings();
  $('status').innerHTML='offset: \u2013'; $('selstatus').innerHTML='';
}

// ---- events ----
// --random: "next" picks a random document not yet visited this session
// (starting over once every document has been seen); "back" retraces the
// documents visited via "next", most recent first.
const RANDOM_NAV = __RANDOM_NAV__;
const seen = new Set();
const navHistory = [];
function randomNext(){
  // Jump far: the new index must be at least MIN_GAP away from the current
  // document and the last few visited ones, so consecutive picks never come
  // from the same neighbourhood/batch of the pack.
  const n = cur ? cur.count : 1;
  if(n<=1) return idx;
  if(seen.size>=n){ seen.clear(); seen.add(idx); }
  const MIN_GAP = Math.max(1, Math.min(1000, Math.floor(n/10)));
  const recent = navHistory.slice(-5).concat([idx]);
  const far = j => recent.every(r => Math.abs(j-r) >= MIN_GAP);
  for(let t=0;t<500;t++){
    const j = Math.floor(Math.random()*n);
    if(!seen.has(j) && far(j)) return j;
  }
  for(let t=0;t<500;t++){            // fall back: any unvisited, far from current
    const j = Math.floor(Math.random()*n);
    if(!seen.has(j) && Math.abs(j-idx) >= MIN_GAP) return j;
  }
  for(let j=0;j<n;j++){ if(!seen.has(j)) return j; }
  return idx;
}
$('prev').onclick = ()=> {
  if(!RANDOM_NAV) return load(Math.max(0, idx-1));
  if(navHistory.length) load(navHistory.pop());
};
$('next').onclick = ()=> {
  if(!RANDOM_NAV) return load(Math.min((cur?cur.count:1)-1, idx+1));
  const j = randomNext();
  if(j!==idx){ navHistory.push(idx); load(j); }
};
$('jump').onchange = e => { const n=parseInt(e.target.value,10)-1; if(!isNaN(n)) load(n); };
$('goId').onclick = ()=>{
  const id=$('jumpId').value.trim(); if(!id) return;
  load(null, id);
};
$('jumpId').onkeydown = e=>{ if(e.key==='Enter') $('goId').click(); };
$('toggleMd').onclick = e => {
  const md=$('md'), dg=$('diag');
  const on = md.style.display==='none';
  md.style.display = on?'block':'none'; dg.style.display = on?'none':'block';
  $('comparisonMd').style.display = on?'block':'none';
  $('comparisonDiag').style.display = on?'none':'block';
  e.target.classList.toggle('active', on);
  updateDiffControls();
};
$('toggleDiff').onclick = e => {
  e.target.classList.toggle('active');
  updateDiffControls();
};
$('toggleDx').onclick = e => {
  const on = $('diag').classList.toggle('nohl');
  $('comparisonDiag').classList.toggle('nohl', on);
  e.target.classList.toggle('active', !on);
};
$('toggleHex').onclick = e => {
  const on = $('hexList').style.display==='none';
  $('hexList').style.display = on?'block':'none';
  $('hexHead').style.display = on?'block':'none';
  e.target.classList.toggle('active', on);
};
for(const id of ['diag', 'comparisonDiag']){
  $(id).addEventListener('mouseup', onCursor);
  $(id).addEventListener('keyup', onCursor);
}
document.addEventListener('selectionchange', ()=>{ if(document.activeElement && document.activeElement.tagName==='TEXTAREA') return; onCursor(); });

// use current selection to fill evidence+hex
// each new selection is appended once ("; "-separated); re-focusing without a new selection adds nothing
function appendSelFill(fieldId, key){
  const f = window._selFill;
  const used = key+'Used';
  if(!f || f[used]) return;
  f[used] = true;
  appendValue(fieldId, f[key]);
  renderRowPreview();
}
function appendValue(fieldId, value){
  const el = $(fieldId);
  if(el.value.split('; ').includes(value)) return;   // same span already recorded
  el.value = el.value ? el.value+'; '+value : value;
}
$('f_evidence').addEventListener('focus', ()=>appendSelFill('f_evidence', 'evidence'));
$('f_hex').addEventListener('focus', ()=>appendSelFill('f_hex', 'hex'));
$('f_diseases').addEventListener('input', ()=>{ syncDiseaseChecks(); updateHexWarn(); renderRowPreview(); });
// picking a dropdown value by hand makes it a real (non-default) value
['f_read','f_verdict'].forEach(id=>{
  const real = ()=>{ delete $(id).dataset.auto; };
  $(id).addEventListener('input', real);
  $(id).addEventListener('change', real);
});
['f_read','f_verdict','f_evidence','f_hex','f_note'].forEach(id=>{
  $(id).addEventListener('input', renderRowPreview);
  $(id).addEventListener('change', renderRowPreview);
});

// Commit the current doc's field values into the in-memory store + localStorage
// buffer (does NOT touch disk). Called on navigation and before saving.
function commitCurrent(withDefaults){
  if(!cur) return;
  const r = currentRowValues(withDefaults);
  // the form on screen is what gets saved. An emptied row that is in the CSV is
  // kept as an empty row, which save turns into "remove it"; one that never
  // reached the CSV is just dropped.
  if(!isEmptyRow(r) || disk[cur.doc_id]){ saved[cur.doc_id] = r; }
  else { delete saved[cur.doc_id]; }
  persistLocal();
  $('savedCount').textContent = Object.keys(saved).length;
}

$('clearRow').onclick = ()=>{
  if(!cur) return;
  clearedRows.add(cur.doc_id);
  ['f_read','f_verdict','f_diseases','f_evidence','f_hex','f_note'].forEach(id=>{ $(id).value=''; });
  applySelectDefaults();
  syncDiseaseChecks(); updateHexWarn();
  commitCurrent(); renderRowPreview();
  $('exportMsg').textContent = disk[cur.doc_id]
    ? 'cleared; click save to remove this row from labels.csv'
    : 'cleared';
};

$('exportBtn').onclick = async ()=>{
  if(saveInFlight) return;
  commitCurrent(true);   // Save on this doc keeps the dropdown defaults shown
  if(!clearedRows.has(cur.doc_id)) Object.keys(SELECT_DEFAULTS).forEach(id=>{ delete $(id).dataset.auto; });
  const rows = Object.values(dirtyRows());   // only edited rows; the server merges by doc_id
  const submitted=Object.fromEntries(rows.map(r=>[r.doc_id,{...r}]));
  saveInFlight=true; $('exportBtn').disabled=true;
  try {
    const res = await fetch('/api/save', {method:'POST', headers:{'Content-Type':'application/json'},
       body: JSON.stringify({rows})});
    const data = await res.json();
    if(!res.ok || !data.saved) throw new Error(data.error || 'Save failed');
    // Capture edits made during the request, then acknowledge only its snapshot.
    commitCurrent();
    const pending=Object.fromEntries(Object.entries(dirtyRows())
      .filter(([id,row])=>!sameRow(row,submitted[id])));
    disk=data.baseline;
    for(const id of Object.keys(saved)) delete saved[id];
    Object.assign(saved,disk,pending);
    persistLocal();
    fillFields(cur.doc_id);
    $('exportMsg').textContent='saved → '+data.saved+' ('+data.rows+' rows in file)';
    $('rowState').textContent=Object.keys(pending).length ? 'new edits pending' : 'saved';
    $('savedCount').textContent=data.rows;
  } catch(error){
    $('exportMsg').textContent='save failed: '+error.message;
    $('rowState').textContent='not saved';
  } finally {
    saveInFlight=false; $('exportBtn').disabled=false;
    updateSaveBtn();
  }
};

document.addEventListener('keydown', e=>{
  if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) return;
  if(e.key==='ArrowRight' || e.key==='Enter') $('next').click();
  else if(e.key==='ArrowLeft' || e.key==='b') $('prev').click();
  else if(e.key==='m') $('toggleMd').click();
  else if(e.key==='h') $('toggleHex').click();
  else if(e.key==='g') $('toggleDx').click();
});

async function bootstrap(){
  // 1) CSV is the source of truth
  try {
    const data = await (await fetch('/api/rows')).json();
    disk = data.rows || {};
    Object.assign(saved, disk);
  } catch(e){}
  // 2) overlay localStorage (unsaved edits win)
  try {
    const ls = JSON.parse(localStorage.getItem(LS_KEY)||'{}');
    Object.assign(saved, ls);
  } catch(e){}
  persistLocal();   // drop buffered rows that already match the CSV
  $('savedCount').textContent = Object.keys(saved).length;
  buildDiseasePicker();
  load(idx);
}
bootstrap();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
