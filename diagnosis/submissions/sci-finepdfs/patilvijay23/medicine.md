# Medicine sheet: sci-finepdfs (patilvijay23)

**Source:** `labels.csv`, the corrected first 100 records of `sci-finepdfs.parquet` (physical rows 1–100 in pack order). **100 distinct documents, all marked `read=full`: 77 `clean`, 19 `fix`, 4 `drop`.** These counts come from the corrected labels, not the superseded initial scanner annotations.

**Labels SHA-256:** `9d7bd631831e3efc0f28740d874321179c4720b04ea3f2da0d1db5cc3e988812`

**Scope.** In accordance with `medicine_TEMPLATE.md`, make a complete medicine section for any disease that occurs in **more than five documents**. Here **F1 (9 documents)** is the only disease above the threshold. Other observed conditions are documented in the below-threshold handling guide so their actions are not lost. A document may have more than one disease.

**Status:** **LABEL REVIEW COMPLETE — harm testing and cleaning execution not supplied.** The 100 verdicts represent required handling; they do not establish that transformations have been applied or that a gold-set harm test passed.

## Disease coverage from the final 100 labels

| Disease | Documents | `fix` | `drop` | Handling |
| --- | ---: | ---: | ---: | --- |
| F1 — private-person information | 9 | 9 | 0 | **Full medicine**: privacy-gated redaction |
| C1 — publisher / page boilerplate | 5 | 5 | 0 | Targeted removal only; below threshold |
| C4 — unrelated content joined | 4 | 2 | 2 | Verified split/trim or drop; below threshold |
| C2 — duplicated content | 3 | 2 | 1 | Verified nonstructural deduplication or drop; below threshold |
| C3 — incomplete source text | 3 | 2 | 1 | Source-boundary repair or drop; below threshold |
| D1 — incorrect language label | 2 | 0 | 2 | Drop these two contaminated records; below threshold |
| B2 — literal markup in prose | 1 | 1 | 0 | Repair verified HTML line-break artifact; below threshold |
| D3 — natural code-mixing | 1 | 1 | 0 | Preserve valid bilingual content; below threshold |

The four existing `drop` document IDs are `eee25e81417bc1b7`, `26a07693d706218f`, `0e4cfb3b81d67dc5`, and `44f66c3734e3d5ca`. **None is an F1 drop.**

---

## Medicine 1 — F1: private-person information

1. **Disease:** **F1 in 9 distinct documents** (all `fix`). Private-person contact or residential details appear within otherwise usable records. Three examples from the reviewed labels:
   - `b0d032fadb33dbf4`: an **individual's direct telephone**, starting at zero-based Python character offset **7697**.
   - `73fbd40e1111121e`: a **person-linked residential address**, starting at offset **386**.
   - `b44b092b0e829a12`: a **private direct telephone**, starting at offset **86**.

   The other F1 IDs are `854af92dbde41a63`, `fb2ef557617d7ad1`, `d1a387dea20a1242`, `3b215cb29425e7d6`, `8c2c1359b53f9442`, and `a6e70d0fef431172`.

   **Privacy exception to the template's request for exact-character examples:** Do not reproduce the sensitive telephone numbers, residential addresses or other private values in this public medicine, its rule code, logs, diffs or PR. Use **type + document ID + starting offset** as safe evidence. The stored offset alone does *not* give the full end boundary for redaction.

2. **Medicine:** Find the **full start/end span of every verified private value** in the *unchanged source text*, using a protected verification workflow. Redact only those spans and preserve the surrounding document. Do not automatically classify public agency switchboards, business addresses, law-firm and academic correspondence details, or example-domain addresses as private-person data. The corrected label audit specifically removed those false positives.

   The following Python helper performs **replacement only after the sensitive spans have been accurately verified**. It is *not* a private-data detector or a one-argument, automatically loadable `cure_f1` rule. Approved spans must be maintained separately from the public medicine and must refer to zero-based offsets in the original source string.

   ```python
   def redact_approved_f1_spans(text, approved_spans):
       '''Replace complete, verified [start, end) Unicode-character spans.

       approved_spans must cover EVERY verified private value in this document.
       Do not use an empty or unverified list to release an F1 document.
       '''
       spans = sorted(approved_spans)
       if not spans:
           raise ValueError('F1 document has no approved redaction spans')

       cursor = 0
       pieces = []
       for start, end in spans:
           if not isinstance(start, int) or not isinstance(end, int):
               raise TypeError('F1 span offsets must be integers')
           if not (0 <= cursor <= start < end <= len(text)):
               raise ValueError('Invalid, overlapping or out-of-range F1 span')
           pieces.append(text[cursor:start])
           private_segment = text[start:end]
           pieces.append('[REDACTED_PRIVATE_DATA]' +
                         '\n' * private_segment.count('\n'))
           cursor = end
       pieces.append(text[cursor:])
       return ''.join(pieces)
   ```

   **Release gate:** For any F1 document, identify and approve *all* private spans before release; verify the redacted result contains no remaining sensitive values. If completeness cannot be established or the document cannot be safely redacted, **quarantine/drop it**. Do not silently return the original text or let a no-op stand in for privacy protection.

