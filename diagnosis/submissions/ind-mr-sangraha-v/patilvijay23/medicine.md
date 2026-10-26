# Medicine sheet: ind-mr-sangraha-v (patilvijay23)

This sheet is based on the 100 rows in the submitted `labels.csv`. Per the template, it contains one section for each disease found more than five times. Harm-test results are left pending because the Marathi gold set is not ready yet.

## Medicine 1

1. **Disease:** A5, 42 documents. Canonically decomposed Devanagari characters that are not NFC-normalized. Three examples:
   - `4884f7c293a7beab`: `ऱ` → expected NFC `ऱ`
   - `47594b68339a08b9`: `ऴ` → expected NFC `ऴ`
   - `0df3bb99ef03ef5f`: `ऱ` appears 8 times → expected NFC `ऱ`

2. **Medicine:** Normalize the complete text to Unicode NFC. This safely composes canonically equivalent Devanagari sequences instead of special-casing individual Marathi letters.

   ```python
   import unicodedata

   def fix_a5(text):
       return unicodedata.normalize("NFC", text)
   ```

3. **Action:** Fix the text.

4. **Harm test:** **Pending.** Run `fix_a5` on the Marathi gold set. Report the number of gold documents changed and dropped and the affected percentage. PASS only if no more than 1% of the gold set is changed or dropped.

5. **Side effects:** NFC can change code-point length, so offsets recorded before normalization are no longer valid afterward. It does not repair a genuinely cut matra such as `क ि`; the space remains after NFC.

## Medicine 2

1. **Disease:** D3, 29 documents. Natural mixed-language content in an otherwise Marathi document. Three examples:
   - `870f3c12624cc486`: `UPSC`
   - `31e2deeb3fd7a6f3`: `Karjat Nagar Panchayat Election`
   - `0a0b3f785c93d999`: `Nirbhaya Squad Nashik`

2. **Medicine:** Do not alter the text for D3. English names, abbreviations, titles and natural Marathi-English code-mixing are valid content and should not be removed simply because they use another language or script.

   ```python
   def fix_d3(text):
       return text
   ```

3. **Action:** Keep the text unchanged. D3 by itself is not a reason to drop the document.

4. **Harm test:** `fix_d3` changes 0 documents and drops 0 documents by construction, so its affected percentage is 0%. PASS.

5. **Side effects:** None from this medicine. The main risk is from other rules: an aggressive A6 or C1 rule must not mistake legitimate D3 content for corruption or boilerplate.

## Medicine 3

1. **Disease:** C1, 24 documents. Publisher, navigation, related-story, login or social-media boilerplate mixed with article text. Three examples:
   - `2c66d24bfd6db2ef`: `हे ही वाचाः`
   - `0ad004d5deb1e7fe`: `keep reading`
   - `d9e954e478572fc0`: `Read Also`

2. **Medicine:** Remove complete lines only when they match a high-confidence boilerplate phrase. Keep the rule narrow; English text is not boilerplate merely because it is English.

   ```python
   import re

   C1_LINE = re.compile(
       r"^\s*(?:"
       r"हे\s*ही\s*वाचा\s*[:ः]?.*"
       r"|हेही\s*वाचा\s*[:ः]?.*"
       r"|हे\s*देखील\s*वाचा\s*[:ः]?.*"
       r"|Read\s+Also\b.*"
       r"|Keep\s+Reading\b.*"
       r"|Forgot\s+your\s+password\??.*"
       r"|(?:Follow|Like|Share|Subscribe)\b.*"
       r"|.*(?:फेसबुक|ट्विटर|इन्स्टाग्राम|यूट्यूब).*(?:फॉलो|लाईक|शेअर).*"
       r")\s*$",
       re.IGNORECASE,
   )

   def fix_c1(text):
       return "\n".join(
           line for line in text.split("\n")
           if not C1_LINE.match(line)
       )
   ```

3. **Action:** Fix the text by removing only matched boilerplate lines. If a document contains no coherent article after boilerplate removal, its existing document-level drop verdict still applies.

4. **Harm test:** **Pending.** Run `fix_c1` on the Marathi gold set and report changed documents, dropped documents and affected percentage. PASS only if no more than 1% of the gold set is changed or dropped.

5. **Side effects:** A genuine article sentence containing one of these phrases could be removed if it occupies a matching line. Boilerplate not covered by the explicit patterns is intentionally left behind rather than risking deletion of real content.

## Medicine 4

1. **Disease:** C2, 13 documents. The same opening text, title, paragraph or other text is repeated inside one document. Three labelled examples:
   - `4884f7c293a7beab`: opening paragraph repeats at offsets 0 and 316
   - `948113e0495d4af9`: opening text repeats at offsets 0 and 122
   - `0eb7206ab016273c`: opening text repeats at offsets 0 and 686

   TODO: Copy exact duplicate text spans from parquet file.

