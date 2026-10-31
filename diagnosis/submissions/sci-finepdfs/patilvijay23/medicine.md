# Medicine sheet: sci-finepdfs — consolidated 500-row working version

> **Status: CONSOLIDATED REVIEW DRAFT; NOT FROZEN / NOT APPROVED FOR CLEANING.** All 500 `doc_id`s are represented once in pack order, but 107 records still have `read=partial`, including all 100 new rows 301–400. Do not call the file a completed human diagnosis or represent its medicines as harm-tested.

**Combined labels SHA-256:** `6c5071704ad10b1659c26580ca859825774f41d35f19b03843716b210762677e`.

**Scope and eligibility:** There is no cleaning proof in these labels. Licence eligibility, attribution, provenance and Team 9 decontamination are separate mandatory gates. Never remove licence/CC-BY-SA attribution as boilerplate. Preserve ZWJ/ZWNJ and long-context documents after safe fixes.

## Coverage and disease inventory

| Code | Full-read source diagnoses | All labelled/candidate rows | Consolidation decision |
|---|---:|---:|---|
| F1 | 101 | 102 | Full medicine; requires harm/positive-case validation |
| C2 | 44 | 45 | Full medicine; requires harm/positive-case validation |
| C1 | 25 | 26 | Full medicine; requires harm/positive-case validation |
| B5 | 18 | 18 | Full medicine; requires harm/positive-case validation |
| C3 | 7 | 13 | Full medicine; requires harm/positive-case validation |
| B2 | 10 | 10 | Full medicine; requires harm/positive-case validation |
| A6 | 9 | 9 | Full medicine; requires harm/positive-case validation |
| A1 | 8 | 8 | Full medicine; requires harm/positive-case validation |
| D3 | 7 | 7 | Full medicine; requires harm/positive-case validation |
| C4 | 4 | 6 | Provisional medicine; only exceeds five including partial rows |
| C5 | 1 | 3 | Below five full-read records — document-level handling only |
| D1 | 2 | 2 | Below five full-read records — document-level handling only |
| E4 | 2 | 2 | Below five full-read records — document-level handling only |
| A3 | 1 | 1 | Below five full-read records — document-level handling only |
| B3 | 1 | 1 | Below five full-read records — document-level handling only |
| B4 | 1 | 1 | Below five full-read records — document-level handling only |
| D4 | 1 | 1 | Below five full-read records — document-level handling only |

**Count caveat:** these are *reported label codes*, not independently verified disease prevalence. In particular, the 201–300 sheet uses F1 for names without reliable private-person evidence; automated 301–400 findings are preliminary. A document can count under multiple codes.

**Missing/invalid source labels:** physical row 162 has no earlier submission, five 201–300 fix/drop labels lacked any disease code, and three 101–200 `clean` rows erroneously carried D3. All were flagged and reconciled conservatively in the combined CSV; original source files remain unchanged. Details in the QA report.

---
## Medicine 1 — F1: Private-person information

1. **Disease:** **F1, 101 documents among existing full-read source labels, 102 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `b0d032fadb33dbf4` — individual direct telephone, offset 7697
   - `73fbd40e1111121e` — person-linked residential address, offset 386
   - `b44b092b0e829a12` — private direct telephone, offset 86

2. **Medicine:** Quarantine an F1 document unless every private-person span is verified and completely redacted; preserve public/institutional contacts. The first-100 corrected medicine is authoritative for its nine F1 IDs. The 201–300 sheet also marked many names as F1 without offsets; those are candidate labels, not independently verified private information.

**Proposed implementation / review-only helper:**

```python
def redact_approved_f1_spans(text, approved_spans):
    # Approved [start, end) Unicode-character spans, kept outside public repo.
    spans = sorted(approved_spans)
    if not spans:
        raise ValueError("No verified private spans; quarantine document")
    parts, cursor = [], 0
    for start, end in spans:
        if not (isinstance(start, int) and isinstance(end, int)
                and 0 <= cursor <= start < end <= len(text)):
            raise ValueError("Invalid, overlapping, or incomplete F1 span")
        original = text[start:end]
        parts.append(text[cursor:start])
        parts.append("[REDACTED_PRIVATE_DATA]" + "\n" * original.count("\n"))
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)
# Not a public one-argument cure_f1: only use after private-span approval.
```