3. **Action:** **Fix** each of the nine F1 records by verified selective redaction, keeping public substantive content. Quarantine/drop only if complete and source-faithful redaction cannot be assured. This fallback does not modify the existing reviewed nine `fix` verdicts. Three F1 records are also marked as long-context candidates — `73fbd40e1111121e`, `d1a387dea20a1242`, `a6e70d0fef431172` — and their coherent long-form text should be preserved after redaction.

4. **Harm test:** **Not run; no result supplied.** This section intentionally has **no `cure_f1(text)`** for a one-argument rule loader: the labels provide starting offsets, not complete, safe redaction boundaries. Once approved spans are supplied through a protected workflow, test (a) **privacy recall** on all affected F1 examples and (b) collateral changes/drops on the official `sci-finepdfs` gold set. Record gold document count, IDs changed/dropped, affected percentage and the executable code hash. Per the assignment, **a rule affecting more than 1% of gold documents fails**. A no-op, an unloaded rule, or a rule that matches nothing is *not* evidence of effective redaction or a measured PASS.

5. **Side effects:** Overbroad phone/address regexes erase legitimate professional or institutional content; narrow matching misses multiple sensitive fields. Text around an address or phone number may identify a person even after a partial replacement. Incorrect offsets may delete ordinary prose or leave private data exposed. The helper guards span validity but **does not** prove detection completeness; that requires a separate privacy audit.

---

## Below-threshold handling guide (not additional general medicines)

The following codes occur **at most five times** in the reviewed sample. They are documented for operational completeness, but there is insufficient evidence here to promote a broad dataset-wide automatic cure for any of them. Their document-level `fix`/`drop` labels remain valid.

### C1 — publisher and page boilerplate (5 documents)

**Examples:** `33d1f7b3eec4d2c0` (publisher wrapper at offset **0**); `a243639493a0e633` (publication footer at **86104**); `bfbe6f0f5d61c19e` (repeated editorial header at **3622**). **Action:** `fix`, removing only verified extraneous wrappers, repeated editorial material or footer content while preserving the actual article/report. **Risk:** Legitimate publication notices, law/report structure, bibliographies, tables of contents and repeated slide/page headings are not automatically C1; avoid blanket deletion.

### C4 — unrelated content joined (4 documents)

**Examples:** `6acc7c94105bdebd` (unrelated section near **7254**); `06b18306786f56a5` (unrelated inserted passage near **2482**); `eee25e81417bc1b7` (unrelated image narration near **1286**). **Action:** two `fix` documents require a verified boundary/split or removal of the unrelated insertion. The two `drop` documents are `eee25e81417bc1b7` and `44f66c3734e3d5ca`. **Risk:** Interviews, normal PDF page transitions, quotations or valid multilingual sections must not be split on superficial text similarity or language switches. Preserve document provenance.

### C2 — duplicate content (3 documents)

**Examples:** `8c1aed2f8a439b91` (repeated lecture explanation near **6944**); `3db737dca1122c53` (repeated outline near **1137**); `0e4cfb3b81d67dc5` (repeated fragment labels near **2**). **Action:** two `fix` documents need removal of *confirmed nonstructural* duplicates; one fragment-only document is `drop`. **Risk:** Normal tables, repeated section headings, equations, legal numbering, slide titles and literary repetition must be retained unless verified to be duplicative corruption.

### C3 — incomplete or truncated source (3 documents)

