# Math reading audit (task 8): math-finemath

Reader: pyru (Data A rotation, week 2). Date: 1 Nov 2026.

## What was read

- **Docs:** 100 picked at random (seed 20261101) from the 28,522 docs spec v1 kept out of 29,122 in the tokenizer sample part `train/math-finemath/part-00000.parquet` (sha256 a5dbb4da6d0c2e89).
- **Cleaner:** spec v1 from g1-specv1 at 67e6187 (clean.py sha256 c7b192ab), run on my machine: keep 20,360, fix 8,162, drop 600, 0 errors. Spec v1 changed 26 of the 100 picked docs.
- **Method: AI-assisted.** Claude (Anthropic) made a first pass over all 100 docs and suggested 148 findings. I accepted all 148 unchanged and added or rejected none. The CSV column `source` marks each one.
- **Approved spec v1:** the approved version (PR #194 at e7531f9, clean.py sha256 d3464bda) differs from the one read here only by the shared F1 rule for math. On these 100 docs it changes one: in e1d06f4e49257cfe it replaces an email at clean offset 2954, inside the C1 block reported at @2801, with `<EMAIL>`. The other 99 docs come out byte-identical to the text read. The math rules and the shared F1 are the same at g1-specv1 5a28e53. I will check the 100 docs again against TSAI's job output when it is returned.
- **Positions:** offsets count characters (code points) from 0 in the original text. This summary and the CSV hold no doc text.

## Findings (docs out of 100)

| Code | What spec v1 left | Kind | Docs | Examples (doc_id @ offset) |
|---|---|---|---|---|
| C1 | Site boilerplate: forum post headers, comment signatures, promos, footers | missed | 69 | d8cdfe9d696affee @462; 2206a4b3f2fa1c98 @9089; 74081137bc07599a @37 |
| NEW | Missing symbols or formulas (images dropped, so a sentence ends in a colon) | missed | 11 | 684104b74a06267b @444; 48f9583ca4f5f6d7 @189; fe988ef1a6257c35 @969 |
| C2 | Quoted posts repeating earlier posts | missed | 10 | cc98b78d56e7d12a @229; 29e09f00864fb729 @475; 91bf5e3b4ad423ee @1053 |
| NEW | Flattened formulas (superscripts lost, fractions split over lines) | missed | 6 | 0f2f052fd95da6d4 @2078; a4e9be8e5651af40 @1175; 1fecb45d0ff3dce1 @105 |
| B5 | Broken LaTeX or Markdown | missed | 5 | 2206a4b3f2fa1c98 @1102; 1b1a0d909bc9c515 @4836; b0db84c6cc4bfa1d @0 |
| B4 | Template and code junk | missed | 4 | 404146d814b03d07 @77; fc3df208c596140d @10365; 627f7669b7376fb5 @8035 |
| NEW | Template-generated pages (number facts, unit converters) | missed | 3 | bfb1450cc0baabcd; fc3df208c596140d; 647d9713533c5664 |
| NEW | SEO filler text | missed | 3 | 085f9f7987b7cf56; 2e13692256fe1603; d10ec0084ee609b0 |
| NEW | Merged table cells | missed | 3 | 1b1c42eddd14c8e7 @2926; 83efffa29c3912fb @293; 1e7fad525310d310 @1927 |
| B1 | HTML entities | missed | 2 | 61515ee94cba4c0c @583; 8758fc16164dd1b6 @961 |
| NEW | Missing spaces between words | missed | 2 | 611df2fbc4c0e699 @167; 1e7fad525310d310 @2817 |
| NEW | AI-generated text | missed 1, unsure 3 | 4 | 91bf5e3b4ad423ee @40; 36c3e8b4b4457083; 91fddbdb172ba0b0 |
| B2, C3, C4, C5, D3, E1, E2 | One doc each | missed | 1 each | see CSV |
| NEW | Code lines missing in the source; dropped ligature letters | missed | 1 each | 1b1a0d909bc9c515 @8827; c4f8ad82ea97fd64 @1159 |

## Harm by spec v1

**DA-C2-001** (repeated lines) deleted real content in 4 docs. It removed program print lines and the result lines of program outputs, R matrix column headers, and the instruction line of numbered problems.

- 404146d814b03d07 @1018
- 1b1a0d909bc9c515 @8997
- bf617118c1ef6d8b @1432
- f8993128de3e2a07

The rule needs an exception for code, program output and lists of numbered items.

## For the lead to decide (unsure)

- **Escaped currency (B5, 5 docs):** dollar signs are written as `\$`. This may be the FineMath convention.
- **Search-results listing pages (C5, 4 docs):** pages that are lists of problem titles with teasers.
- **AI-generated text (3 docs):** possible machine-written text, which falls under the licence rule.
- **Unattributed CC-BY-SA copy (1 doc):** an encyclopedia mirror with no attribution.

## New diseases above 1% (2 or more docs) for task 11

- Missing symbols or formulas (11)
- Flattened formulas (6)
- Template-generated pages (3)
- SEO filler text (3)
- Merged table cells (3)
- AI-generated text (4, mostly unsure)
- Missing spaces between words (2)

Spec v1 also misses the following, although it has rules for them:

- C1 (69 docs)
- C2 (10)
- B5 (5)
- B4 (4)
- B1 (2)

## Files

- `reading_math-finemath_pyru.csv`: one row per finding (doc_id, code, kind, rule, offsets, source), with no doc text.
- The free-text notes stay on my machine, because some of them quote doc text.