3. **Action:** Fix via verified private-span redaction, otherwise quarantine/drop. Never copy private values to labels, logs, diffs or PR.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Overbroad phone/address patterns mask business, university and government contacts; inadequate span length leaves private data exposed. Do not treat a zero-change gold result as proof of F1 recall.

---

## Medicine 2 — C1: Publisher/page boilerplate or archive cover

1. **Disease:** **C1, 25 documents among existing full-read source labels, 26 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `33d1f7b3eec4d2c0` — publisher wrapper, offset 0
   - `a243639493a0e633` — publication footer, offset 86104
   - `bfbe6f0f5d61c19e` — editorial header, offset 3622

2. **Medicine:** Remove only confirmed extraneous material: an archive cover where the paper title reappears, site navigation, or repeated non-content footer. Preserve attribution, CC-BY-SA licence terms, author metadata and research structure. The Kunal2016 medicine has narrow HAL/City/MPRA markers; do not replace it with a blanket copyright-line removal.

**Proposed implementation / review-only helper:**

```python
import re
C1_COVER_END = re.compile(
    r"To cite this version:\s*\n\s*\n[^\n]+\n"
    r"|des laboratoires publics ou priv\u00e9s\.\s*\n"
    r"|Reuse: Copies of full items[^\n]*\n"
    r"|MPRA Paper No\. \d+, posted [^\n]*\n"
)
def cure_c1_archive_cover(text):
    # REVIEW BEFORE USE: possible source paper/attribution loss.
    matches = list(C1_COVER_END.finditer(text[:4000]))
    if not matches:
        return text
    rest = text[matches[-1].end():].lstrip("\n")
    return rest if len(rest) >= 1000 else text
```

3. **Action:** Fix verified external wrapper; otherwise keep.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Could remove scientific copyright/attribution, legal sections, publisher information, or actual footnotes. The broad copyright-line rule in the aneeshads reference is *not* approved as-is.

---

## Medicine 3 — C2: Nonstructural duplicated text

1. **Disease:** **C2, 44 documents among existing full-read source labels, 45 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `8c1aed2f8a439b91` — repeated lecture explanation, offset 6944
   - `3db737dca1122c53` — repeated outline, offset 1137
   - `0e4cfb3b81d67dc5` — fragment repetition, offset 2

2. **Medicine:** Remove only verified duplicate runs/pages with confirmed source boundaries. The reference medicine removes lines repeated >=4, but it also removed legitimate roll-call votes, form fields and recurring footnotes. Do NOT enable that broad rule without manual review and passing gold evidence.

**Proposed implementation / review-only helper:**

```python
def remove_verified_duplicate_spans(text, approved_spans):
    # Ranges may be approved only after inspection of the whole source.
    cursor, out = 0, []
    for start, end in sorted(approved_spans):
        if not 0 <= cursor <= start < end <= len(text):
            raise ValueError("Invalid duplicate span")
        out.append(text[cursor:start]); cursor = end
    out.append(text[cursor:])
    return "".join(out)
# Not an autonomous one-argument cure_c2.
```

3. **Action:** Fix verified duplicates; drop a source only if it consists entirely of unusable repeated fragments.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Repeated mathematical definitions, forms, statute subsections, survey options, table headings and recurring signatures can be legitimate. A duplicate count alone is not sufficient.

---

## Medicine 4 — C3: Truncated or incomplete source text

1. **Disease:** **C3, 7 documents among existing full-read source labels, 13 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `51a4fb599da754db` — opening fragment, offset 0
   - `6acc7c94105bdebd` — second report incomplete, offset 9393
   - `26a07693d706218f` — incomplete practice-exam question, offset 1085

2. **Medicine:** Locate a demonstrably missing beginning/end or clipped fragment by original text position. Recover missing material from the source where possible; else trim only the verified fragment, keeping the coherent document. Never infer C3 solely from FinePDFs `is_truncated=true` or from a valid excerpt.

**Proposed implementation / review-only helper:**

```python
def trim_verified_c3_tail(text, approved_end):
    if not isinstance(approved_end,int) or not 0 < approved_end <= len(text):
        raise ValueError("Source-confirmed end offset required")
    return text[:approved_end]
# Not an automatic truncation detector.
```

