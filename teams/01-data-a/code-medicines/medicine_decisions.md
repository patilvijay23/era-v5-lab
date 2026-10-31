# Code medicines: final decision

## Verdict

**Good to hand to Vijay for review: yes. Approved and frozen: not yet.** Only the lead can do that, and 2 questions below still need a team answer. All 23 rules are `CANDIDATE` in Spec v1 terms. No criterion fails on the sheet itself; the open items are reviewer sign-off and those 2 answers.

### Result per pack

Each pack is tested with the team's `harm_test.py --rule all` on its own gold set. "Stress" leaves in the docs that the gold builder excludes as disputed.

| pack | gold harm | result | stress | fixed / dropped / untouched | labelled rows treated |
|---|---|---|---|---|---|
| go | 0 / 163 = 0.00% | PASS | 1 / 171 = 0.58% | 265 / 44 / 191 | 309 / 337 |
| rust | 0 / 78 = 0.00% | PASS | 0 / 78 = 0.00% | 238 / 17 / 245 | 255 / 259 |
| js-ts | 0 / 204 = 0.00% | PASS | 2 / 207 = 0.97% | 265 / 16 / 219 | 281 / 296 |
| java | 0 / 116 = 0.00% | PASS | 2 / 138 = 1.45% | 350 / 11 / 139 | 361 / 384 |
| cpp | 0 / 120 = 0.00% | PASS | 0 / 124 = 0.00% | 343 / 10 / 147 | 353 / 378 |
| python | 0 / 46 = 0.00% | PASS | 1 / 51 = 1.96% | 325 / 16 / 159 | 336 / 343 |

Stress is not the official test. Its 6 hits are all docs that a third reader labelled with that disease, so the rule is right on each. Python's 1 doc is over 1% only because its gold set is so small. "Labelled rows" still counts the H3 and F2 rows that the instructor's ruling makes wrong.

### Against the criteria

| criterion | source | result |
|---|---|---|
| Disease, medicine in words and code, action, harm test, side effects | `DISEASES.md` §4, medicine template | **Met.** Every section has all 5. Examples give `doc_id` only, as Spec v1 asks; the exact characters are in the authors' sheets. |
| Changes or drops at most 1% of gold | `DISEASES.md` §4 | **Met.** Every rule alone and the whole sheet, per pack. |
| Pick the rule that passes and fixes the most; two rules only if they fix different cases | TSAI answer, 27 Oct | **Met.** |
| Vendored copy and "leetcode" rulings | Instructor answer, 30 Oct | **Met.** No path-based H3 or F2 rule is in the sheet. |
| Never remove a gold doc to make a rule pass | TSAI answer; guideline 3 | **Met by this sheet.** It removes none, and rules that relied on a dispute are held back. The branch's java gold has a separate problem: see below. |
| A medicine for each disease seen more than 5 times | `DISEASES.md` §4 | **Partly.** Gaps: cpp D1 (7, no medicine exists), js-ts E4 (9, no rule passes at 0 gold), java F1 (94, waiting on an answer). By ruling, no medicine: go H3, the F2 rows, js-ts D3. |
| Exact text differences count; each doc counted once | Spec v1 §2 | **Met.** Counted by the team's tool. |
| Tested on every pack a rule applies to; failures not hidden | Spec v1 §2.6 | **Met.** `LANGS` is explicit; other packs are N/A. Failures are listed in the table for each disease. |
| Treats real cases without new damage | Spec v1 §2.3 | **Met after fixes.** Python: 0 files stop parsing. All packs: 0 docs with code changed by a comment rule. No markers, placeholders or CR left. |
| Idempotent; order and conflicts recorded; combined test | Spec v1 §2.8 and §4 | **Met.** 0 docs change on a second run. Order matters in one way: drops run before licence removal, or generated files with a banner inside the licence survive. |
| No secrets or personal data | `DISEASES.md` §2a, pr-guard | **Met.** Scanned both files: no keys, and the only email is `user@example.com`. |
| Digests, owner, reviewer, commit | Spec v1 §1 and §2.9 | **Partly.** Gold and pack digests are in the sheet. Reviewer and the sheet's own commit come when it is pushed. |

