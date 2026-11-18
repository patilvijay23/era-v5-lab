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

# Audit changed/missing documents, with random Next navigation
python3 diagnosis/tools/view_pack_web.py pre.parquet post.parquet \
  --changed-only --random --out audit.csv
```

Open <http://127.0.0.1:8000>. Files are supplied at startup as local paths.
Use `--start N` for a zero-based initial position, `--port N` for another port,
and `--host 0.0.0.0` to explicitly enable LAN access. The default binds to localhost.
`--help` lists the options.

## Filtering and navigation

By default the viewer shows all primary rows in their original order.

| Option | Current behavior |
| --- | --- |
| `--changed-only` | Requires a second file. Retains primary rows whose text differs or whose ID is missing from the second file. Unchanged rows are excluded from navigation and ID search. Metadata changes alone do not qualify; null and empty text compare as equal. |
| `--random` | Next chooses an unvisited document, trying to jump away from the current and recent positions. After all documents have been seen, another cycle begins. Back retraces Next choices; number/ID jumps do not add history. History resets on page reload. |
| `--start N` | Zero-based initial position in the displayed, possibly filtered primary rows. Defaults to zero and clamps to valid bounds. The on-page number field is one-based. |

The standalone viewer exits with an error when `--changed-only` leaves no rows.
Omit that option to inspect an unchanged pair. Random mode still starts at
`--start`; it changes Next/Back navigation rather than shuffling the file.

Keyboard controls outside form fields: Right/Enter = Next, Left/`b` = Back,
`m` = Markdown preview, `h` = hex panel, and `g` = disease highlights.

## Comparison behavior

- The first file is primary. Its displayed rows control navigation, number
  jumps, and document-ID search, subject to the filtering/random options above.
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

CSV columns: `doc_id,read,verdict,diseases,evidence,hex,note`. This file stores
manual annotations; it does not automatically export text differences or change
the Parquet files.

Empty read/verdict fields display **full** and **clean** as provisional defaults.
Merely browsing a document does not save those defaults. Clicking Save records
the displayed defaults for the current document; adding a real annotation such
as a note also retains them. Review these fields before saving an audit decision.
The CSV preview shows what saving the current document would write.

**Clear this row**, followed by Save, deletes that document's existing CSV row.
The displayed defaults remain provisional after clearing and do not recreate
the deleted row. Entering a real annotation starts a new row normally.

Save acknowledges only the submitted snapshot: edits made while a request is
pending remain buffered and marked unsaved, including edits on another document.
Duplicate Save requests are suppressed while one is in flight. Write failures
are displayed without discarding drafts. Cooperating viewer processes serialize
CSV updates with a persistent `<output>.lock` sidecar, then atomically replace
the CSV from a temporary file in the same directory. Leave the sidecar in place;
external editors that do not use that lock should edit only with writers stopped.

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

## Optional multi-pack hub

[`view_packs_hub.py`](view_packs_hub.py) imports the viewer and adds a pack
sidebar to one server. Keep it for auditing many pack pairs without restarting
the viewer for each pair. It is not required by `view_pack_web.py`; use the
standalone command above for one file or one pair.

```bash
python3 diagnosis/tools/view_packs_hub.py \
  --pre-root /path/to/Cap1-packs \
  --post-root /path/to/tokenizer_sample_v0_clean/train \
  --labels-dir /path/to/audit_labels
```

The hub discovers this exact directory layout and pairs by pack/file name:

```text
<pre-root>/<pack>/Part_<number>/<file>.parquet
<post-root>/<pack>/<file>.parquet
```

Missing post files are skipped. A `<pre-root>/<pack>/train/<file>.parquet`
layout is not discovered. Use the standalone viewer with explicit paths for
other layouts. Multiple Parquet files in one `Part_*` directory are supported;
each pair's key and sidebar label include its filename.

The sidebar counts changed/total documents in the background. Click a pair to
load it. **Only changed docs** and **Random next** are enabled by default;
**Apply** reloads the current pair with the chosen settings. Unlike the standalone
viewer, the hub falls back to all rows when a pair has no changed documents and
displays a note. Random mode chooses a random initial document in the hub.

With one file in a Part directory, its existing output remains
`<labels-dir>/<pack>_<Part_number>.csv`. With multiple files, each output adds
a stable 16-character hash of its pack/part/filename key before `.csv` to avoid
collisions. If a previously single-file directory gains another shard, its
output names change; earlier CSVs are left untouched and are not automatically
migrated because the old multi-file naming was ambiguous. Unsaved annotations are
buffered per primary/output path before switching, and the page reloads into
the selected pair. Browser buffering is not a substitute for saving the CSV.

Hub options:

| Option | Behavior |
| --- | --- |
| `--pre-root` | Defaults to `Cap1-packs` in the repository's parent directory. |
| `--post-root` | Defaults to `tokenizer_sample_v0_clean/train` in that parent directory. |
| `--labels-dir` | Defaults to `audit_labels` in that parent directory; created at startup. |
| `--exclude PREFIX ...` | Skips pack names beginning with any supplied prefix; none excluded by default. |
| `--all-docs` | Starts with Only changed disabled. |
| `--sequential` | Starts with Random next disabled. |
| `--host`, `--port` | Default to `127.0.0.1:8000`, as in the standalone viewer. |

The hub still has one active view per process. Each page includes a generation
token on every API request. Switching pairs or applying options invalidates
older pages: their reads, saves, and selections receive a conflict response
instead of accessing another pack. Reload an older tab to use the active view;
its unsaved annotations remain in that pack's browser draft buffer. Pack changes
and complete document/hex/save requests are serialized, so an in-flight save
finishes against its original CSV before a switch proceeds. Multiple tabs do
not maintain independently selected packs.

## Verification

```bash
python3 -I teams/01-data-a/tests/tools/test_view_pack_web.py
python3 -I teams/01-data-a/tests/tools/test_view_packs_hub.py

# Optional UI behavior checks; requires Node.js and Python with pyarrow
PACK_VIEWER_PYTHON=python3 node teams/01-data-a/tests/tools/test_view_pack_web_ui.cjs
```

The Python suite uses generated Parquet files and a temporary localhost server.
The JavaScript suite exercises the bundled UI with a DOM double. It checks
application behavior and does not replace visual checks in a real browser.
Diff regressions cover insertion/deletion/replacement, whitespace/newline
changes, Unicode code-point offsets, unchanged/missing/empty texts, large
replacement fallback, and hashes of exact UTF-8 text.

The UI harness substitutes the random-navigation template value and checks
both navigation modes, provisional defaults, clear/save deletion, pending-save
edits, and failure handling. Python tests also exercise atomic-write failure,
concurrent writer processes, unique multi-file hub keys, stale-page rejection,
pack-switch/save serialization, and zero-change fallback. A real-browser visual
check remains outstanding.
