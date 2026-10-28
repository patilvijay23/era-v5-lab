# Medicine check

Medicine sheets: `/Users/aneeshadas/ERA5/Capstone/Week1-G-work/era-v5-lab/teams/01-data-a/medicines/submissions`. Gold files: `/Users/aneeshadas/ERA5/Capstone/Week1-G-work/era-v5-lab/teams/01-data-a/gold`. Rules: `medicine_en.md`. Made by `medicine_conflicts.py`; no code was run.
"Can run" means that the rule's code defines every name it needs. It says nothing about the harm test: run `harm_test.py` for that.

## Summary

| Gold file | Gold docs | Sheets | Rules | Rules that can run | Flags |
|---|---|---|---|---|---|
| en-dclm_gold.csv | 62 | 2 | 19 | 19 | BLANK SHEET, ONE ANNOTATOR, SMALL GOLD SET |
| en-fineweb-edu_gold.csv | 160 | 1 | 15 | 15 | ONE ANNOTATOR, NO RULE |
| en-nemotroncc_gold.csv | 34 | 1 | 11 | 11 | BLANK SHEET, SMALL GOLD SET |
| en-nemotroncc-synth_gold.csv | 96 | 2 | 12 | 12 | NO RULE, SMALL GOLD SET |

## en-dclm

- Gold set: en-dclm_gold.csv, 62 documents (1% allows 0); 62 of the target 200 (BELOW_TARGET)

| Annotator | Sheet | Rules | Can run |
|---|---|---|---|
| mittalutkarsh | blank template | 0 | 0 |
| shekar-maker | 8 medicines | 8 | 8 |

Rules written for several packs that also run here (11): `DA-A4-002` (A4), `DA-C3-005` (C3), `DA-A2-007` (A2), `DA-A5-001` (A5), `DA-B1-002` (B1), `DA-B2-002` (B2), `DA-B3-009` (B3), `DA-C1-006` (C1), `DA-C2-003` (C2), `DA-C2-004` (C2), `DA-C5-002` (C5).

### Flags

- **BLANK SHEET**: mittalutkarsh: the medicine sheet is the blank template
- **ONE ANNOTATOR**: only shekar-maker wrote medicines
- **SMALL GOLD SET**: 62 documents: 1% allows 0, so one touched document fails a rule

### Medicines with the same code

No code has more than one medicine.

## en-fineweb-edu

- Gold set: en-fineweb-edu_gold.csv, 160 documents (1% allows 1); 160 of the target 200 (BELOW_TARGET)

| Annotator | Sheet | Rules | Can run |
|---|---|---|---|
| deepjyotisaha | 5 medicines | 4 | 4 |

Rules written for several packs that also run here (11): `DA-A4-002` (A4), `DA-C3-005` (C3), `DA-A2-007` (A2), `DA-A5-001` (A5), `DA-B1-002` (B1), `DA-B2-002` (B2), `DA-B3-009` (B3), `DA-C1-006` (C1), `DA-C2-003` (C2), `DA-C2-004` (C2), `DA-C5-002` (C5).

### Flags

- **ONE ANNOTATOR**: only deepjyotisaha wrote medicines
- **NO RULE**: D3: found more than 5 times (6) and no rule that can run

### Medicines with the same code

No code has more than one medicine.

## en-nemotroncc

- Gold set: en-nemotroncc_gold.csv, 34 documents (1% allows 0); 34 of the target 200 (BELOW_TARGET)

| Annotator | Sheet | Rules | Can run |
|---|---|---|---|
| HariniJasti | blank template | 0 | 0 |

Rules written for several packs that also run here (11): `DA-A4-002` (A4), `DA-C3-005` (C3), `DA-A2-007` (A2), `DA-A5-001` (A5), `DA-B1-002` (B1), `DA-B2-002` (B2), `DA-B3-009` (B3), `DA-C1-006` (C1), `DA-C2-003` (C2), `DA-C2-004` (C2), `DA-C5-002` (C5).

### Flags

- **BLANK SHEET**: HariniJasti: the medicine sheet is the blank template
- **SMALL GOLD SET**: 34 documents: 1% allows 0, so one touched document fails a rule

### Medicines with the same code

No code has more than one medicine.

