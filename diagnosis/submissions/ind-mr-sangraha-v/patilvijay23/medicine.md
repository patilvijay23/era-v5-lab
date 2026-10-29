# Medicine sheet: ind-mr-sangraha-v (patilvijay23)

**Source:** `labels.csv`, **252 distinct documents** (246 marked `full`, 6 `partial`; 45 `clean`, 190 `fix`, 17 `drop`). This updates the earlier medicine sheet based on 100 documents. Disease counts below are document counts, not the number of character occurrences; a document can have multiple diseases. Each disease appearing in **more than five** labelled documents has a section. The six `partial` records require a complete review before their diagnoses and verdicts are treated as final.

**Status:** **DRAFT — harm testing pending.**

## Disease coverage from the supplied labels

| Disease | Documents | Proposed handling |
| --- | ---: | --- |
| A5 | 111 | Executable NFC normalization candidate |
| D3 | 72 | Preserve natural code-mixing; explicit no-op |
| C1 | 52 | Narrow publisher/related-content boilerplate removal |
| C2 | 51 | Conservative exact lead duplication removal |
| A6 | 24 | Repair mixed-script **numeric tokens only**; other cases need review |
| C3 | 11 | **Manual:** incomplete/truncated document; no generic rewrite |
| D4 | 9 | **Manual:** severe bad translation; review/drop as labelled |
| F1 | 9 | **Manual privacy gate:** redact or exclude without exposing private values |
| B4 | 7 | Convert literal `\n` escape sequences in prose only |
| C4 | 6 | **Manual:** split verified joined documents or drop |
| C5 | 6 | Remove high-confidence standalone tag-list lines; otherwise review |

**Below the medicine threshold:** G1 (3 documents: detached Indic marks; manually inspect, never globally delete spaces); B5 (1 document: broken Markdown blockquote marker). These still need review but have no medicine section under the more-than-five rule.

**Suggested order for independently approved fixes:** B4 → A5 → narrowly scoped A6 → C1 → C5 → C2. D3 is a no-op. C3, C4, D4 and F1 are manual gates, **not** executable medicine candidates. This order is a proposal, not a harm-tested or approved combined pipeline.

---

## Medicine 1 — A5: wrong Unicode normal form

1. **Disease:** A5, **111 documents**. Decomposed Devanagari forms whose NFC normalization changes the code-point sequence. Examples from the labels:
   - `4884f7c293a7beab`: `ऱ` at offset 2437 → NFC `ऱ`.
   - `47594b68339a08b9`: `ऴ` → NFC `ऴ`.
   - `038ffeeda8d9dca7`: `ऱ` at offset 68 (5 occurrences) → NFC `ऱ`.

2. **Medicine:** Normalize the text to NFC. Do **not** use NFKC or change Indic digits, ZWJ or ZWNJ.

   ```python
   import unicodedata

   def cure_a5(text):
       return unicodedata.normalize("NFC", text)
   ```

3. **Action:** Fix by NFC normalization only; it does not override a document-level `drop` decision for other diseases.

4. **Harm test:** **Pending** on the actual Marathi gold set. Record changed/dropped gold IDs and percentages; PASS only at ≤1% affected.

5. **Side effects:** NFC changes code-point sequences and may invalidate offsets; NFC does **not** reconnect a detached matra/virama, repair OCR errors, or fix severe structural corruption. Count actual changes in the harm test rather than presuming they are harmless.

## Medicine 2 — D3: natural mixed-language content

1. **Disease:** D3, **72 documents**. Natural Marathi mixed with English names, titles, technical words, or Sanskrit quotations. Examples:
   - `870f3c12624cc486`: `UPSC` near offset 1172.
   - `31e2deeb3fd7a6f3`: `Karjat Nagar Panchayat Election` near offset 200.
   - `8344f9091076fadd`: English phrase `The question is will he get` near offset 866.