**Examples:** `51a4fb599da754db` (opening fragment at **0**); `6acc7c94105bdebd` (incomplete second report near **9393**); `26a07693d706218f` (practice-exam extract ends mid-question near **1085**). **Action:** two `fix` documents require verified source-boundary repair or selective removal of the incomplete fragment; the exam extract is `drop`. **Risk:** Source metadata `is_truncated=true` was observed broadly across this pack and **is not proof of C3** by itself. Do not fabricate missing prose or drop coherent excerpts solely because a flag is set.

### D1 — incorrect language label (2 documents)

**Examples:** `eee25e81417bc1b7` contains Finnish source slides under `eng_Latn` beginning at **0**; `44f66c3734e3d5ca` contains Latvian source text under `eng_Latn` beginning at **0**. Both also have C4 contamination. **Action:** `drop` these two records under their reviewed labels. **Risk:** A bilingual quotation or multilingual academic material in an otherwise valid document is not, by itself, a wrong-language-label defect.

### B2 — literal HTML markup in extracted prose (1 document)

**Example:** `7ea84af3398cb3ed`, literal `<br>` beginning at offset **445945**. **Action:** `fix` the verified line-break artifact while retaining neighboring prose. **Risk:** HTML-like strings may be intentionally quoted source, code or technical notation; do not replace all angle brackets or markup throughout the pack.

### D3 — natural code-mixing (1 document)

**Example:** `bfbe6f0f5d61c19e`, normal English–German mixture near **6897**, with a separate C1 page-header defect at **3622**. **Action:** Preserve the natural mixed-language passage; repair C1 only. **Risk:** A no-op for D3 should not be counted as an effective cleaning operation or used to justify an unrelated `fix` mutation.

**Overlaps requiring care:** `8c1aed2f8a439b91` has C1 and C2; `6acc7c94105bdebd` has C3 and C4; `bfbe6f0f5d61c19e` has C1 and D3. Handle each supported defect independently; one disease code does not authorize deleting every matching span in a multi-disease document.

---

## General-purpose PDF safeguards and long-context policy

- **Respect reviewed document types.** The pack contains research papers, legal documents, public meeting minutes, regulatory forms, textbooks, product specifications, certificates, catalogues and historical prose. Neither short length nor non-science topics alone constitute an ERA V5 disease.
- **Preserve legitimate structure.** Tables of contents, table/figure headings, recurring form fields, mathematical and LaTeX notation, citations, copyright statements, professional business contacts and public institutional addresses are not automatically corruptions. Do not broadly map these to C1/C2/B2/F1.
- **Preserve long-context candidates.** **22 non-dropped documents** contain `Long-context candidate — use for long context` in the `note` field. Preserve their coherent extended spans after any documented fixes; do not impose an indiscriminate length cap. The tag is a selection candidate, not a claim of training-quality certification.
- **Privacy first.** All nine F1 fixes require fully verified private-span coverage prior to releasing cleaned source text; keep sensitive values out of GitHub, logs and public review artifacts.
- **Do not conflate labels with cleaning.** All 100 records are fully reviewed; their verdicts do not imply actual cleaning has happened. Retain the reviewed `77 clean / 19 fix / 4 drop` distribution unless a separately documented relabeling task changes it.

## Harm-test and release status

**No sci-finepdfs gold-set harm-test command or result was supplied.** In particular, the previously shared PASS for `ind-mr-sangraha-v` is for a *different pack* and does **not** validate these PDF operations. No gold count, code hash, affected percentage, or PASS is asserted here.

The only above-threshold medicine, F1, deliberately lacks an automatically loadable `cure_f1(text)` because its release-safe operation requires separately verified private spans. A `harm_test.py` warning about F1 having no one-argument function is therefore **expected and must not be represented as a PASS**. Do not treat a zero-change gold report as evidence of privacy recall.

**Release checklist:** Enforce the four reviewed drop verdicts; complete and verify all F1 redactions in the nine `fix` records; apply only source-confirmed C1/C2/C3/C4/B2 repairs; preserve D3 and all 22 long-context candidates subject to privacy safety; independently test any new deterministic rule on its disease-positive examples and official gold documents; record the exact command, pack/rules/gold hashes, changed/dropped IDs and results.

**Interpretation:** The 100 source records have completed *label* review. They have **not** supplied a measured gold-set PASS, a generally safe executable F1 detector, or proof that cleaned output has been produced.
