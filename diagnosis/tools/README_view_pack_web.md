# Web pack viewer and clean-document audit

This version is built on top of
[keshavamurali/dataviewer's `view_pack_web.py`](https://github.com/keshavamurali/dataviewer/blob/main/view_pack_web.py),
with additions for pre/post comparison, diff highlighting, document hashes, and
selection-based hex inspection.

Run from the repository root with Python and `pyarrow` installed. The app uses
the standard-library HTTP server and bundled JavaScript; no frontend build or
external web assets are needed.

```bash
# Existing single-pack viewer
python3 diagnosis/tools/view_pack_web.py pack.parquet --out labels.csv

# Compare original documents with cleaned documents
python3 diagnosis/tools/view_pack_web.py pre.parquet post.parquet --out audit.csv
```

Open <http://127.0.0.1:8000>. Files are supplied at startup as local paths.
Use `--start N` for a zero-based initial position, `--port N` for another port,
and `--host 0.0.0.0` to explicitly enable LAN access. The default binds to localhost.
`--help` lists the options.

## Comparison behavior

- The first file is primary. Its row order and document count control Back,
  Next, keyboard navigation, document-number jumps, and document-ID search.
- The second file is left-joined by exact `doc_id`, regardless of its row order.
  Secondary-only IDs are excluded from navigation and search.
- Pre and post text appear in independently scrollable panes. Each matched pair
  is marked “Text changed” or “Text unchanged.” Markdown preview and disease
  highlights toggle together for both panes.
- Both document headers share a height, so their first text lines align even
  when metadata, hashes, or warning banners wrap. Navigation scrolls both
  document bodies back to the start.
- Git-style diff highlights are enabled by default: red marks removed primary
  text and green marks added comparison text. The **differences** button toggles
  them independently of disease highlights. Diff colors use diagnostic text;
  switch off Markdown preview to see them. Changed newlines show a `↵` marker;
  selecting text still uses raw Python code-point offsets.
- Small replacements are refined by character. Large replacement blocks are
  highlighted in full to bound matching work, with a note in the comparison
  header. Unchanged pairs have no diff coloring. A missing secondary row remains
  an unmatched row rather than being treated as a text deletion.
- Above each document, **SHA-256 (UTF-8)** hashes its exact raw text, including
  whitespace and hidden characters, without Unicode normalization. This is a
  document-text hash, not a hash of the Parquet file or its metadata. Null text
  uses the same hash as the empty text shown by the viewer. Single-pack mode
  also shows its document hash; an unmatched post document has no hash.
- A missing secondary row displays an explicit message. An empty or null
  secondary text is still a matched document, rendered as empty text.
- Both files require `doc_id` and `text` columns. IDs must be unique, nonempty
  strings; text must be a string or null. Duplicate IDs fail at startup rather
  than choosing an arbitrary match. An empty primary pack fails clearly; an
  empty secondary pack is valid when it contains the required columns.
- With one file, the existing single-document presentation is used.

## Annotations

Annotations and detected-candidate lists refer to the primary document. Select
primary text to fill evidence and hex using Python code-point offsets. Secondary
selections do not fill primary evidence, because cleaning can move offsets.
The right pane displays hidden characters and candidate highlights for comparison.

The Save button merges edited rows into `--out`, using the existing label CSV
schema. Use a separate output path for a clean-document audit when you want to
keep its decisions separate from original diagnosis labels.

Unsaved edits are buffered as you type in browser local storage, scoped to the
primary file path and output CSV path. Saving still requires the Save button.
Browser storage is best-effort; only the CSV is a durable submission artifact.
Old drafts stored under the earlier global `view_pack_web_rows` key are not
automatically imported into a pack's new draft buffer.

The hex panel initially shows the first 100 primary code points. Clicking or
selecting diagnostic text in either document changes it to the selected code
point, 25 preceding code points, and 75 following code points (up to 101 rows).
For a selection spanning several characters, its starting offset is used.
The range clips at document boundaries and keeps absolute Python code-point
offsets. The current row is highlighted, and the heading identifies the active
pre/post document and range. Navigation resets the panel to the first 100
primary code points. Hex context is available throughout the document and is
fetched without rerunning disease detection. Secondary inspection still does
not fill primary annotation evidence.

Diagnostic text and candidate detection use the complete document. The candidate
list shows at most 1,000 findings; counts include all findings. Candidate
highlights require human judgment.

## Verification

```bash
python3 -I teams/01-data-a/tests/tools/test_view_pack_web.py

# Optional UI behavior checks; requires Node.js and Python with pyarrow
PACK_VIEWER_PYTHON=python3 node teams/01-data-a/tests/tools/test_view_pack_web_ui.cjs
```

The Python suite uses generated Parquet files and a temporary localhost server.
The JavaScript suite exercises the bundled UI with a DOM double. It checks
application behavior and does not replace visual checks in a real browser.
Diff regressions cover insertion/deletion/replacement, whitespace/newline
changes, Unicode code-point offsets, unchanged/missing/empty texts, large
replacement fallback, and hashes of exact UTF-8 text.