2. **Medicine:** Preserve the text. Mixed language alone is **not** evidence that the document is damaged.

   ```python
   def cure_d3(text):
       return text
   ```

3. **Action:** Keep unchanged for D3. Apply separate, independently tested medicines if the same document also has another disease. Some D3-only records carry a `fix` verdict in the input labels; those verdicts merit reconciliation because this medicine intentionally makes no change.

4. **Harm test:** A no-op has **0 changed and 0 dropped documents by construction**; this is not an empirical gold-set result and does not establish effectiveness. Gold-set audit remains pending for all other candidate rules.

5. **Side effects:** No direct mutation. The risk is *over-cleaning by other medicines*: an English name, English headline, or Sanskrit quotation is not necessarily C1/C5 boilerplate or A6 corruption.

## Medicine 3 — C1: publisher/navigation boilerplate

1. **Disease:** C1, **52 documents**. Publisher promotions, unrelated navigation, login/footer prompts and related-story notices. Examples:
   - `2c66d24bfd6db2ef`: related-story marker `हे ही वाचाः` near offset 1082.
   - `e14f9a0e6e8d1d9b`: English publisher promotion near offset 741 and Marathi follow prompt near offset 972.
   - `038ffeeda8d9dca7`: social-media/source navigation near offset 1312 (`साम आता सर्व सोशल मीडिया`).

2. **Medicine:** Remove only full lines starting with clearly identified navigation/related-story/promo phrases; do not delete text just because it is in English. Keep line endings stable and avoid deleting partial sentence matches.

   ```python
   import re

   _C1_LINE = re.compile(
       r"^\s*(?:"
       r"हे\s*ही\s*वाचा\s*[:ः]?.*"
       r"|हेही\s*वाचा\s*[:ः]?.*"
       r"|हे\s*देखील\s*वाचा\s*[:ः]?.*"
       r"|Read\s+Also\s*[:\-]?.*"
       r"|Keep\s+Reading\s*[:\-]?.*"
       r"|Forgot\s+your\s+password\??\s*.*"
       r"|Home\s*/\s*Marathi\s*"
       r"|Get\s+Latest\s+Marathi\s+News.*"
       r"|साम\s+आता\s+सर्व\s+सोशल\s+मीडिया.*"
       r")\s*$",
       flags=re.IGNORECASE,
   )

   def cure_c1(text):
       lines = text.splitlines(keepends=True)
       return "".join(
           line for line in lines
           if not _C1_LINE.fullmatch(line.rstrip("\r\n"))
       )
   ```

3. **Action:** Fix only matching boilerplate lines. A `drop` verdict remains if no coherent article survives.

4. **Harm test:** **Pending.** Test against gold documents, inspect every removed line, and verify ≤1% changed/dropped before considering approval.

5. **Side effects:** Some genuine article text could begin with one of the listed phrases, and boilerplate embedded mid-paragraph is intentionally not removed. This rule is conservative; manual review is needed for more complex cases.

## Medicine 4 — C2: exact repeated lead/content

1. **Disease:** C2, **51 documents**. Duplicate titles, lead paragraphs, or repeated article snippets. Examples:
   - `4884f7c293a7beab`: opening paragraph repeats at offsets 0 and 316.
   - `948113e0495d4af9`: opening text repeats at offsets 0 and 122.
   - `9532c5c8c0d27ac4`: lead/title repeats at offsets 0 and 114.

2. **Medicine:** Remove only a **long, exact** second copy of the document's opening content if it occurs near the beginning; do not perform global line deduplication, fuzzy matching, or removal of legitimate refrains.

   ```python
   def cure_c2(text):
       seed_len, min_repeat, search_limit = 48, 80, 1600
       if len(text) < min_repeat * 2:
           return text
       seed = text[:seed_len]
       second = text.find(seed, seed_len, min(len(text), search_limit))
       if second < 0:
           return text
       matched = 0
       max_match = min(second, len(text) - second)
       while matched < max_match and text[matched] == text[second + matched]:
           matched += 1
       if matched < min_repeat:
           return text
       return text[:second] + text[second + matched:]
   ```