## en-nemotroncc-synth

- Gold set: en-nemotroncc-synth_gold.csv, 96 documents (1% allows 0); 96 of the target 200 (BELOW_TARGET)

| Annotator | Sheet | Rules | Can run |
|---|---|---|---|
| AJJAPUSIVA | hand edits | 0 | 0 |
| maheshsv | 7 medicines | 1 | 1 |

Rules written for several packs that also run here (11): `DA-A4-002` (A4), `DA-C3-005` (C3), `DA-A2-007` (A2), `DA-A5-001` (A5), `DA-B1-002` (B1), `DA-B2-002` (B2), `DA-B3-009` (B3), `DA-C1-006` (C1), `DA-C2-003` (C2), `DA-C2-004` (C2), `DA-C5-002` (C5).

### Flags

- **NO RULE**: B5: found more than 5 times (12) and no rule that can run
- **NO RULE**: C4: found more than 5 times (9) and no rule that can run
- **SMALL GOLD SET**: 96 documents: 1% allows 0, so one touched document fails a rule

### Medicines with the same code

#### B4: COMPARE

| Annotator | Kind | Action | Rule | Medicine |
|---|---|---|---|---|
| AJJAPUSIVA | hand edit (line 73) | fix | - | Row 81: B4 placeholder medicine |
| maheshsv | no rule | fix | - | match the negated phrase (`…`, `…`) or `…`. Delete the bullet, `…` line or QA pair that carries it; in runnin… |
| maheshsv | no rule | fix | - | when a letter is directly followed by `…`, the quote opens a word that starts with `…`, `…` or `…`, and the p… |

#### C1: ACTIONS DIFFER

