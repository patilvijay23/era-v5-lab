# English medicines

The medicines of the English packs (en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth) as rules that the team's tools run unchanged.

| File | What it is |
|---|---|
| `medicine_en.md` | the standard sheet: 24 rules, one `RULE_ID` block each, in the form of `code-medicines/medicine_code.md`. Each section follows the medicine template of `diagnosis/DISEASES.md` (disease with counts and three examples, medicine in words and code, action, harm test, side effects) and ends with the decision of guideline 2. |
| `MEDICINE_CHECK.md` | from `tools/medicine_conflicts.py`: gold files without enough medicines, and medicines of different annotators that clash |

## Run

```
python -I teams/01-data-a/tools/harm_test.py --pack en-dclm.parquet --gold teams/01-data-a/gold/en-dclm_gold.csv --rules teams/01-data-a/en-medicines/medicine_en.md --rule DA-C1-006
python -I teams/01-data-a/tools/harm_test.py --pack en-dclm.parquet --gold teams/01-data-a/gold/en-dclm_gold.csv --rules teams/01-data-a/en-medicines/medicine_en.md --rule all
python -I teams/01-data-a/tools/medicine_conflicts.py --packs en- --sheet teams/01-data-a/en-medicines/medicine_en.md --out teams/01-data-a/en-medicines/MEDICINE_CHECK.md
python -I teams/01-data-a/tools/gold_notes.py
```

`DA-A3-002` needs `pip install ftfy`. The pack Parquet files are not in the repo.

## The rules

- **From the annotators' sheets (13):** shekar-maker's 8 (en-dclm, registry IDs), deepjyotisaha's 4 (en-fineweb-edu: `DA-B4-009`, `DA-C1-005`, `DA-C3-003`, `DA-F1-003`) and maheshsv's C3 (`DA-C3-004`, en-nemotroncc-synth). Their code is copied unchanged; `_std()` puts the result in the shared form.
- **New (11, author aneeshads):** A2 control characters, A4 replacement characters, A5 NFC, B1 HTML entities, B2 HTML tags, B3 chat markers, C1 site lines, C2 repeated paragraphs, C2 doubled lines, C3 teaser marks, C5 tag lines (`DA-A2-007`, `DA-A4-002`, `DA-A5-001`, `DA-B1-002`, `DA-B2-002`, `DA-B3-009`, `DA-C1-006`, `DA-C2-003`, `DA-C2-004`, `DA-C3-005`, `DA-C5-002`).
- **Decision (guideline 2):** 19 KEEP, 5 DROP. `DA-C1-002`, `DA-C1-005` and `DA-C5-001` fail the harm test; all of `DA-C3-001`'s and `DA-F1-002`'s labelled rows are fixed by the kept rules. The 19 KEEP rules together, in sheet order, change and drop no gold document of any English pack.

## Notes

- Every rule runs on every English pack (`LANGS = {"en", "eng"}`), so a rule written for one pack is also tested on the gold sets of the others.
- "Labelled rows" are the fix and drop rows of the English label sheets in the open pull requests of `theschoolofai/era-v5-lab` (dclm 3 sheets, fineweb-edu 3, nemotroncc 2, nemotroncc-synth 2, read on 29 Oct). They are not in this repo.
- Examples give the doc_id and the position only, never the text.
- deepjyotisaha's C1 scorer (and C3, which uses it) can take the pack's line counts. `harm_test.py` passes only the document, so they run without them; the author reports a different result on 7 of 500 documents then.
- `DA-C1-002` fails on en-dclm only because it collapses every run of three or more newlines, also where it removes no line (all 16 changed gold documents). `DA-C1-006` keeps its phrase list without that side effect.
- `DA-C3-004` is maheshsv's code with the constants his sheet gives in words, and one added guard: only documents with a `Question:` line. Without it the rule touches 14 gold documents of the other packs.
- F1: `DA-F1-002` (shekar-maker) puts `[EMAIL]` and `[PHONE]` in place of the value; `DA-F1-003` (deepjyotisaha) deletes it. Guideline 2 keeps `DA-F1-003` because it fixes more labelled rows; whether a placeholder is wanted is a team decision.
- Not covered: C4 (no rule passes), D3 (label, do not judge), D4 and D5 (no pattern), H1 to H3 (need the whole pack or other sources), B5 (maheshsv's detector cannot run). The table at the top of `medicine_en.md` says why.