### What this review changed

1. **A real bug in `DA-E4-004`.** It deleted `#include`, `#ifndef`, `#pragma once` and `#[derive]` on 20 cpp and 2 rust docs, because it treats `#` lines as comments. It also deleted shebang, encoding and Go build lines. The 1% test cannot see this, because those docs are not in gold. It is now `DA-E4-009`:
   - `#` counts as a comment on python only.
   - Shebang, encoding and Go build lines stay.
   - It repeats until nothing changes, so stacked headers go in one run.

   Result: gold still 0, 2 more labelled rows, 0 docs with code changed.
2. **New rule `DA-E3-004` for secrets.** It replaces the value with `EXAMPLE_SECRET` and never drops a file. It decides by the shape of the value, so dummy values stay. It touches 0 gold docs on all 6 packs and replaces the 4 real secrets no other rule could reach (rust 1, js-ts 2, java 1). `DA-E3-003` handles the 5th (go). It replaces `DA-E3-001`, which dropped files over dummy values.
3. **Instructor ruling applied.** `DA-H3-001` and `DA-F2-001` are rejected. No pack has a duplicate file, and no doc names a known benchmark.
4. **The A2 pick changed.** `DA-A2-006` deletes a lone CR, which joins lines and can pull code into a comment. No doc here has one, so the numbers could not show it.
5. **2 rules held back.** `DA-F1-003` and `DA-E4-003` passed only because a reader's own disputes kept docs out of gold.
6. **Rules that never acted were removed or scoped down**, such as `DA-E4-006`.

Every other rule is its author's code, copied unchanged: 0 differences from the source. Only the imports, `_std` and the `LANGS` guard are added. The person who compiled this sheet also wrote several of the picks (`DA-A2-007`, `DA-B4-009`, `DA-E3-003`, `DA-E3-004`, `DA-E4-005` and others), so a reviewer should look at those picks independently. The numbers for every candidate are in the tables below.

### Questions for the team

| question | what the answer changes |
|---|---|
| Are author names personal data? | `DA-F1-003` on: treats java's 93 rows, and java gold must be re-judged. |
| Do short licence notes count as E4, in every pack? | `DA-E4-003` on, and a rule for js-ts: 13 more java rows, 5 more js-ts rows for 1 gold doc. cpp also has 81 labelled E4 rows untreated. |

### Problems to report to the team

- **The branch's java gold fails the team's own check.** `gold_notes.py` reports 18 problems: docs left the gold set with no note. Its docstring says such a file must not be used. The 18 are the docs vaibh27 disputes.
- **amukka's `DA-E4-004` deletes code**, in their own rust pack too (2 docs).
- **F2 and H3 rows need re-reading** under the ruling: F2 in go 7, rust 4, js-ts 1, python 5; H3 in go 38. The go rows are being fixed by their annotator. That will change the go gold set, so this test must be rerun on the rebuilt gold.
- **The extractor gets nothing from 3 sheets:** amukka (`RULES` dict), AjaySnl and udisinghania (no `**Disease:**` lines). It also skips RaviNaik's E4 and B4, vaibh27's C4 and varshith2000's E4 sections.
- **Rules that return None to drop:** `harm_test.py` reports an error on those docs (saitej123's and vaibh27's E1). The sheet's wrapper handles it.
- **Rule IDs in this sheet are provisional.** `DA-E3-004`, `DA-E4-008`, `DA-E4-009` and `DA-C4-002` are new, and others come from a local extractor run.
- **The team decides the folder.** `code-medicines/` was removed in the branch cleanup.

### Limits

- The numbers come from 500-doc samples, and 5 of 6 gold sets are under the 200 target. On rust and python, 1 touched doc is already a FAIL.
- `DA-E3-004` is not a full scanner. A key with no digits, under 16 characters, or under a neutral name is missed. Its thresholds were written after seeing these packs, so new data is its real test.
- Only python has a real parser check. Other languages have the comments-stripped comparison and bracket counts, not a compile.
- A licence rule can take a file description in the same comment block: over 5 lines with no licence word on 19 cpp, 7 python, 5 java and 1 rust docs. No code is lost.
- Run on Windows with the merged watchdog, not on Linux. No rule hung.


