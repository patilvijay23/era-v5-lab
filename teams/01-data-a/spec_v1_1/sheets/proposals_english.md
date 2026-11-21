# proposals_english: spec v1.1 proposals from the day D6 en-dclm audit

**Proposals, 21 Nov. Not part of spec v1.1 yet.** Five fixes for cleaner bugs found in the day D6 en-dclm audit (patilvijay23/era-v5-lab#68, `teams/01-data-a/audit/day_D6_en-dclm.md`), raised as spec v1.1 proposals with harm tests. Spec v1, `specv1_1.md` and the running `clean.py` are not changed.

- **Four replace a spec v1.1 rule** (`DA-A2-008`, `DA-C2-003`, `DA-B4-010`, `DA-F1-005`) with the same rule and one narrow change; **one is new** (`DA-B3-002`). Each replacement's code block is the rule it replaces, copied from `sheets/specv1_1.md`; the change is commented, and `SOURCE_RULE_ID` names the rule it would replace.
- **This is its own sheet**, not `medicine_english.md`: `combine_spec.py` builds `specv1_1.md` from `medicine_english.md`, and a replacement added there would run next to the rule it replaces. When a proposal is accepted, its card replaces the old card in `specv1_1.md` and `clean.py` is rebuilt.
- **Every bug was reproduced with the current `spec_v1_1/clean.py`**: on the five audited docs its output is the text in `tokenizer_sample_v0_clean` and in the decoded frozen-p1536 shards, byte for byte.
- **Rule form** as the other sheets: `medicine(doc)` returns `(action, text)`; each rule runs on the four English packs only.
- **Tests:** `tests/test_proposals_english.py`, 22 tests, and `tests/test_speed_equivalence_proposals_english.py`, 9 tests; all text made up.

**Speed.** `python3 -I spec_v1_1/scripts/speed_proposals.py --clean spec_v1_1/clean.py --packs <dir of the 500-doc sample packs>` (from `teams/01-data-a`) times each proposal against the rule it replaces, and spec v1.1's English `clean()` as it is and with all five proposals in place; best of 3 passes, one process, CPU only. The first versions made `clean()` 0.69x as fast (`DA-C2-005` tested every line against `C2_CODE`: 0.34 to 1.03 ms/doc against 0.04 to 0.13 for `DA-C2-003`). Three speed-ups, each exact (same output), bring it back:
- **`DA-C2-005`:** `C2_CODE` is tested only on a line whose key is there 3 or more times; a key there fewer times cannot reach 3 without its code lines either. The fence test runs only when the text holds ` ``` ` or `~~~`.
- **`DA-F1-007`:** the numbers to mask on every line are found once, and only when a phone line near an organisation asks (on an organisation's page there are none).
- **`DA-A2-009`:** a text with no control character (most) is returned after the line-ending step; the C1 search starts at the first control character.

| pack (500 docs) | `clean()` spec v1.1, docs/s | with the proposals, first version | with the proposals, now |
|---|---:|---:|---:|
| en-dclm | 418.4 | 294.6 (0.69x) | 411.9 (0.98x) |
| en-fineweb-edu | 556.4 | 393.9 (0.69x) | 583.2 (1.05x) |
| en-nemotroncc | 533.7 | 409.9 (0.72x) | 558.5 (1.05x) |
| en-nemotroncc-synth | 1524.8 | 989.8 (0.63x) | 1526.8 (1.00x) |
| all 2,000 | 3.36 s | 4.69 s (0.69x) | 3.29 s (1.02x) |

Timings vary by about 5%, so 0.98x to 1.05x is the same speed. Each sped-up rule gives the same result as its first version on all 63,367 docs (the four sample packs and the two en-dclm train parts), the harm results are identical, and the equivalence tests hold a frozen copy of each first version (9 of 9 hand-made mutations of the speed-ups are caught). No rule loops over tokens; the loops are over lines, as in the rules they replace.

**How each proposal was checked**
- **Harm test:** `python3 -I teams/01-data-a/harmtest/harm_test.py --pack <pack>.parquet --gold teams/01-data-a/gold/<pack>_gold.csv --rules teams/01-data-a/spec_v1_1/sheets/proposals_english.md --rule all`, on the 500-doc sample packs whose sha256 equals `pack_sha256` in `results/sheets/<pack>_harm.json`. Limits: 1 doc on en-dclm (62 gold), en-fineweb-edu (158) and en-nemotroncc (129); 3 on en-nemotroncc-synth (326).
- **In place:** each proposal put into spec v1.1's English pipeline in place of the rule it replaces (`DA-B3-002` added after `DA-B4-012`), and the final output compared with spec v1.1's `clean()` on every doc of the four sample packs and of the two en-dclm train parts of tokenizer sample v0 (61,367 docs). The replayed pipeline gives exactly `clean()`'s output on all 2,000 sample docs. Every changed doc was read.

## 1. `DA-A2-009` · A2 control characters: map cp1252 quotes before removing controls · fix · stage 10 · replaces `DA-A2-008`

1. **Disease:** A2, handled wrongly. Text that was cp1252 bytes read as Latin-1 holds ’ “ ” – — as the C1 controls U+0092, U+0093, U+0094, U+0096, U+0097. `DA-A2-008` deletes every U+0080–U+009F, so the punctuation is lost: `children’s` becomes `childrens`, `that’s` becomes `thats`, and quotation marks disappear.
   - `a9a7821bb3d942d0` (en-dclm, Part_1): `children\x92s` becomes `childrens`, `you\x92ve` becomes `youve`; 6 apostrophes and 4 quotes are lost.
   - In the two en-dclm train parts of tokenizer sample v0, 50 kept docs hold U+0092; spec v1.1 removes the apostrophe in 49 of them.
2. **Medicine:** as `DA-A2-008`, with one step first, only in a doc that has a C1 control:
   - `â`, `\x80` and one more byte are the UTF-8 bytes of a U+2000–U+203F (`–`, `’`, `“`, `”`, `…`) read as Latin-1; with the `â` lost (`me \x80\x93 let\x80\x99s`) they are its last two. Either way they become that punctuation. This also covers `\x9d` (`”`), which cp1252 leaves undefined.
   - Every other C1 control that cp1252 defines is mapped to its character (`\x92` → `’`, `\x93` → `“`, `\x80` → `€`, `\x86` → `†`, …), as ftfy's `fix_c1_controls` does.
   - The five that cp1252 leaves undefined (0x81, 0x8D, 0x8F, 0x90, 0x9D) and all other controls are removed, as before.

```python
RULE_ID = "DA-A2-009"
SOURCE_RULE_ID = "DA-A2-008"  # proposed replacement of DA-A2-008
CODE = "A2"
ACTION = "fix"
STAGE = "10"
STATUS = "PROPOSAL"
LANGS = {"en", "eng"}
ORIGIN = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # packs it runs on
SOURCE = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # pack whose medicine this came from
AUTHOR = "aneeshads"  # new in the 29 Oct sheet as DA-A2-007
PROPOSED_BY = "TEJASKUMAR-REDDY-J"  # this change, from the day D6 en-dclm audit
import re

A2_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# U+0080..U+009F that cp1252 defines (\x92 is ’, \x93 “, \x94 ”, \x96 – ...): text that was cp1252 bytes read as
# Latin-1. They are mapped to their characters first; the five cp1252 leaves undefined are still removed.
A2_CP1252 = {c: bytes([c]).decode("cp1252") for c in range(0x80, 0xA0) if c not in (0x81, 0x8D, 0x8F, 0x90, 0x9D)}
A2_C1 = re.compile(r"[\x80-\x9f]")
# UTF-8 read as Latin-1, with a C1 control among its bytes: `Ã\x89` is É, `â\x80\x99` is ’, `â\x80\x9d` is ” (\x9d is
# one that cp1252 leaves undefined). Such a sequence is decoded back first; one with no C1 control (`Â©`) is
# left alone. `\x80` and a second C1 control, with the first byte lost (`me \x80\x93 let\x80\x99s`), are the last
# two bytes of a U+2000..U+201F (– ’ “ ”) and become it.
A2_UTF8 = re.compile(r"[\xc2-\xdf][\x80-\xbf]|[\xe0-\xef][\x80-\xbf]{2}|\x80[\x80-\x9f]")


def _a2_utf8(m):
    s = m.group()
    if not A2_C1.search(s):
        return s
    if s[0] == "\x80":
        return chr(0x2000 + ord(s[1]) - 0x80)
    try:
        return s.encode("latin-1").decode("utf-8")
    except UnicodeDecodeError:
        return s


def medicine_a2(text):
    new = text.replace("\r\n", "\n").replace("\r", "\n")
    first = A2_CONTROL.search(new)  # speed: most docs have no control character, and then nothing else changes
    if first:
        if A2_C1.search(new, first.start()):  # a C1 control is a control character: none comes before the first
            new = A2_UTF8.sub(_a2_utf8, new).translate(A2_CP1252)
        new = A2_CONTROL.sub("", new)
    return ("fix" if new != text else "keep", new)


def medicine(doc):
    if doc.get("lang_label") not in LANGS:
        return ("keep", doc["text"])
    return medicine_a2(doc["text"])

_spec_source_medicine = medicine

SPEC_PACKS = {'en-dclm', 'en-fineweb-edu', 'en-nemotroncc', 'en-nemotroncc-synth'}

def medicine(doc):
    if doc.get("pack_id") not in SPEC_PACKS:
        return ("keep", doc["text"])
    out = _spec_source_medicine(doc)
    return out
```

3. **Action:** fix. **Runs on:** en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth.
4. **Harm test:** gold docs changed or dropped: en-dclm 0/62, en-fineweb-edu 0/158, en-nemotroncc 0/129, en-nemotroncc-synth 0/326. PASS on all four, alone and all in order.

   **In place of the rule it replaces:**

| Pack | Docs | Docs whose output changes | of them gold |
|---|---:|---:|---:|
| en-dclm | 500 | 2 | 0 |
| en-fineweb-edu | 500 | 0 | 0 |
| en-nemotroncc | 500 | 0 | 0 |
| en-nemotroncc-synth | 500 | 0 | 0 |
| en-dclm train part-00000 | 46,245 | 102 | — |
| en-dclm train part-00001 | 15,122 | 36 | — |

5. **Side effects:**
   - Mojibake of two or more layers (`\x83Â\x82Ã\x82Â\x96`) stays garbage, as with `DA-A2-008`, only with different characters; `DA-A3-002` handles such docs.
   - When `DA-A3-002` (ftfy) later repairs other mojibake in a doc, it also straightens the doc's curly quotes, as it does today.
   - A doc that holds a real C1 control on purpose (none seen) gets a character instead of nothing.
6. **Spec v1.1:** status PROPOSAL, reviewer pending. Proposed by TEJASKUMAR-REDDY-J from the day D6 en-dclm audit.

## 2. `DA-C2-005` · C2 repeated lines: leave code and config alone · fix · stage 35 · replaces `DA-C2-003`

1. **Disease:** `DA-C2-003` removes the later copies of any line that appears 3 or more times. Inside a code or config snippet a line repeats because the program needs it, so removing it changes the code.
   - `f1b8673c7cfd7aac` (en-dclm, Part_2): an OpenVPN setup post. `cd /etc/openvpn` goes from 3 lines to 1 and `# up ip route add via` from 4 to 1, so the scripts shown no longer do what the text says.
2. **Medicine:** as `DA-C2-003`, but a line is not counted, and so never removed, when it is inside a ```` ``` ```` or `~~~` fence, or looks like code or config (`C2_CODE`):
   - a `#`, `//`, `$ ` or `>>> ` at its start; `{` at its end or `}` at its start;
   - `;` at its end after `)`, in an assignment, a declaration (`private String name;`) or a CSS property (`display: block;`);
   - a Unix path (`/etc/openvpn`), `key=value` at its start, `a::b`, `->`, `=>` or an empty `()`.

   Dates (`Joined: 02/15/2010`), URLs and `::` as a separator (`Amy :: permalink`) do not count, so forum and blog furniture still goes, as do menu and share lines (`Share this:`, `Read more`).

```python
RULE_ID = "DA-C2-005"
SOURCE_RULE_ID = "DA-C2-003"  # proposed replacement of DA-C2-003
CODE = "C2"
ACTION = "fix"
STAGE = "35"
STATUS = "PROPOSAL"
LANGS = {"en", "eng"}
ORIGIN = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # packs it runs on
SOURCE = "en-fineweb-edu"  # pack whose medicine this came from
AUTHOR = "deepjyotisaha"  # extractor; adapter for spans
PROPOSED_BY = "TEJASKUMAR-REDDY-J"  # this change, from the day D6 en-dclm audit
import re

def _merge(spans):
    """Overlapping spans joined into one, keeping the rule of the first."""
    out = []
    for s, e, rule in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(e, out[-1][1]), out[-1][2])
        else:
            out.append((s, e, rule))
    return out

C2_MIN_REPEAT, C2_MIN_CHARS = 3, 10

# a line of code or config, which repeats because the program needs it, not because it is boilerplate:
# a comment or prompt at its start (#, //, $, >>>); { at its end or } at its start; ';' after ')' or in an
# assignment, a declaration or a CSS property; a Unix path (/etc/); key=value at its start; a::b, -> or =>;
# an empty (). Dates (02/15/2010), URLs and '::' as a separator do not count.
C2_CODE = re.compile(r"^\s*(?:#|//|\$ |>>> )|\{\s*$|^\s*\}|\)\s*;\s*$|=[^=\n]*;\s*$|^\s*(?:private|public|protected|static|final|var|let|const|int|long|char|float|double|bool|boolean|String|void|my|use|import|include|require)\b[^\n]*;\s*$|^\s*[a-z][a-z-]*:\s*[^;\n]{1,40};\s*$|(?:^|\s)[~.]?/[A-Za-z_][\w.-]*/|^\s*[A-Za-z_]\w*=\S|\w::\w|->|=>|\w\(\)")

def c2_spans(text):
    """C2: later copies of a line repeated C2_MIN_REPEAT or more times in the document."""
    fenced = "```" in text or "~~~" in text  # speed: no fence marker, no fence
    seen, lines, pos, fence = {}, [], 0, False
    for line in text.split("\n"):
        key = " ".join(line.split())
        if fenced and line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if len(key) >= C2_MIN_CHARS and not fence:
            lines.append((pos, pos + len(line), key, line))
            seen[key] = seen.get(key, 0) + 1
        pos += len(line) + 1
    # a code line is not counted. speed: C2_CODE is tested only on a line whose key is there C2_MIN_REPEAT times or
    # more with code lines counted; a key there fewer times stays under C2_MIN_REPEAT without them too
    code = {k for k, (_, _, key, line) in enumerate(lines) if seen[key] >= C2_MIN_REPEAT and C2_CODE.search(line)}
    for k in code:
        seen[lines[k][2]] -= 1
    out, first = [], set()
    for k, (s, e, key, _) in enumerate(lines):
        if k not in code and seen[key] >= C2_MIN_REPEAT:
            if key in first:
                out.append((s, e, "C2-repeated-line"))
            first.add(key)
    return out


def _std(out, text):  # added by Data A
    # the author's result (spans to remove) in the shared form, as their clean() reads it: (spans, True) from
    # c1_spans -> drop; a whole-document "B4-mostly-code" or "C5-list-page" span -> drop; else the spans go
    if isinstance(out, tuple):
        out, flagged = out
        if flagged: return ("drop", text)
    if out and out[0][2] in ("B4-mostly-code", "C5-list-page"): return ("drop", text)
    new = text
    for s, e, _ in reversed(_merge(out)):
        new = new[:s] + new[e:]
    return ("fix" if new != text else "keep", new)


def medicine(doc):
    if doc.get("lang_label") not in LANGS:
        return ("keep", doc["text"])
    return _std(c2_spans(doc["text"]), doc["text"])

_spec_source_medicine = medicine

SPEC_PACKS = {'en-dclm', 'en-fineweb-edu', 'en-nemotroncc', 'en-nemotroncc-synth'}

def medicine(doc):
    if doc.get("pack_id") not in SPEC_PACKS:
        return ("keep", doc["text"])
    out = _spec_source_medicine(doc)
    return out
```

3. **Action:** fix. **Runs on:** en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth.
4. **Harm test:** gold docs changed or dropped: en-dclm 0/62, en-fineweb-edu 0/158, en-nemotroncc 0/129, en-nemotroncc-synth 0/326. PASS on all four, alone and all in order.

   **In place of the rule it replaces:**

| Pack | Docs | Docs whose output changes | of them gold |
|---|---:|---:|---:|
| en-dclm | 500 | 0 | 0 |
| en-fineweb-edu | 500 | 0 | 0 |
| en-nemotroncc | 500 | 1 | 0 |
| en-nemotroncc-synth | 500 | 1 | 0 |
| en-dclm train part-00000 | 46,245 | 48 | — |
| en-dclm train part-00001 | 15,122 | 16 | — |

5. **Side effects:**
   - A repeated line that starts with `#`, holds `->` in prose, or `::` between words now stays. On the 61,367 en-dclm docs that is 3 boilerplate lines: `# of Dives: …`, `# of people in Group: …` and `::CrossRef::Google Scholar::`. The other 61 changed docs are code or config (Java, C, C#, PHP, Perl, Python, shell, CSS, Haskell, Verilog, SDP).
   - Code that the test does not see as code (a repeated `print report` line with no sign) is still cut, as before.
6. **Spec v1.1:** status PROPOSAL, reviewer pending. Proposed by TEJASKUMAR-REDDY-J from the day D6 en-dclm audit.

## 3. `DA-B4-014` · B4 template expressions: a `${` that opens math stays · fix · stage 40 · replaces `DA-B4-010`

1. **Disease:** `DA-B4-010` removes `${...}` as a template expression (`${name}`). In LaTeX, `$` followed by a group is ordinary math (`${8,16,24}$`, `${\bf a}$`, `${\mathcal P}$`), so the rule cuts formulas and leaves stray `$` signs.
   - `bfa86fe32d00c663` (en-dclm, Part_1): `Multiples of $8$ are: ${8,16,24,...}$` becomes `Multiples of $8$ are: $`; the three lists that lead to the answer (168) are gone.
2. **Medicine:** as `DA-B4-010`, but a `${...}` whose content starts like math stays: a backslash, a digit, `{`, `}`, `<`, `^`, `_` or `$` (`${8,16,24}$`, `${\bf a}$`, `${}^* N$`, `${<}\kappa$`, `${\log_2 n}$`). Template expressions (`${name}`, `${user.id}`, `${ a + b }`, `${@srctree}`, `${.project.name}`) go as before. The other template forms and the mostly-code drop are unchanged.

```python
RULE_ID = "DA-B4-014"
SOURCE_RULE_ID = "DA-B4-010"  # proposed replacement of DA-B4-010
CODE = "B4"
ACTION = "fix"
STAGE = "40"
STATUS = "PROPOSAL"
LANGS = {"en", "eng"}
ORIGIN = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # packs it runs on
SOURCE = "en-fineweb-edu"  # pack whose medicine this came from
AUTHOR = "deepjyotisaha"  # extractor; adapter for spans
PROPOSED_BY = "TEJASKUMAR-REDDY-J"  # this change, from the day D6 en-dclm audit
import re

def _merge(spans):
    """Overlapping spans joined into one, keeping the rule of the first."""
    out = []
    for s, e, rule in sorted(spans):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(e, out[-1][1]), out[-1][2])
        else:
            out.append((s, e, rule))
    return out

B4_TEMPLATE = re.compile(
    r"\{\{[^{}\n]{0,80}\}\}"                          # {{ title }}
    r"|\{%[^\n]{0,80}?%\}"                            # {% if x %}
    r"|\$\{(?!\s*[\\\d{}<^_$])[^{}\n]{0,80}\}"          # ${name}; not math: ${8,16,24}, ${\bf a}, ${}^*
    r"|`[\w.]+(?:\s*(?:\|\||&&)\s*[\w.]+)+`"          # `page.data.shortTitle || page.data.title`
    r"|(?<=[:=$])\s*(?:undefined|NaN)\b"              # Price: NaN, name=undefined
    r"|^[ \t]*(?:undefined|NaN|null)[ \t]*$", re.M)

B4_CODE_TOKENS = re.compile(
    r"::|->|=>|==|!=|<=|>=|&&|\|\||\+\+|\+=|-=|\);|\)\s*\{|[{};]\s*$|\}"
    r"|^\s*(?:#include|import\s|from\s+\S+\s+import|def\s|class\s|public\s|private\s|static\s|void\s|return\b"
    r"|require\s|var\s|let\s|const\s|function\b|Sub\s|End Sub|Dim\s|\$\s|>>>\s|>\s)"
    r"|\b(?:End Sub|ByVal|As Integer|System\.out|printf|println)\b", re.M)

B4_MIN_TOKENS, B4_WORDS_PER_TOKEN, B4_SHARE = 2, 6, 0.5

TABLE_ROW = re.compile(r"^\s*\|.*\|\|")

def b4_code_lines(text):
    """(start, end) of every line that looks like code."""
    out, pos = [], 0
    for line in text.split("\n"):
        tokens = len(B4_CODE_TOKENS.findall(line))
        words = len(line.split())
        if tokens >= B4_MIN_TOKENS and tokens * B4_WORDS_PER_TOKEN >= words and not TABLE_ROW.match(line):
            out.append((pos, pos + len(line)))
        pos += len(line) + 1
    return out

def b4_mostly_code(text):
    """Whether the lines b4_code_lines finds are more than B4_SHARE of the text, as b4_spans asks. The same test, but it
    stops as soon as the answer cannot change: when the code lines already pass the limit, or when the code found plus
    every character not yet read cannot reach it (a prose document is settled halfway through)."""
    if not text.strip():
        return False
    limit = B4_SHARE * len(text.strip())
    code, left = 0, len(text)
    for line in text.split("\n"):
        tokens = len(B4_CODE_TOKENS.findall(line))
        if tokens >= B4_MIN_TOKENS and tokens * B4_WORDS_PER_TOKEN >= len(line.split()) and not TABLE_ROW.match(line):
            code += len(line)
            if code > limit:
                return True
        left -= len(line) + 1
        if code + left <= limit:
            return False
    return False

# Every alternative of B4_TEMPLATE contains one of these, so a text with none of them has no template expression.
B4_TEMPLATE_HINTS = ("{{", "{%", "${", "`", "undefined", "NaN", "null")

def b4_spans(text):
    """B4: the document is dropped if it is mostly code; otherwise template expressions are removed."""
    if b4_mostly_code(text):
        return [(0, len(text), "B4-mostly-code")]
    if not any(hint in text for hint in B4_TEMPLATE_HINTS):
        return []
    return [(m.start(), m.end(), "B4-template") for m in B4_TEMPLATE.finditer(text)]


def _std(out, text):  # added by Data A
    # the author's result (spans to remove) in the shared form, as their clean() reads it: (spans, True) from
    # c1_spans -> drop; a whole-document "B4-mostly-code" or "C5-list-page" span -> drop; else the spans go
    if isinstance(out, tuple):
        out, flagged = out
        if flagged: return ("drop", text)
    if out and out[0][2] in ("B4-mostly-code", "C5-list-page"): return ("drop", text)
    new = text
    for s, e, _ in reversed(_merge(out)):
        new = new[:s] + new[e:]
    return ("fix" if new != text else "keep", new)


def medicine(doc):
    if doc.get("lang_label") not in LANGS:
        return ("keep", doc["text"])
    return _std(b4_spans(doc["text"]), doc["text"])

_spec_source_medicine = medicine

SPEC_PACKS = {'en-dclm', 'en-fineweb-edu', 'en-nemotroncc', 'en-nemotroncc-synth'}

def medicine(doc):
    if doc.get("pack_id") not in SPEC_PACKS:
        return ("keep", doc["text"])
    out = _spec_source_medicine(doc)
    return out
```

3. **Action:** fix. **Runs on:** en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth.
4. **Harm test:** gold docs changed or dropped: en-dclm 0/62, en-fineweb-edu 0/158, en-nemotroncc 0/129, en-nemotroncc-synth 0/326. PASS on all four, alone and all in order.

   **In place of the rule it replaces:**

| Pack | Docs | Docs whose output changes | of them gold |
|---|---:|---:|---:|
| en-dclm | 500 | 0 | 0 |
| en-fineweb-edu | 500 | 0 | 0 |
| en-nemotroncc | 500 | 0 | 0 |
| en-nemotroncc-synth | 500 | 0 | 0 |
| en-dclm train part-00000 | 46,245 | 11 | — |
| en-dclm train part-00001 | 15,122 | 2 | — |

5. **Side effects:**
   - A template expression that starts with one of those characters (`${0}`, `${_id}`) is no longer removed.
   - Math that starts with a letter (`${a,b,c}$`) is still removed, as before.
6. **Spec v1.1:** status PROPOSAL, reviewer pending. Proposed by TEJASKUMAR-REDDY-J from the day D6 en-dclm audit.

## 4. `DA-F1-007` · F1 phone numbers: one decision per number, and UK freephone is toll-free · fix · stage 40 · replaces `DA-F1-005`

1. **Disease:** `DA-F1-005` masks a phone number unless an organisation word is within 6 lines of it (or the page speaks as an organisation). The same number on two lines can fall on both sides of that window, so it is masked on one line and left in full on the next, which masks nothing. Its toll-free test also knows only US 8xx numbers, so a UK `0800` freephone is treated as private.
   - `ef987c066d1cdf0f` (en-dclm, Part_2): a heating company's page with its freephone number on two lines in a row; spec v1.1 gives `FREEPHONE <PHONE>` and then `FREEPHONE` with the number in full.
2. **Medicine:** as `DA-F1-005`, with two changes:
   - **One decision per number, privacy first:** a first pass collects the numbers that would be masked on some line (no organisation context there, not toll-free). Such a number is masked on every line, also on a line near an organisation word. Numbers only ever seen in an organisation's context are kept, as before.
   - **UK freephone is toll-free:** `TOLL_FREE` also matches `0800`, `0808`, `+44 800` and `+44 808`.

   Emails and addresses are handled as before.

```python
RULE_ID = "DA-F1-007"
SOURCE_RULE_ID = "DA-F1-005"  # proposed replacement of DA-F1-005
CODE = "F1"
ACTION = "fix"
STAGE = "40"
STATUS = "PROPOSAL"
LANGS = {"en", "eng"}
ORIGIN = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # packs it runs on
SOURCE = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # pack whose medicine this came from
AUTHOR = "aneeshads"  # new rule to the instructor's F1 ruling of 31 Oct; email test from DA-F1-002 (shekar-maker)
PROPOSED_BY = "TEJASKUMAR-REDDY-J"  # this change, from the day D6 en-dclm audit
import re

EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b")

WEBMAIL = re.compile(r"@(?:gmail|googlemail|yahoo|ymail|hotmail|outlook|live|msn|aol|icloud|me|mac|protonmail|proton|"
                     r"rediffmail|zoho|gmx|yandex|mail|comcast|verizon|att|sbcglobal|bellsouth|earthlink|btinternet)\.", re.I)

PERSONAL_LOCAL = re.compile(r"[._\-]|\d|^.{13,}$")

ROLE_LOCAL = re.compile(r"^(?:info|contact|contactus|enquir(?:y|ies)|inquir(?:y|ies)|sales|support|help|helpdesk|admin|"
                        r"office|hello|hi|press|media|news|newsletter|editor|editors|team|jobs|careers|hr|marketing|"
                        r"billing|accounts|orders|service|services|customerservice|webmaster|postmaster|noreply|"
                        r"no-reply|abuse|privacy|legal|admissions|registrar|events|bookings|reservations)$", re.I)

NOT_REAL = re.compile(r"@(?:example|test|domain|email)\.(?:com|org|net)$", re.I)

PHONE = re.compile(r"(?<![\w-])(?:\+\d{1,3}[\s.\-‐‑–]?)?(?:\(\d{2,4}\)[\s.\-‐‑–]?|\d{2,4}[\s.\-‐‑–])\d{3,4}[\s.\-‐‑–]\d{3,4}(?![\w-])")

# US 8xx, and UK freephone 0800/0808 (+44 800/808)
TOLL_FREE = re.compile(r"^(?:(?:\+?1[\s.-]?)?\(?8(?:00|88|77|66|55|44|33)\)?|(?:\+44[\s.-]?|0)80[08](?=[\s.\-]))")
NOT_DIGIT = re.compile(r"\D")

STREET = (r"(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Boulevard|Blvd|Drive|Dr|Court|Ct|Way|Place|Pl|Terrace|Ter|Close|"
          r"Crescent|Cres|Highway|Hwy|Parkway|Pkwy|Circle|Cir|Square|Sq)")

ADDRESS = re.compile(r"\b\d{1,5}[A-Za-z]?\s+(?:[NSEW]\.?\s+)?(?:[A-Z][a-z]+\.?\s+){1,4}" + STREET + r"\b\.?"
                     r"(?:,?\s*(?:Apt|Unit|Suite|Ste|#)\.?\s*\w+)?"
                     r"(?:,\s*(?:[A-Z][a-z]+\s?){1,3},\s*[A-Z]{2}\.?\s*\d{5}(?:-\d{4})?)?")

CONTACT_LINE = 120

ORGANISATION = re.compile(
    r"(?i)\b(?:inc|llc|ltd|plc|corp|co\.|company|warehouse|store|shop|market|restaurant|cafe|café|bar|grill|bistro|"
    r"hotel|inn|motel|resort|spa|salon|clinic|hospital|surgery|pharmacy|cent(?:er|re)|office|offices|university|"
    r"college|school|academy|library|museum|church|gallery|theat(?:er|re)|cinema|bank|agency|association|society|"
    r"council|department|ministry|embassy|tourist|information|headquarters|hq|branch|showroom|dealership|"
    r"open (?:mon|tue|wed|thu|fri|sat|sun|daily|7|24)\w*|hours|menu|reservations|fax|"
    r"on (?:urbanspoon|yelp|tripadvisor|zomato|foursquare)|"
    # trades and services that put their number on their own page
    r"pros?|plumb\w*|roofing|hvac|electric(?:al|ians?)|landscap\w*|cleaning|movers?|moving|storage|rentals?|hire|"
    r"repairs?|construction|builders?|contractors?|auto|motors|towing|insurance|realty|real estate|mortgage|loans?|"
    r"law|lawyers?|attorneys?|legal|dental|dentistry|orthodont\w*|chiropract\w*|physiotherap\w*|therapy|"
    r"veterinar\w*|vet|clinics?|practice|surgery|medical|health(?:care)?|consult(?:ation|ing|ants?)?|services?|"
    r"solutions|group|partners|associates|studio|chalet|lodge|villa|apartments?|cottage|camping|farm|winery|"
    r"brewery|bakery|club|bbs|board|optometr\w*|optic\w*|opticians?|spectacles|suite)\b")

ORG_VOICE = re.compile(r"(?i)\b(?:call us|contact us|email us|e-mail us|visit us|reach us|text us|give us a call|"
                       r"our (?:office|team|staff|clinic|store|shop|experts?|technicians?|specialists?|services?|"
                       r"company|firm|practice|location)|one of our|we (?:offer|provide|specialize|specialise|serve)|need help\?)|☎")

PUBLIC_ROLE = re.compile(r"(?i)\b(?:reporter|editor|journalist|correspondent|spokes(?:man|woman|person)|press|media|"
                         r"publicist|author of|professor|prof\.|dr\.|lecturer|faculty|researcher|principal investigator|"
                         r"media contact|press contact|for more information|high[- ]res|images|photos)\b")

DIGIT = re.compile(r"\d")

def _email(m, org):
    addr = m.group()
    local = addr.split("@", 1)[0]
    if NOT_REAL.search(addr) or ROLE_LOCAL.match(local):
        return addr
    if WEBMAIL.search(addr):  # a webmail address belongs to a person
        return "<EMAIL>"
    # a name-like address at an organisation's domain is a work address when the context is an organisation's
    return addr if org or not PERSONAL_LOCAL.search(local) else "<EMAIL>"

def medicine_f1(text):
    lines = text.split("\n")
    org_page = []  # ORG_VOICE on the whole text: searched once, and only when a contact line asks
    has_org = {}  # line number -> an organisation word on that line: searched once, and only when a contact line asks

    def on_org_page():
        if not org_page:
            org_page.append(bool(ORG_VOICE.search(text)))
        return org_page[0]

    def org_near(i):  # same answer as searching the joined 13-line window, as no match spans a newline
        for j in range(max(0, i - 6), min(len(lines), i + 7)):
            if j not in has_org:
                has_org[j] = ORGANISATION.search(lines[j]) is not None
            if has_org[j]:
                return True
        return False

    # one decision per number, privacy first: a number masked on any line is masked on every line, also on a line
    # near an organisation word (the 13-line window alone can mask a number on one line and keep it on the next).
    # speed: the masked numbers are found once, and only when a phone line near an organisation asks
    masked = []

    def masked_numbers():
        if not masked:
            nums = set()
            if not on_org_page():  # on an organisation's page no line is masked
                for i, line in enumerate(lines):
                    if DIGIT.search(line) and PHONE.search(line) and not org_near(i):
                        nums.update(NOT_DIGIT.sub("", m.group()) for m in PHONE.finditer(line)
                                    if not TOLL_FREE.match(m.group()))
            masked.append(nums)
        return masked[0]

    out = []
    for i, line in enumerate(lines):
        if "@" not in line and not DIGIT.search(line):  # no EMAIL, PHONE or ADDRESS can match
            out.append(line)
            continue
        new = EMAIL.sub(lambda m: _email(m, on_org_page() or org_near(i) or bool(PUBLIC_ROLE.search(
            "\n".join(lines[max(0, i - 2):i + 1])))), line) if "@" in line else line
        if PHONE.search(new) or ADDRESS.search(new):
            if not (on_org_page() or org_near(i)):
                new = PHONE.sub(lambda m: m.group() if TOLL_FREE.match(m.group()) else "<PHONE>", new)
                if len(line.strip()) <= CONTACT_LINE:
                    new = ADDRESS.sub("<ADDRESS>", new)
            elif masked_numbers():
                new = PHONE.sub(lambda m: "<PHONE>" if NOT_DIGIT.sub("", m.group()) in masked[0] else m.group(), new)
        out.append(new)
    return "\n".join(out)


def _std(out, text):  # added by Data A
    # the author's result in the shared form: str -> fix/keep, None or True -> drop, False -> keep,
    # ("drop", _) -> drop. An empty result is a drop: nothing of the document is left.
    if out is None or out is True: return ("drop", text)
    if out is False: return ("keep", text)
    if isinstance(out, tuple):
        if out[0] == "drop": return ("drop", text)
        out = out[1]
    if not out.strip(): return ("drop", text)
    return ("fix" if out != text else "keep", out)


def medicine(doc):
    if doc.get("lang_label") not in LANGS:
        return ("keep", doc["text"])
    return _std(medicine_f1(doc["text"]), doc["text"])

_spec_source_medicine = medicine

SPEC_PACKS = {'en-dclm', 'en-fineweb-edu', 'en-nemotroncc', 'en-nemotroncc-synth'}

def medicine(doc):
    if doc.get("pack_id") not in SPEC_PACKS:
        return ("keep", doc["text"])
    out = _spec_source_medicine(doc)
    return out
```

3. **Action:** fix. **Runs on:** en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth.
4. **Harm test:** gold docs changed or dropped: en-dclm 0/62, en-fineweb-edu 0/158, en-nemotroncc 0/129, en-nemotroncc-synth 0/326. PASS on all four, alone and all in order.

   **In place of the rule it replaces:**

| Pack | Docs | Docs whose output changes | of them gold |
|---|---:|---:|---:|
| en-dclm | 500 | 0 | 0 |
| en-fineweb-edu | 500 | 0 | 0 |
| en-nemotroncc | 500 | 0 | 0 |
| en-nemotroncc-synth | 500 | 0 | 0 |
| en-dclm train part-00000 | 46,245 | 13 | — |
| en-dclm train part-00001 | 15,122 | 2 | — |

5. **Side effects:**
   - A business number that appears once far from an organisation word is now masked on every line (before: on that line only). That masks more, never less.
   - Other countries' free numbers (IE, AU, IN `1800`) are still not toll-free; they need the same review first.
6. **Spec v1.1:** status PROPOSAL, reviewer pending. Proposed by TEJASKUMAR-REDDY-J from the day D6 en-dclm audit.

## 5. `DA-B3-002` · B3 ghost markers: `<s>` and `</s>` used as markup in English text · fix · stage 40 · new

1. **Disease:** B3, the BOS/EOS markers `<s>` and `</s>` in plain text. On wiki talk pages they are strikethrough markup; `DA-B2-002` removes a fixed list of HTML tags that has no `s`, and English has no B3 rule (`DA-B3-001` is for code). The markers reach the shards as text.
   - `b86875f06abe649a` (en-dclm, Part_1): a wiki talk page with `<s>` twice and `</s>` once; all three are in the decoded p1536 shard `en-dclm-train-000000`.
2. **Medicine:** in a doc that has both `<s>` and `</s>` (strikethrough markup), remove every `<s>` and `</s>`; the struck text stays. A doc with only a lone `<s>` is not touched: on HTML reference pages (`<s> Defines strikethrough text`) it is the topic, not markup. Runs after the B4 rules (stage 40), before the A8, D7 and F1 rules.

```python
RULE_ID = "DA-B3-002"
CODE = "B3"
ACTION = "fix"
STAGE = "40"
STATUS = "PROPOSAL"
LANGS = {"en", "eng"}
ORIGIN = "en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth"  # packs it runs on
PACKS = set(ORIGIN.split(", "))
SOURCE = "en-dclm"  # pack whose reading found it (day D6 audit)
AUTHOR = "TEJASKUMAR-REDDY-J"
import re

# <s> and </s>: the BOS/EOS markers in text. Used together they are strikethrough markup, which DA-B2-002 leaves
# alone: the markers go, the struck text stays. A lone <s> (an HTML reference: "<s> Defines strikethrough text") stays.
B3_S = re.compile(r"</?s>")


def medicine(doc):
    if doc.get("pack_id") not in PACKS or doc.get("lang_label") not in LANGS:
        return ("keep", doc["text"])
    text = doc["text"]
    if "<s>" not in text or "</s>" not in text:  # markup needs both; speed: most docs have neither
        return ("keep", text)
    new = B3_S.sub("", text)
    return ("fix" if new != text else "keep", new)
```

3. **Action:** fix. **Runs on:** en-dclm, en-fineweb-edu, en-nemotroncc, en-nemotroncc-synth.
4. **Harm test:** gold docs changed or dropped: en-dclm 0/62, en-fineweb-edu 0/158, en-nemotroncc 0/129, en-nemotroncc-synth 0/326. PASS on all four, alone and all in order.

   **In place of nothing (added):**

| Pack | Docs | Docs whose output changes | of them gold |
|---|---:|---:|---:|
| en-dclm | 500 | 0 | 0 |
| en-fineweb-edu | 500 | 0 | 0 |
| en-nemotroncc | 500 | 0 | 0 |
| en-nemotroncc-synth | 500 | 0 | 0 |
| en-dclm train part-00000 | 46,245 | 2 | — |
| en-dclm train part-00001 | 15,122 | 0 | — |

5. **Side effects:**
   - An HTML tutorial that shows `<s>…</s>` in an example loses the markers in the example (1 doc of 61,367).
   - A lone `<s>` or `</s>` stays, so a page that only names the markers keeps them; `<S>`, `<strike>` and `<del>` are not touched.
6. **Spec v1.1:** status PROPOSAL, reviewer pending. Proposed by TEJASKUMAR-REDDY-J from the day D6 en-dclm audit.