| Annotator | Kind | Action | Rule | Medicine |
|---|---|---|---|---|
| AJJAPUSIVA | hand edit (line 7) | drop | - | Drop document rows 22 (F3), 113 (C5 / search-result collage), and 124 (C5/C1 / snippets lacking coherent arti… |
| maheshsv | no rule | fix | - | delete a line when the whole line, trimmed, matches a navigation, sharing, metadata or footer pattern. |

#### C3: RULE VS HAND

| Annotator | Kind | Action | Rule | Medicine |
|---|---|---|---|---|
| AJJAPUSIVA | hand edit (line 14) | fix | - | Rows 75, 76: manually reviewed local join applied; C3 remains provisional because both source rows end in com… |
| AJJAPUSIVA | hand edit (line 15) | fix | - | Rows 109, 110: manually reviewed body join and separate Q&A applied locally. Missing list after row 110's `…`… |
| AJJAPUSIVA | hand edit (line 54) | fix | - | Rows 75-76: manual list reconstruction (C3 provisional) |
| AJJAPUSIVA | hand edit (line 71) | fix | - | Side effects: source continuation is inferred from list contents, not verified against the original article.… |
| AJJAPUSIVA | hand edit (line 108) | fix | - | Unresolved: the article still ends `…`. Flag the missing list; do not claim the joined article is complete. R… |
| maheshsv | rule | fix | DA-C3-004 (can run) | take the passage before the first `…` line. (a) If its last line is a prose line (20 characters or more, not… |

#### C4: ACTIONS DIFFER

| Annotator | Kind | Action | Rule | Medicine |
|---|---|---|---|---|
| AJJAPUSIVA | hand edit (line 18) | fix | - | Row 16: manual C4 medicine |
| AJJAPUSIVA | hand edit (line 36) | fix | - | Row 34: manual C4 medicine |
| maheshsv | no rule | drop | - | the obvious lexical rule, as code, so that its failure is on record: |

#### C5: COMPARE

| Annotator | Kind | Action | Rule | Medicine |
|---|---|---|---|---|
| AJJAPUSIVA | hand edit (line 7) | drop | - | Drop document rows 22 (F3), 113 (C5 / search-result collage), and 124 (C5/C1 / snippets lacking coherent arti… |
| maheshsv | no rule | drop | - | none that passes a test yet. I tried "flag a document in which at least half of the non-QA lines are short ti… |


## Across the packs of one language

### en-* B4

| Pack | Annotator | Action | Rule | Medicine |
|---|---|---|---|---|
| en-dclm | shekar-maker | fix | DA-B4-006 (can run) | delete the residue tokens, not the document. |
| en-fineweb-edu | deepjyotisaha | fix | DA-B4-009 (can run) | Two parts. - template junk (fix): remove what a web page left unfilled: "{{ title }}", "{% if … %}", "${name}… |
| en-nemotroncc-synth | AJJAPUSIVA | fix | - | Row 81: B4 placeholder medicine |
| en-nemotroncc-synth | maheshsv | fix | - | match the negated phrase (`…`, `…`) or `…`. Delete the bullet, `…` line or QA pair that carries it; in runnin… |
| en-nemotroncc-synth | maheshsv | fix | - | when a letter is directly followed by `…`, the quote opens a word that starts with `…`, `…` or `…`, and the p… |

### en-* C1: ACTIONS DIFFER

| Pack | Annotator | Action | Rule | Medicine |
|---|---|---|---|---|
| en-dclm | shekar-maker | fix | DA-C1-002 (can run) | remove a line when it is short (8 words or fewer) and starts with a site-chrome phrase. |
| en-fineweb-edu | deepjyotisaha | fix | DA-C1-005 (can run) | Remove a line, or the end of a line, when it is website text rather than article text. Five kinds, each with… |
| en-nemotroncc-synth | AJJAPUSIVA | drop | - | Drop document rows 22 (F3), 113 (C5 / search-result collage), and 124 (C5/C1 / snippets lacking coherent arti… |
| en-nemotroncc-synth | maheshsv | fix | - | delete a line when the whole line, trimmed, matches a navigation, sharing, metadata or footer pattern. |

### en-* C3: ACTIONS DIFFER

| Pack | Annotator | Action | Rule | Medicine |
|---|---|---|---|---|
| en-dclm | shekar-maker | drop | DA-C3-001 (can run) | only the *stub* form is treated. A document of at most 600 characters whose last word is one no sentence ends… |
| en-fineweb-edu | deepjyotisaha | fix | DA-C3-003 (can run) | Remove the last line of a document when it is an unfinished sentence: the last non-empty line has at least si… |
| en-nemotroncc-synth | AJJAPUSIVA | fix | - | Rows 75, 76: manually reviewed local join applied; C3 remains provisional because both source rows end in com… |
| en-nemotroncc-synth | AJJAPUSIVA | fix | - | Rows 109, 110: manually reviewed body join and separate Q&A applied locally. Missing list after row 110's `…`… |
| en-nemotroncc-synth | AJJAPUSIVA | fix | - | Rows 75-76: manual list reconstruction (C3 provisional) |
| en-nemotroncc-synth | AJJAPUSIVA | fix | - | Side effects: source continuation is inferred from list contents, not verified against the original article.… |
| en-nemotroncc-synth | AJJAPUSIVA | fix | - | Unresolved: the article still ends `…`. Flag the missing list; do not claim the joined article is complete. R… |
| en-nemotroncc-synth | maheshsv | fix | DA-C3-004 (can run) | take the passage before the first `…` line. (a) If its last line is a prose line (20 characters or more, not… |

### en-* C5

| Pack | Annotator | Action | Rule | Medicine |
|---|---|---|---|---|
| en-dclm | shekar-maker | drop | DA-C5-001 (can run) | drop when (a) a 4-word phrase made of 3+ content words repeats 6+ times at a density of at least 8 per 1000 w… |
| en-nemotroncc-synth | AJJAPUSIVA | drop | - | Drop document rows 22 (F3), 113 (C5 / search-result collage), and 124 (C5/C1 / snippets lacking coherent arti… |
| en-nemotroncc-synth | maheshsv | drop | - | none that passes a test yet. I tried "flag a document in which at least half of the non-QA lines are short ti… |

### en-* F1

| Pack | Annotator | Action | Rule | Medicine |
|---|---|---|---|---|
| en-dclm | shekar-maker | fix | DA-F1-002 (can run) | replace with a placeholder. An email is redacted when its shape is personal (first.last, digits, a long local… |
| en-fineweb-edu | deepjyotisaha | fix | DA-F1-003 (can run) | Remove every email address, phone number and ID number, together with a label in front of it ("Tel:", "Fax:",… |