## How rules were picked

On each pack, run the smallest set of rules that treats the most labelled rows and touches 0 gold docs of that pack. Where rules tie, read the code and take the one closest to the disease definition. A rule that passes only because its own supporters' disputes removed docs from gold is held back as BLOCKED.

**Inputs:** the latest `medicine.md` of all 11 code sheets in the open PRs (for TEJASKUMAR-REDDY-J, a 13-medicine file that is not in PR 73 yet, in place of its older 6-rule one), the latest labels of all 17 label sheets, and the official gold sets of `g1-harm-test` at `5513a7c` (a rebuild from the same labels gave identical files).

## The decision for each disease

Each cell: gold docs touched · labelled rows treated / labelled rows · labelled-clean docs touched outside gold.

### A1 invisible junk characters

**Picked:** `DA-A1-001` (TharunSivamani) on all 6 packs.

**Why:** One candidate. It treats every labelled row and touches no gold doc.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-A1-001` | TharunSivamani | **PICKED** | 0 · 0/0 · 0 | 0 · 1/1 · 0 | 0 · 1/1 · 0 | 0 · 1/1 · 0 | 0 · 12/12 · 0 | 0 · 0/0 · 0 |

### A2 control characters

**Picked:** `DA-A2-007` (TEJASKUMAR-REDDY-J) on all 6 packs.

**Why:** All 7 give the same text on all 3000 docs, because the packs only have CRLF. So the decision is on the code, with a test string holding a lone CR, `\x00` and form feed. Five only fix line endings and leave `\x00`. `DA-A2-006` joins lines on a lone CR. `DA-A2-007` is the only one that treats all of it safely. It was chosen on that test.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-A2-007` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |
| `DA-A2-001` | TharunSivamani | Only fixes line endings; leaves `\x00`, `\x1b`, DEL. | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |
| `DA-A2-002` | curioustushar | Only fixes line endings. | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |
| `DA-A2-003` | vaibh27 | Only fixes line endings. | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |
| `DA-A2-004` | varshith2000 | Only fixes line endings. | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |
| `DA-A2-006` | amukka | Same text on all 3000 docs, but it deletes a lone CR instead of turning it into LF. That joins lines and can pull code into a `//` comment. No doc here has a lone CR; the full corpus may. | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |
| `DA-A2-008` | riyaagrahari | Only fixes line endings. | 0 · 1/1 · 1 | 0 · 6/6 · 0 | 0 · 17/17 · 8 | 0 · 44/44 · 0 | 0 · 47/47 · 0 | 0 · 2/2 · 2 |

### A4 replacement characters

**Picked:** `DA-A4-002` (TEJASKUMAR-REDDY-J) on all 6 packs; `DA-A4-003` (vaibh27) on java.

**Why:** A conflict. `DA-A4-003` treats java's 2 rows, but on go it also changes `1dbf03039c9ea15c`, where the author quotes U+FFFD on purpose (ruling 7). So `DA-A4-002` runs everywhere and `DA-A4-003` on java only.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-A4-002` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 1/1 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/2 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |
| `DA-A4-003` | vaibh27 | **PICKED** | 0 · 1/1 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 2/2 · 1 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |

### A5 wrong normal form

**Picked:** nothing.

**Why:** 1 labelled row (js-ts). No medicine exists, and one row is below the 5 the template asks for.

### A6 mixed script (look-alike letters)

**Picked:** `DA-A6-001` (TEJASKUMAR-REDDY-J) on all 6 packs.