3. **Action:** Fix only verified exact repeated prefixes, keeping the first occurrence. Review other C2 variants manually.

4. **Harm test:** **Pending.** Include examples of legitimate repeated prose in gold and measure changed/dropped gold IDs (≤1% threshold).

5. **Side effects:** Repeated opening text may be intentional (poetry, quotations, structured articles). The strict rule misses shorter duplicates and OCR-altered copies, which is preferable to deleting uncertain content. Check the resulting join around the removed span.

## Medicine 5 — A6: wrong or mixed script

1. **Disease:** A6, **24 documents**. A heterogeneous collection including corrupted mixed digits, hyphenated Marathi words, intruding Latin characters, and a stray non-Devanagari symbol. Examples:
   - `4884f7c293a7beab`: mixed digits `१0७`, `१0`, `३0` at offsets 1900, 1909 and 1951.
   - `e71787a3124f9007`: Marathi word fragments `चेह-याच्या` (offset 506) and `ब-याच` (offset 833).
   - `208b033cb8584898`: stray `U+00BA` inside a Marathi word near offset 787 (2 occurrences).

2. **Medicine:** **Automate only one narrow subtype:** replace ASCII digits inside a contiguous token containing both ASCII and Devanagari digits. Hyphen, stray `U+00BA`, Latin-character intrusion, standalone ASCII digits, and other A6 cases need separate context-aware decisions.

   ```python
   import re

   _A6_MIXED_DIGITS = re.compile(r"[०-९0-9]+")
   _A6_DIGIT_MAP = str.maketrans("0123456789", "०१२३४५६७८९")

   def cure_a6(text):
       def convert(match):
           token = match.group()
           if re.search(r"[०-९]", token) and re.search(r"[0-9]", token):
               return token.translate(_A6_DIGIT_MAP)
           return token
       return _A6_MIXED_DIGITS.sub(convert, text)
   ```

3. **Action:** Fix the mixed-digit subtype only; flag the remaining A6 occurrences for manual review or future separately tested medicines.

4. **Harm test:** **Pending.** Verify on the gold set that mixed-script numbers are actually unwanted, and record changed/dropped gold counts (≤1%).

5. **Side effects:** Even mixed-script digits can occasionally be deliberate; global Latin removal, blanket hyphen replacement, or indiscriminate `U+00BA` substitution would risk damaging legitimate names and D3 code-mixing.

## Medicine 6 — B4: literal escaped newline in prose

1. **Disease:** B4, **7 documents**. A literal backslash followed by `n` occurs where a line boundary is intended. Examples:
   - `5cd1cc2146075a9f`: literal `\n` near offset 81 (3 occurrences).
   - `09f78635c7686fd8`: literal `\n` near offset 14 (11 occurrences).
   - `8f3c76c4c4ad8584`: literal `\n` near offset 109 (13 occurrences).

2. **Medicine:** Convert the literal two-character sequence `\n` to a newline **only for this identified prose subtype**. Run before line-based C1/C5/C2 cleaning.

   ```python
   def cure_b4(text):
       # Conservative gate for recurring escaped newlines in the Marathi prose pack.
       if text.count("\\n") < 3:
           return text
       return text.replace("\\n", "\n")
   ```

3. **Action:** Fix escaped newlines when they recur as prose formatting artifacts.

4. **Harm test:** **Pending.** Test on the Marathi gold set and inspect any changed gold record; PASS requires ≤1% affected.

5. **Side effects:** Technical quotations can legitimately include `\n`. The recurrence threshold reduces but does not eliminate that risk. Other escaped control sequences are left untouched.

## Medicine 7 — C3: incomplete or truncated document