3. **Action:** Fix a source-confirmed incomplete boundary; drop only irreparable fragment-only documents.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Trimming may remove references, equations, appendices or legal language. Invented completions are unacceptable; preserve long-context materials.

---

## Medicine 5 — C4: Unrelated documents/content joined

1. **Disease:** **C4, 4 documents among existing full-read source labels, 6 including provisional candidates**; provisional review section (threshold reached only including partial candidates). Three traceable examples (IDs and positions only):
   - `6acc7c94105bdebd` — unrelated second section, offset 7254
   - `06b18306786f56a5` — unrelated inserted passage, offset 2482
   - `6af2bcb11b896884` — image-inpainting explanation joined to unrelated arts essay (row 335)

2. **Medicine:** Split at source-confirmed boundaries and retain a traceable source ID for each resulting segment; preserve both if usable, otherwise retain the coherent component. Do not split at natural multilingual passages, magazine article boundaries, lawful annexes or PDF page transitions.

**Proposed implementation / review-only helper:**

```python
def split_at_verified_c4_boundary(text, boundary):
    if not isinstance(boundary, int) or not (0 < boundary < len(text)):
        raise ValueError("Verified boundary offset required")
    return text[:boundary], text[boundary:]
# Return both with provenance; no automatic one-argument cure.
```

3. **Action:** Fix by reviewed split/trim; drop unrepairable contamination.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Automatic topic-switch rules split legitimate technical reports and mixed-language documents. Source provenance can be lost.

---

## Medicine 6 — B2: Literal HTML/XML tags in extracted prose

1. **Disease:** **B2, 10 documents among existing full-read source labels, 10 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `7ea84af3398cb3ed` — literal break tag, offset 445945
   - `8854bf31b8eea361` — superscript markup, offset 6674
   - `aa241f145eca058d` — superscript markup, offset 39648

2. **Medicine:** Convert only HTML fragments that are clearly extraction artifacts, such as verified `<br>` in running prose or explicit superscript markup. Preserve maths, code samples and genuine tags in quoted technical material.

**Proposed implementation / review-only helper:**

```python
import re
def cure_b2_verified_br(text):
    # Candidate for reviewed prose only, not for code or tables.
    return re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
# Require independent positive-case inspection + official gold test.
```

3. **Action:** Fix only verified tags.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Removing tags broadly damages technical documentation and formulae; replacing `<br>` with a semicolon may join unrelated list items.

---

## Medicine 7 — B5: Broken Markdown or LaTeX

1. **Disease:** **B5, 18 documents among existing full-read source labels, 18 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `80c340aef304a24c` — LaTeX footnote wrapper, offset 21835
   - `d7a3e129dcd9c041` — footnote wrapper, offset 2392
   - `ae0c958288200e55` — footnote wrapper, offset 4087

2. **Medicine:** A source reference proposes changing LaTeX `\footnote{...}` wrappers into readable parenthesized footnotes, with brace balancing. A bare inline math command, valid LaTeX footnote, table or code block is not automatically broken: only transform confirmed extraction damage.

**Proposed implementation / review-only helper:**

```python
def cure_b5_reviewed_footnotes(text):
    out, i = [], 0
    marker = "\\footnote{"
    while True:
        j = text.find(marker, i)
        if j < 0:
            out.append(text[i:]); return "".join(out)
        out.append(text[i:j]); k=j+len(marker); depth=1
        while k < len(text) and depth:
            if text[k] == "{" and (k == 0 or text[k-1] != "\\"):
                depth += 1
            elif text[k] == "}" and (k == 0 or text[k-1] != "\\"):
                depth -= 1
            k += 1
        if depth:
            # Unsafe to guess the missing end: leave source intact.
            out.append(text[j:]); return "".join(out)
        out.append(" (" + text[j+len(marker):k-1].strip() + ")")
        i=k
```

3. **Action:** Fix verified broken markup; otherwise retain genuine maths and LaTeX.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Overcorrection can change equations, real TeX examples, bibliography anchors and footnotes. Many flagged B5 cases in the 101–200 reference were deliberately left unchanged.

---

## Medicine 8 — A1: Invisible junk characters