**Why:** One candidate.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-A6-001` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 2/2 · 1 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |

### B1 HTML entities

**Picked:** nothing.

**Why:** 2 labelled rows (go 1, cpp 1). saitej123 withdrew `DA-B1-001`. Unescaping entities in code would harm valid HTML templates.

### B2 HTML or XML tags

**Picked:** nothing.

**Why:** No rule picked. The only candidate gives the same text as the B3 pick, so the 244 js-ts rows are treated under B3.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-B2-001` | varshith2000 | Same text as the B3 pick on all 3000 docs. varshith2000 labels the StarCoder markers B2; ruling 1 says B3. | 0 · 0/0 · 0 | 0 · 0/1 · 0 | 0 · 244/244 · 1 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |

### B3 ghost markers

**Picked:** `DA-B3-001` (TharunSivamani) on all 6 packs.

**Why:** A conflict. 7 rules give identical text, so any of them works; the lowest registry ID was taken. The real choice was AjaySnl's, which scores highest on row count (1504 vs 1484 rows) only because it also treats B4 rows. Choosing it would hide the B4 decision, and it would replace `<NAME>` with a different word from the B4 pick.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-B3-001` | TharunSivamani | **PICKED** | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `AjaySnl:B3` | AjaySnl | Also rewrites `<EMAIL>` and `<NAME>`, which is B4's job, so it clashes with the B4 pick. The markers it removes are the same. Its extra 13 js-ts and 12 python rows all hold placeholders, and the B4 pick treats them. Its chat-token removal fires on 0 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 258/258 · 8 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 279/284 · 0 |
| `DA-B3-002` | RaviNaik | Same text as the pick on all 3000 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `DA-B3-003` | TEJASKUMAR-REDDY-J | Same text as the pick on all 3000 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `DA-B3-004` | curioustushar | Same text as the pick on all 3000 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `DA-B3-005` | vaibh27 | Same, plus it strips a BOM, which is A1's job (15 docs differ). | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `DA-B3-006` | saitej123 | Leaves a blank first line on every file it changes (880 docs differ from the pick). | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `DA-B3-007` | amukka | Same text as the pick on all 3000 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `DA-B3-008` | riyaagrahari | Same text as the pick on all 3000 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |
| `udisinghania:B3` | udisinghania | Same text as the pick on all 3000 docs. | 0 · 247/247 · 0 | 0 · 225/225 · 0 | 0 · 245/258 · 1 | 0 · 250/250 · 0 | 0 · 245/245 · 0 | 0 · 272/284 · 0 |

### B4 template junk / PII placeholders

**Picked:** `DA-B4-009` (TEJASKUMAR-REDDY-J) on all 6 packs.