1. **Disease:** C3, **11 documents**. Text starts or stops mid-sentence, or page-continuation artifacts interrupt it. Examples:
   - `7ac16bc32542abcd`: incomplete ending near offset 1203.
   - `8acc240b173977d0`: incomplete beginning at offset 0 and page-continuation artifacts.
   - `177179a646864418`: incomplete ending near offset 824 (`चांगले निर्णय`).

2. **Medicine:** **Manual/review-only.** Verify the source boundary and either restore the missing text, trim the demonstrably incomplete fragment while preserving a coherent document, or exclude the document. A universal regex cannot reliably infer the original sentence or detect all truncated Marathi prose. **No executable Python medicine is proposed.**

3. **Action:** Fix only with verified source/boundary; **drop** when no coherent content remains (as in `0ad004d5deb1e7fe`, labelled `drop`).

4. **Harm test:** **Not run; no executable candidate.** Once a safe, deterministic repair is proposed, evaluate it against gold before approval. A manual review outcome is not a programmatic harm-test PASS.

5. **Side effects:** Trimming near punctuation can remove legitimate text; generating a missing ending would invent content. Some incomplete-looking passages are intentional excerpts.

## Medicine 8 — D4: severely unnatural machine translation

1. **Disease:** D4, **9 documents**. Broken literal translation, unnatural Marathi grammar, or extensive semantically corrupted wording. Examples:
   - `61b2c25e9513730b`: broken translated phrasing near offset 2793 (`काय माजी कर्मचारी किराणा दुकान...`).
   - `866b1853d8a9d95a`: severely unnatural text from offset 0.
   - `43785419033933e9`: severely unnatural translated phrasing from offset 0.

2. **Medicine:** **Manual/review-only.** For the attached records, all nine D4-labelled documents carry `drop`. Do not attempt word-by-word regex "repair" or machine-generate a replacement training document. Where warranted, review a trusted original source and label again. **No executable Python medicine is proposed.**

3. **Action:** **Drop** the confirmed heavily corrupted documents; `partial` documents (`9e41a5d56ac92089`, `f94044ff48697280`) require full review before final sign-off.

4. **Harm test:** **Not run; no executable candidate.** Any future automatic D4 detector/dropper needs independent gold-set evaluation and ≤1% affected-gold validation.

5. **Side effects:** Unusual idioms, literary style and natural code-mixing could be mistaken for bad translation. Avoid applying a broad language-quality classifier without validation.

## Medicine 9 — F1: private-person information

1. **Disease:** F1, **9 documents**. Private residential locations, personally linked addresses or contact details. Examples **without revealing any private values**:
   - `fab4928039a870ab`: private-person-linked street-level location near offset 9.
   - `727a8a3d9a6f4fd4`: phone number near offset 2095.
   - `d2dbdd1f87b6a3e1`: private residential location near offset 278.

2. **Medicine:** **Manual privacy gate.** Identify and redact the exact private span with surrounding context, or exclude the document if the sensitive material cannot be safely removed. Names of public figures and public institutions are not automatically private data. **Do not embed any private values in rule code, examples, logs, PRs or JSON reports. No executable redaction rule is proposed until a safe detector is tested.**

3. **Action:** Fix by verified, privacy-preserving redaction; otherwise **drop**. Do not release an unredacted F1 record.

4. **Harm test:** **Not run; no executable candidate.** Future redaction rules require separate privacy-recall checks **and** gold-set harm testing; changing 0 gold documents does not guarantee they detect private data.

5. **Side effects:** A broad name/address detector can erase legitimate public references; a narrow detector can miss sensitive data. The label's `hex` and evidence should never reproduce private values.

## Medicine 10 — C4: unrelated documents joined

1. **Disease:** C4, **6 documents**. Two unrelated articles or passages concatenated without a reliable document boundary. Examples:
   - `eca53051bfdab52d`: a new document begins near offset 1975.
   - `815eb112e94faf6e`: unrelated second text begins near offset 115.
   - `f2b8c25ffbcc196c`: unrelated standalone passage begins near offset 555 (`रशियातल्या फिफा`).