1. **Disease:** **A1, 8 documents among existing full-read source labels, 8 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `b64c51d59247a36c` — variation selector near offset 92911 — verify whether genuinely junk
   - `d5f88477e272bd7c` — variation selector near offset 1606
   - `78687cb0dc7a4f80` — variation selector near offset 398301

2. **Medicine:** Allow only tightly-scoped removal of verified U+200B / BOM U+FEFF / problematic controls. Retain **ZWJ U+200D and ZWNJ U+200C**. Do not blindly erase emoji U+FE0E/U+FE0F as it changes presentation.

**Proposed implementation / review-only helper:**

```python
def cure_a1_verified_junk(text):
    # Conservative: do not include U+200C, U+200D, U+FE0E, U+FE0F.
    return text.replace("\uFEFF", "").replace("\u200B", "")
```

3. **Action:** Fix verified invisible junk without removing Indic shaping marks.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Even invisible characters may have formatting significance; global removal of variation selectors changes emoji and symbol rendering.

---

## Medicine 9 — A6: Wrong/mixed script in a word

1. **Disease:** **A6, 9 documents among existing full-read source labels, 9 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `f5faeb5d20b73087` — CJK character embedded in Latin word near offset 11498
   - `12e943fb710cab5b` — CJK run embedded in Latin word near offset 882
   - `6324a2bb8fae9275` — Greek scientific notation reported but should be preserved

2. **Medicine:** The 101–200 reference proposes Latin/Cyrillic transliteration and small CJK-run deletion, but warns that it may corrupt names or words and should preserve Greek scientific notation. Use human-approved codepoint substitutions only.

**Proposed implementation / review-only helper:**

```python
def replace_verified_codepoint_spans(text, replacements):
    # Sequence of human-approved (start, end, new_string) operations.
    cursor, out = 0, []
    for start, end, new in sorted(replacements):
        if not 0 <= cursor <= start < end <= len(text):
            raise ValueError("Bad Unicode replacement span")
        out.extend((text[cursor:start], new));cursor=end
    return "".join(out)+text[cursor:]
```

3. **Action:** Fix verified character confusables; otherwise keep scientific/quoted script.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Generic transliteration produces incorrect names and deletes source information. No script-change rule is approved for automatic release.

---

## Medicine 10 — D3: Natural or unintended mixed language

1. **Disease:** **D3, 7 documents among existing full-read source labels, 7 including provisional candidates**; full medicine (reported >5 full-read diagnoses). Three traceable examples (IDs and positions only):
   - `bfbe6f0f5d61c19e` — natural English/German passage, offset 6897
   - `f26a6a8bd745c1a2` — foreign institution name in otherwise valid source
   - `19c895320632e7b0` — Amharic/English bilingual prescription forms (row 366)

2. **Medicine:** Protect natural code-mixing and multilingual quotations; do not drop science PDFs simply for Spanish institution names, Chinese tables or English/local-language summaries. The reference D3 heuristic dropping texts with >50% non-English paragraphs is NOT accepted without human source-language review.
   **No automatic executable cure** is proposed; this is a keep/verify policy.

3. **Action:** Keep valid multilingual content. Drop only separately verified wrong-language source via D1 decision.

4. **Harm test:** **NOT RUN on the current verified gold set.** Older per-contributor results are historical and cannot certify the combined rule. The TSAI current acceptance threshold is `changed + dropped <= max(1, floor(0.01 * n))`; `n=0` is `NOT TESTABLE`, exit code 2. Validate the selected rule against disease-positive rows and refreshed pack gold before promotion.

5. **Side effects:** Word-list or script-share detectors misclassify untranslated quotations, code, named entities, linguistic studies and bilingual forms.

---

## Other low-count codes and cross-cutting safeguards

Codes not meeting the >5 fully reviewed document threshold are retained as **document-level findings, not automatic general cures**:

- **D1 (2 full-read; 2 total)** — Incorrect language label; verify dominant language and true source metadata before dropping. Two corrected first-100 foreign-language records are tagged drop; genuine multilingual texts are not automatically D1.
- **C5 (1 full-read; 3 total)** — SEO/book-download keyword/link spam. Source row 313 and 372 are clear preliminary candidates; require human confirmation before final drop. Do not drop catalogs or real references just for links.
- **E4 (2 full-read; 2 total)** — Repeated licence headers from code taxonomy; preserve copyright/reuse obligations, do not strip source attribution, and decide source eligibility independently.
- **B3 (1 full-read; 1 total)** — Ghost chat marker; high risk despite low count. Detect exact model-control tokens without deleting legitimate quotes.
- **B4 (1 full-read; 1 total)** — Template/code junk in prose; distinguish valid configuration examples and forms before treating as corruption.
- **A3 (1 full-read; 1 total)** — Mojibake; repair only when byte-faithful reversible mapping is established; log original byte positions, do not guess language.
- **D4 (1 full-read; 1 total)** — Bad machine translation; requires bilingual human review; do not rely on automatic grammar score.

**H2/H3 duplicate detection** is an independent dedup design and cannot be inferred from within-document repeated lines. **F2 benchmark contamination** needs Team 9 benchmark fingerprints, and is not certified absent by this label exercise.

## Exact safeguards carried forward from the first-100 reference

- Keep the four first-100 drop IDs exactly as diagnosed: `eee25e81417bc1b7`, `26a07693d706218f`, `0e4cfb3b81d67dc5`, `44f66c3734e3d5ca` (subject to the later gold conflict noted below). None is a corrected-first-100 F1 drop.
- The corrected first-100 review reports **22 non-dropped long-context candidates**, flagged `Long-context candidate — use for long context`. Keep coherent extended text after approved repairs; length alone is not a disease.
- F1 requires exact verified sensitive spans and complete privacy recall. Names, public government offices, professional correspondence, example domains and public organization contacts are not automatically private-person F1.
- Keep mathematics, scientific Greek notation, legitimate LaTeX, formula tables, repeated legal clauses, natural bilingual text, page numbering, and repeated form fields unless actual corruption is substantiated.
- Do not collapse `fix`/`drop` into success: proposed actions require an executed rule, a separate positive-case effectiveness check and an approved gold harm test.

## Current harm-test and Gate 2 status

- **No new harm-test PASS is claimed for this combined medicine.** The earlier aneeshads reference describes a 26-document gold set with a stricter zero-change rule; TSAI has since adopted `max(1 document, floor(1% of n))`.
- The checked `g1-harm-test` branch gold set has 40 rows. It includes first-100 ID `eee25e81417bc1b7`, which the corrected source labels `drop`; treat this as **gold contamination/dispute pending refresh**.
- Rules requiring manual/approved source boundaries are intentionally *not* one-argument `cure_*` rules, to avoid generating a false PASS from a no-op or unverified mutation.
- After completing the 107 partial rows and adjudicating conflicting source labels, regenerate gold sets from current submissions, resolve all rule clashes, test each executable rule and record gold IDs affected, counts, code hashes and provenance in `spec_v1/harm_tests.md`.
- For release: preserve ZWJ/ZWNJ; licence gate accepts permissive and CC-BY-SA with attribution and allowed gpt-oss outputs, rejects NC/ND/unstated/untraceable and disallowed closed-model text.

## Reference provenance

- `labels(9).csv` SHA-256 `9d7bd631831e3efc0f28740d874321179c4720b04ea3f2da0d1db5cc3e988812`.
- `medicine(10).md` SHA-256 `a8ee7b8075e6f215ee469a8e904ed45d1665d0c1e0889f3b965ab4e349304dbe`.
- `sci-aneeshads-medicine.md` SHA-256 `e6601ebcee836fae2d673a1f0a8e308116d0037cf0f65b4226eaaccaa97b2a6d`.
- `sci-kunal2016-medicine.md` SHA-256 `379118e078cfa3235ef4ab9b825e437adaec8efded755ea90e248b9ebc7511ed`.
- `sci-aneesha-labels.csv` SHA-256 `8e2a6b569618caa16af33899f269a2a644eaa3f32008332bad9eb7686697e458`.
- `sci-smita-labels.csv` SHA-256 `99d5e835837472f72a4180d53765ce9e57b2dc40a8549bb6deba2e472daeafcd`.
- `sci-kunal2026-labels.csv` SHA-256 `769cd7026ebaebaa83c83ab6323a6762bc4db0a5949598083d88e02e91662a6b`.

**Finalization gate:** This draft consolidates the available sources and recommendations, but is **not yet a final approved medicine** until pending document-level diagnosis and current harm tests are complete.