**Why:** A conflict in the action: delete, replace, or drop. Replace was chosen. All 3 rules that leave no placeholder treat the same docs, so the count cannot decide. Deleting `<NAME>` in a code position breaks the syntax, while a neutral word stays valid in code and in strings. `DA-B4-009` is by the person who compiled this sheet, so this pick deserves a second look; vaibh27 and curioustushar also replace rather than delete, and the rulings do not settle it.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-B4-009` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 43/45 · 0 | 0 · 18/18 · 0 | 0 · 25/25 · 11 | 0 · 82/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `DA-B4-001` | TharunSivamani | Deletes the word. `IGNORECASE` also hits real `<email>` and `<year>` tags. Leaves `<KEY>`: 12 docs keep placeholders. | 0 · 39/45 · 0 | 0 · 17/18 · 1 | 0 · 22/25 · 9 | 0 · 81/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `DA-B4-002` | curioustushar | Leaves `<KEY>`: 12 docs keep placeholders. | 0 · 39/45 · 0 | 0 · 17/18 · 0 | 0 · 22/25 · 9 | 0 · 81/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `DA-B4-003` | vaibh27 | Same idea as the pick, but only replaces a quoted `"<KEY>"`: 7 docs keep placeholders. | 0 · 41/45 · 0 | 0 · 18/18 · 0 | 0 · 24/25 · 11 | 0 · 82/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `DA-B4-004` | varshith2000 | Detector only: it would drop 377 docs that the ruling says to fix. | 0 · 43/45 · 0 | 0 · 18/18 · 0 | 0 · 25/25 · 11 | 0 · 82/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `DA-B4-005` | amukka | Treats the same docs but deletes the word, which breaks a placeholder in a code position. | 0 · 43/45 · 0 | 0 · 18/18 · 0 | 0 · 25/25 · 11 | 0 · 82/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `DA-B4-010` | riyaagrahari | Treats the same docs but deletes the word, which breaks a placeholder in a code position. | 0 · 43/45 · 0 | 0 · 18/18 · 0 | 0 · 25/25 · 11 | 0 · 82/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |
| `RaviNaik:B4` | RaviNaik | Drops 145 docs that can be fixed (any `<KEY>`, `<PASSWORD>`, or a placeholder in code). | 0 · 43/45 · 0 | 0 · 18/18 · 0 | 0 · 25/25 · 11 | 0 · 82/83 · 0 | 0 · 121/122 · 0 | 0 · 27/27 · 1 |

### C1 boilerplate

**Picked:** `DA-C1-004` (TEJASKUMAR-REDDY-J) on go; `DA-C1-005` (vaibh27) on java.

**Why:** A different rule for each kind of boilerplate: `DA-C1-004` for Go scaffolds (go), `DA-C1-005` for IDE templates (java). `DA-C1-005` touches 1 gold doc each on js-ts and cpp, so cpp's 2 labelled rows stay untreated.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-C1-004` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 1/1 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/80 · 0 | 0 · 0/2 · 0 | 0 · 0/0 · 0 |
| `DA-C1-005` | vaibh27 | **PICKED** | 0 · 0/1 · 0 | 0 · 0/0 · 0 | 1 · 0/0 · 0 | 0 · 78/80 · 23 | 1 · 0/2 · 0 | 0 · 0/0 · 0 |
| `DA-C1-001` | curioustushar | Its 1 java row is treated by `DA-C1-005`. It touches 1 js-ts gold doc. | 0 · 0/1 · 0 | 0 · 0/0 · 0 | 1 · 0/0 · 0 | 0 · 1/80 · 1 | 0 · 0/2 · 0 | 0 · 0/0 · 0 |

### C2 repeated lines

**Picked:** nothing.

**Why:** 4 labelled rows (js-ts 3, cpp 1). saitej123 withdrew `DA-C2-001`.

### C3 truncated or broken document

**Picked:** `DA-C3-002` (TEJASKUMAR-REDDY-J) on go.

**Why:** One candidate, Go only. It drops 16 rust, 20 python and 2 js-ts gold docs because it does not understand those languages.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-C3-002` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 1/1 · 0 | 16 · 0/0 · 36 | 2 · 0/0 · 1 | 0 · 0/0 · 0 | 0 · 0/0 · 1 | 20 · 0/0 · 62 |

### C4 two documents joined

**Picked:** `DA-C4-002` (vaibh27) on java.

**Why:** One candidate, java only.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-C4-002` | vaibh27 | **PICKED** | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 1/1 · 0 | 0 · 0/1 · 0 | 0 · 0/0 · 1 |

### D1 wrong language label

**Picked:** nothing.

**Why:** 8 labelled rows (js-ts 1, cpp 7). No medicine exists; a rule on one document cannot tell that a language label is wrong.

### D3 mixed language

**Picked:** nothing.