2. **Medicine:** **Manual/review-only.** Inspect the boundary and split into separately traceable documents, or retain just the verified coherent span if provenance permits. Do not create duplicate `doc_id`s or guess split locations from language switches alone. **No executable Python medicine is proposed.**

3. **Action:** Fix by a provenance-preserving split/removal when possible; **drop** when the surviving text is not coherent (`d89a364142de1d38` and `9910e11f3461f5d0` are labelled `drop`).

4. **Harm test:** **Not run; no executable candidate.** Any future split rule must test gold preservation, boundary accuracy, and document-ID handling.

5. **Side effects:** Legitimate bilingual quotations, interviews, and multi-section articles may look like joined documents; blind splitting can corrupt source context.

## Medicine 11 — C5: tag/keyword/headline-list contamination

1. **Disease:** C5, **6 documents**. Navigation headlines, SEO tags, related-article lists, and keyword blocks mixed with prose. Examples:
   - `4dea645e7a66adbb`: headline/keyword list begins near offset 2520.
   - `5c0626f06c750fcf`: navigation headline/tag-list starts at offset 0 (`लाईव्ह न्यूज`); the record is labelled `drop`.
   - `9532c5c8c0d27ac4`: standalone `Tags: Sleeping habits` near offset 320.

2. **Medicine:** Remove only clearly standalone tag/keyword lines, not legitimate lists that are part of article content. Whole navigation-only documents need manual exclusion; generic text segmentation is not safe here.

   ```python
   import re

   _C5_TAG_LINE = re.compile(
       r"^\s*(?:Tags?|Keywords?|कीवर्ड)\s*[:：]\s*\S.*$",
       flags=re.IGNORECASE,
   )

   def cure_c5(text):
       return "".join(
           line for line in text.splitlines(keepends=True)
           if not _C5_TAG_LINE.fullmatch(line.rstrip("\r\n"))
       )
   ```

3. **Action:** Fix standalone matched tag lines; manually remove verified other contamination. **Drop** documents composed almost entirely of navigation/headline lists (e.g., `5c0626f06c750fcf`), consistent with their labels.

4. **Harm test:** **Pending.** Measure affected gold IDs at the 1% threshold; also check recall on the actual labelled C5 documents because this narrow rule deliberately leaves many C5 forms untouched.

5. **Side effects:** Metadata examples and instructional prose can contain genuine `Tags:` or `Keywords:` lines. Broadly deleting any list or headline would destroy real content. Some C5 overlaps C1, so combined-rule effects must be assessed separately.

---

## Review and release checklist

- **Labels:** Resolve the six `partial` records before treating the 252-document slice as fully read. Investigate records labelled `fix` where only natural D3 mixing is identified, and A6 diagnoses that describe valid Latin text or numerals.
- **Rule extraction:** Only sections with `cure_<code>` Python functions above are executable candidates. **C3, D4, F1 and C4 are intentionally non-executable manual gates**; they must not be counted as approved or effective rules merely because they appear in this medicine sheet.
- **Harm tests:** Run each executable candidate against official, refreshed, two-reader Marathi gold CSV and the corresponding original Parquet pack. Record hashes, changed/dropped IDs and percentage. Do not claim empirical PASS without the actual run.
- **Effectiveness and conflicts:** Check changes on labelled sick examples, select one approved medicine per disease where proposals overlap, and evaluate the combined pipeline separately; 1% individual-rule harm does not imply safe combined application.
- **Privacy:** Publish only ID/offset/type evidence for F1. Never include raw private values in the public repository.
- **Normalization/Indic:** Retain ZWJ and ZWNJ; do not apply NFKC or globally collapse spaces around matras/viramas. G1 needs precise manual review until enough well-understood cases support a separate rule.