2. **Medicine:** Remove only exact repeats. First remove exact duplicate lines of meaningful length. Then detect a second exact copy of a sufficiently long prefix near the beginning of the document. Do not use fuzzy semantic matching.

   ```python
   def dedupe_lines(text, min_len=40):
       seen, out = set(), []
       for line in text.split("\n"):
           key = line.strip()
           if len(key) >= min_len and key in seen:
               continue
           if len(key) >= min_len:
               seen.add(key)
           out.append(line)
       return "\n".join(out)

   def dedupe_lead_repeat(text, seed_len=48, min_match=60, search_limit=1200):
       if len(text) < seed_len * 2:
           return text

       seed = text[:seed_len]
       j = text.find(seed, seed_len, min(len(text), search_limit))
       if j < 0:
           return text

       k = 0
       max_k = min(j, len(text) - j)
       while k < max_k and text[k] == text[j + k]:
           k += 1

       if k < min_match:
           return text

       return text[:j] + text[j + k:]

   def fix_c2(text):
       return dedupe_lead_repeat(dedupe_lines(text))
   ```

3. **Action:** Fix the text by keeping the first copy and removing the later exact duplicate.

4. **Harm test:** **Pending.** Run `fix_c2` on the Marathi gold set. Report changed documents, dropped documents and affected percentage. PASS only if no more than 1% of the gold set is changed or dropped.

5. **Side effects:** Poems, songs, legal forms or other documents can intentionally repeat text. An exact-repeat rule may remove legitimate repetition. The rule can also miss duplicates with small OCR, punctuation or whitespace differences.

## Medicine 5

1. **Disease:** A6, 11 documents. Wrong or mixed script inside a token. The labelled examples are heterogeneous, so one global character replacement is unsafe. Three examples:
   - `4884f7c293a7beab`: `१0७`, `१0`, `३0`
   - `61b2c25e9513730b`: `कर्मचा-यांची`
   - `9910e11f3461f5d0`: `आर्टाş`

2. **Medicine:** Automatically repair only the high-confidence mixed-digit subtype: when one numeric token contains both Devanagari and ASCII digits, convert the ASCII digits in that token to Devanagari. Do not globally remove Latin characters or replace every hyphen because valid D3 text and real hyphens would be damaged. Other A6 patterns remain review candidates until a separately harm-tested rule exists.

   ```python
   import re

   ASCII_TO_DEVANAGARI = str.maketrans(
       "0123456789",
       "०१२३४५६७८९"
   )

   MIXED_NUMBER = re.compile(r"[०-९0-9]+")

   def fix_a6(text):
       def repl(match):
           token = match.group()
           has_devanagari = bool(re.search(r"[०-९]", token))
           has_ascii = bool(re.search(r"[0-9]", token))
           if has_devanagari and has_ascii:
               return token.translate(ASCII_TO_DEVANAGARI)
           return token

       return MIXED_NUMBER.sub(repl, text)
   ```

3. **Action:** Fix only the safe mixed-digit subtype. Do not automatically repair the remaining A6 forms until their rules pass the gold-set harm test. Documents with dense unrecoverable mixed-script corruption keep their existing drop verdict.

4. **Harm test:** **Pending.** Run `fix_a6` on the Marathi gold set and report changed documents, dropped documents and affected percentage. PASS only if no more than 1% of the gold set is changed or dropped.

5. **Side effects:** A mixed-script number may occasionally be intentional. This medicine intentionally leaves `कर्मचा-यांची`, `आर्टाş`, ordinary ASCII numbers, valid Latin names and natural Marathi-English code-mixing untouched rather than guessing at a repair.

## Medicine 6

1. **Disease:** B4, 6 documents. Literal backslash-`n` sequences are stored in the text where real line breaks should be. Three examples:
   - `5cd1cc2146075a9f`: `\n` at offset 81 (3x)
   - `09f78635c7686fd8`: `\n` at offset 14 (11x)
   - `8f3c76c4c4ad8584`: `\n` at offset 109 (13x)

2. **Medicine:** Replace the two literal characters backslash + `n` with a real newline. Run this before line-based medicines such as C1 and C2.

   ```python
   def fix_b4(text):
       return text.replace("\\n", "\n")
   ```

3. **Action:** Fix the text.

4. **Harm test:** **Pending.** Run `fix_b4` on the Marathi gold set and report changed documents, dropped documents and affected percentage. PASS only if no more than 1% of the gold set is changed or dropped.

5. **Side effects:** A programming or technical document may intentionally contain the literal characters `\n`; this rule would turn them into a line break. The rule does not repair literal `\t` or `\r`.