**Why:** No rule picked: `DISEASES.md` says to label it, not judge it.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-D3-001` | varshith2000 | A check that changes nothing. `DISEASES.md`: label it, do not judge it. | 0 · 0/1 · 0 | 0 · 0/0 · 0 | 0 · 0/27 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |

### E1 minified or generated code

**Picked:** `DA-E1-001` (RaviNaik) on go; `DA-E1-002` (varshith2000) on js-ts; `DA-E1-004` (amukka) on rust, python; `DA-E1-005` (TEJASKUMAR-REDDY-J) on cpp; `DA-E1-006` (riyaagrahari) on java; `DA-E1-007` (vaibh27) on cpp.

**Why:** A conflict: 7 rules overlap, each tuned to its own language. For each pack the sheet takes the smallest set that fixes the most labelled rows. Running all of them everywhere only adds drops nobody labelled. Rows still untreated: go 1, rust 6, js-ts 7, java 4, cpp 13, python 1. Those have no marker a rule can see.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-E1-001` | RaviNaik | **PICKED** | 0 · 42/43 · 0 | 0 · 8/23 · 0 | 0 · 4/23 · 0 | 0 · 3/14 · 0 | 0 · 5/20 · 0 | 0 · 0/11 · 0 |
| `DA-E1-002` | varshith2000 | **PICKED** | 0 · 32/43 · 0 | 0 · 8/23 · 0 | 0 · 16/23 · 4 | 0 · 3/14 · 1 | 0 · 2/20 · 0 | 0 · 3/11 · 1 |
| `DA-E1-004` | amukka | **PICKED** | 0 · 34/43 · 0 | 0 · 17/23 · 0 | 0 · 4/23 · 0 | 0 · 4/14 · 1 | 0 · 6/20 · 0 | 0 · 10/11 · 1 |
| `DA-E1-005` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 41/43 · 0 | 0 · 14/23 · 0 | 0 · 3/23 · 0 | 0 · 6/14 · 1 | 0 · 6/20 · 0 | 0 · 0/11 · 0 |
| `DA-E1-006` | riyaagrahari | **PICKED** | 0 · 2/43 · 0 | 0 · 0/23 · 0 | 0 · 1/23 · 0 | 0 · 10/14 · 1 | 0 · 0/20 · 0 | 0 · 1/11 · 0 |
| `DA-E1-007` | vaibh27 | **PICKED** | 0 · 34/43 · 0 | 0 · 9/23 · 0 | 0 · 4/23 · 0 | 0 · 8/14 · 1 | 0 · 4/20 · 0 | 0 · 0/11 · 0 |
| `DA-E1-003` | saitej123 | Adds no row: every row it hits on python is hit by `DA-E1-004`. It crashes on 8 docs because it returns None, which the team tool rejects. | 0 · 1/43 · 0 | 0 · 0/23 · 0 | 0 · 1/23 · 0 | 0 · 1/14 · 0 | 0 · 0/20 · 0 | 0 · 8/11 · 0 |

### E2 data blobs

**Picked:** `DA-E2-001` (RaviNaik) on all 6 packs.

**Why:** `DA-E2-001` covers every row of `DA-E2-003`.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-E2-001` | RaviNaik | **PICKED** | 0 · 7/7 · 0 | 0 · 0/2 · 0 | 0 · 0/1 · 0 | 0 · 0/1 · 0 | 0 · 1/1 · 0 | 0 · 0/1 · 0 |
| `DA-E2-003` | TEJASKUMAR-REDDY-J | Its rows are a subset of `DA-E2-001` (go 5 of 7). | 0 · 5/7 · 0 | 0 · 0/2 · 0 | 0 · 0/1 · 0 | 0 · 0/1 · 0 | 0 · 1/1 · 0 | 0 · 0/1 · 0 |

### E3 secrets

**Picked:** `DA-E3-003` (TEJASKUMAR-REDDY-J) on all 6 packs; `DA-E3-004` (TEJASKUMAR-REDDY-J) on all 6 packs.

**Why:** A placeholder, never a drop. `DA-E3-003` handles known formats and base32 seeds. `DA-E3-004` is new, written for this sheet, because no submitted rule could do this: it separates real keys from dummy values by the shape of the value, and touches 0 gold docs. Of the 12 labelled rows: 5 are real secrets and all 5 are replaced (go 1, rust 1, js-ts 2, java 1). 6 js-ts rows already hold `<PASSWORD>` or `<KEY>`, which the B4 pick replaces. 1 js-ts row has neither a value nor a placeholder that a rule can see.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-E3-003` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 1/1 · 0 | 0 · 0/1 · 0 | 0 · 0/9 · 0 | 0 · 0/1 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |
| `DA-E3-004` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 0/1 · 0 | 0 · 1/1 · 0 | 0 · 2/9 · 0 | 0 · 1/1 · 1 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |
| `DA-E3-001` | varshith2000 | Drops the file, and takes any 8+ character value: it touches 1 js-ts gold doc over a dummy `AuthToken` and 1 go gold doc over `Password: "password"`. Replaced by `DA-E3-004`, which keeps the file and touches no gold doc. | 1 · 0/1 · 0 | 0 · 0/1 · 0 | 1 · 4/9 · 2 | 0 · 0/1 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |

### E4 repeated licence headers

**Picked:** `DA-E4-005` (TEJASKUMAR-REDDY-J) on go; `DA-E4-008` (RaviNaik) on java; `DA-E4-009` (amukka) on go, rust, java, cpp, python.

**Why:** The biggest conflict, and the one rule that was changed. `DA-E4-004` had the widest reach and the best numbers, and it was deleting real code (see its row). So `DA-E4-009` is that rule with 3 bugs fixed: gold still 0, 2 more labelled rows, 0 docs with code changed, idempotent. It is the base on 5 packs. `DA-E4-005` runs first on go because it reads Go headers and keeps build tags. `DA-E4-008` adds java rows it misses. **js-ts has none:** every rule touches its gold, because the js-ts readers mark real licence headers clean, so js-ts's 9 labelled rows stay untreated. `DA-E4-006` would add 5 rows for 1 gold doc, a 22-line MIT header, taking js-ts to 0.98%.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-E4-005` | TEJASKUMAR-REDDY-J | **PICKED** | 0 · 56/76 · 3 | 1 · 19/22 · 0 | 4 · 9/9 · 4 | 0 · 81/103 · 3 | 1 · 91/176 · 1 | 0 · 0/70 · 0 |
| `DA-E4-008` | RaviNaik | **PICKED** | 0 · 53/76 · 2 | 0 · 12/22 · 0 | 1 · 6/9 · 3 | 0 · 82/103 · 2 | 1 · 85/176 · 1 | 0 · 0/70 · 0 |
| `DA-E4-009` | amukka | **PICKED** | 0 · 50/76 · 2 | 0 · 22/22 · 0 | 4 · 6/9 · 3 | 0 · 81/103 · 2 | 0 · 94/176 · 1 | 0 · 49/70 · 4 |
| `DA-E4-001` | TharunSivamani | Cannot run: needs a second `header` argument, and it has no detection logic. | crash 500 | crash 500 | crash 500 | crash 500 | crash 500 | crash 500 |
| `DA-E4-002` | curioustushar | Touches gold on go (1) and js-ts (5). Adds no java row beyond the picks. | 1 · 9/76 · 0 | 0 · 0/22 · 0 | 5 · 1/9 · 2 | 0 · 37/103 · 6 | 0 · 0/176 · 0 | 0 · 0/70 · 0 |
| `DA-E4-003` | vaibh27 | **BLOCKED.** Fails with disputed docs left in: java 2 of 138, 1.45%. Only vaibh27 disputes those 2. Would add 13 java rows, 8 of them labelled clean by another reader. Needs: do short licence notes count as E4? | 5 · 45/76 · 15 | 2 · 10/22 · 2 | 8 · 6/9 · 4 | 0 · 48/103 · 10 | 5 · 79/176 · 14 | 0 · 0/70 · 0 |
| `DA-E4-004` | amukka | **Bug: deletes real code.** It treats `#` lines as comments, so on 20 cpp and 2 rust docs it removes `#include`, `#ifndef`, `#pragma once`, `#[derive]`. It also removes shebang, encoding and Go build lines, and needs 2 runs on stacked headers. The gold sets cannot see this. Replaced by `DA-E4-009`. | 0 · 50/76 · 2 | 0 · 21/22 · 0 | 4 · 6/9 · 3 | 0 · 81/103 · 2 | 0 · 93/176 · 5 | 0 · 49/70 · 4 |
| `DA-E4-006` | riyaagrahari | Its cpp rows are treated by `DA-E4-009`: it never acts inside the sheet. | 0 · 23/76 · 0 | 0 · 3/22 · 0 | 1 · 5/9 · 1 | 0 · 72/103 · 0 | 0 · 47/176 · 0 | 0 · 0/70 · 0 |
| `DA-E4-007` | saitej123 | Changes 0 documents on all 6 packs. | 0 · 0/76 · 0 | 0 · 0/22 · 0 | 0 · 0/9 · 0 | 0 · 0/103 · 0 | 0 · 0/176 · 0 | 0 · 0/70 · 0 |

### E5 broken encoding in code

**Picked:** nothing.

**Why:** 2 labelled rows (go 1, cpp 1). No medicine exists. go's row sits in the same comment that `DA-A4-002` removes.

### E6 not code

**Picked:** nothing.

**Why:** 1 labelled row (python). No medicine exists.

### F1 personal data

**Picked:** nothing.

**Why:** Nothing active. `DA-F1-001` is the same regex as a B4 rule, so its 83 python, 2 cpp and 1 go rows are treated by the B4 pick. `DA-F1-003` is the only rule for names, and it is blocked: see its row. So java's 93 author-name rows stay until the team decides. The `DISEASES.md` definition lists emails, phones, addresses and IDs, not names.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-F1-001` | saitej123 | Same regex as `DA-B4-010`. saitej123 labels the placeholders F1; the B4 pick treats the same 377 docs. | 0 · 1/2 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 11 | 0 · 10/94 · 0 | 0 · 2/2 · 0 | 0 · 83/83 · 1 |
| `DA-F1-003` | vaibh27 | **BLOCKED.** Fails with disputed docs left in: java 16 of 138, 11.59%. Only vaibh27 calls those sick, and those docs left the java gold set with no note, so `gold_notes.py` fails. Needs: are author names personal data? | 1 · 1/2 · 0 | 1 · 0/0 · 0 | 2 · 0/0 · 1 | 0 · 93/94 · 37 | 5 · 0/2 · 0 | 1 · 5/83 · 1 |

### F2 benchmark leak

**Picked:** nothing.

**Why:** Nothing active. The instructor ruled that "leetcode" alone is not a benchmark leak, so the only candidate, which reads the path, is rejected. A real F2 rule would have to match known benchmark problems (HumanEval, MBPP, LiveCodeBench, SWE-bench) and none exists yet. The labelled rows in go, rust, js-ts and python need re-reading by their annotators.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-F2-001` | TEJASKUMAR-REDDY-J | **Rejected by the instructor.** The word "leetcode" alone is not a benchmark leak. F2 needs a problem or solution from a known benchmark test set, named in the evidence. | 0 · 6/7 · 1 | 0 · 4/4 · 1 | 0 · 1/1 · 1 | 4 · 0/0 · 0 | 11 · 0/0 · 0 | 0 · 3/5 · 2 |

### F3 harmful content

**Picked:** nothing.

**Why:** 4 labelled rows (go 1, js-ts 1, cpp 2). No medicine exists; it needs a harm classifier.

### H3 same content in another source

**Picked:** nothing.

**Why:** Nothing active. The instructor ruled that a vendored copy is not a disease by itself and needs no proof of which copy is the original. If the same file is in the pack twice, the second copy is H1 or H2; otherwise it is clean. So vendored files stay.

| rule | author | decision | go | rust | js-ts | java | cpp | python |
|---|---|---|---|---|---|---|---|---|
| `DA-H3-001` | TEJASKUMAR-REDDY-J | **Rejected by the instructor.** A vendored copy is not a disease by itself. Only the same file twice in a pack counts, as H1 or H2 on the second copy. | 0 · 38/38 · 17 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 | 0 · 0/0 · 0 |

## Medicines that could not run

| medicine | why |
|---|---|
| udisinghania's B4, E1, E2, E4 | Need reviewed patches or human confirmation as arguments, so they are hand edits, not rules. Their B3 runs and is listed above. |
| varshith2000's E4 | The section has only a regex and no function, so nothing can run. |
| TharunSivamani's E4 (`DA-E4-001`) | Needs a second `header` argument. |
| saitej123's A1, A2, A3, A4, B1, C2, E2, E3 | Withdrawn: no longer in their `medicine.md`. |
| vaibh27's `cure` and `drop_if_nothing_left` | `cure` is their own pipeline of their rules. `drop_if_nothing_left` has no disease code, so nothing labels it. |
