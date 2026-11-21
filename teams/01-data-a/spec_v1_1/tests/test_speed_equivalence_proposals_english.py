"""Equivalence tests for the speed-ups of three rules in sheets/proposals_english.md (DA-A2-009, DA-C2-005, DA-F1-007).

Each rule is read from its card in the sheet. A frozen copy of the function as it was before the speed-up (below; it uses
the regexes of the same card) must give the same result as the card on hand-written cases at the edge of each change and on
random texts. Every text here is made up; none comes from a pack. The phone numbers are in the UK range kept for drama.

  python3 -m unittest discover -s spec_v1_1/tests -p "test_speed_equivalence_proposals*"      (from teams/01-data-a)
"""
import random
import re
import textwrap
import unittest
from pathlib import Path

SHEET = Path(__file__).resolve().parents[1] / "sheets" / "proposals_english.md"
SRC = SHEET.read_text(encoding="utf-8")
N_RANDOM = 4000


def card(rule_id):
    """The card's code block run on its own: a fresh namespace each time, so a test can wrap its regexes."""
    body = re.search(rf"^## \d+\. `{rule_id}`.*?^```python\n(.*?)^```", SRC, re.S | re.M).group(1)
    ns = {"__name__": "rules"}
    exec(textwrap.dedent(body), ns)
    return ns


class Spy:
    """A compiled regex that counts its search() calls."""

    def __init__(self, rx):
        self.rx, self.calls = rx, 0

    def search(self, *a):
        self.calls += 1
        return self.rx.search(*a)

    def __getattr__(self, name):
        return getattr(self.rx, name)


# ---------------------------------------------------------------- frozen copies, as before the speed-up. Keep unchanged.

def old_a2(text, ns):
    new = text.replace("\r\n", "\n").replace("\r", "\n")
    if ns["A2_C1"].search(new):
        new = ns["A2_UTF8"].sub(ns["_a2_utf8"], new).translate(ns["A2_CP1252"])
    new = ns["A2_CONTROL"].sub("", new)
    return ("fix" if new != text else "keep", new)


def old_c2_spans(text, ns):
    seen, lines, pos, fence = {}, [], 0, False
    for line in text.split("\n"):
        key = " ".join(line.split())
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
        if len(key) >= ns["C2_MIN_CHARS"] and not fence and not ns["C2_CODE"].search(line):
            lines.append((pos, pos + len(line), key))
            seen[key] = seen.get(key, 0) + 1
        pos += len(line) + 1
    out, first = [], set()
    for s, e, key in lines:
        if seen[key] >= ns["C2_MIN_REPEAT"]:
            if key in first:
                out.append((s, e, "C2-repeated-line"))
            first.add(key)
    return out


def old_f1(text, ns):
    ORG_VOICE, ORGANISATION, PUBLIC_ROLE = ns["ORG_VOICE"], ns["ORGANISATION"], ns["PUBLIC_ROLE"]
    DIGIT, PHONE, ADDRESS, TOLL_FREE, NOT_DIGIT = ns["DIGIT"], ns["PHONE"], ns["ADDRESS"], ns["TOLL_FREE"], ns["NOT_DIGIT"]
    EMAIL, _email, CONTACT_LINE = ns["EMAIL"], ns["_email"], ns["CONTACT_LINE"]
    lines = text.split("\n")
    org_page, has_org = [], {}

    def on_org_page():
        if not org_page:
            org_page.append(bool(ORG_VOICE.search(text)))
        return org_page[0]

    def org_near(i):
        for j in range(max(0, i - 6), min(len(lines), i + 7)):
            if j not in has_org:
                has_org[j] = ORGANISATION.search(lines[j]) is not None
            if has_org[j]:
                return True
        return False

    masked = set()
    for i, line in enumerate(lines):
        if DIGIT.search(line) and PHONE.search(line) and not (on_org_page() or org_near(i)):
            masked.update(NOT_DIGIT.sub("", m.group()) for m in PHONE.finditer(line) if not TOLL_FREE.match(m.group()))
    out = []
    for i, line in enumerate(lines):
        if "@" not in line and not DIGIT.search(line):
            out.append(line)
            continue
        new = EMAIL.sub(lambda m: _email(m, on_org_page() or org_near(i) or bool(PUBLIC_ROLE.search(
            "\n".join(lines[max(0, i - 2):i + 1])))), line) if "@" in line else line
        if PHONE.search(new) or ADDRESS.search(new):
            if not (on_org_page() or org_near(i)):
                new = PHONE.sub(lambda m: m.group() if TOLL_FREE.match(m.group()) else "<PHONE>", new)
                if len(line.strip()) <= CONTACT_LINE:
                    new = ADDRESS.sub("<ADDRESS>", new)
            elif masked:
                new = PHONE.sub(lambda m: "<PHONE>" if NOT_DIGIT.sub("", m.group()) in masked else m.group(), new)
        out.append(new)
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------- random texts

A2_CHARS = list("ab cd\n.") + ["\r\n", "\r", "\x00", "\x07", "\x1f", "\x7f", "\x80", "\x81", "\x8d", "\x92", "\x93",
                               "\x94", "\x96", "\x9d", "\x9f", "\xa0", "\xa9", "\xc2", "\xc3", "\xe2", "\xef", "\xbf", "’"]
C2_LINES = ["Share this article now", "Share  this article now", "  Share this article now ", "Read more about us here",
            "cd /etc/openvpn", "cd  /etc/openvpn", "# up ip route add", "x = f();", "if (a) {", "}", "a -> b here now",
            "key=value thing", "Joined: 02/15/2010", "```", "~~~", "  ```python", "short", "", "A plain line of text",
            "$ make install now", "$\tmake install now", "body: margin 0 auto;", "Amy :: permalink :: here"]
F1_LINES = ["Call 020 7946 0123", "Call 020 7946 0124 or 020 7946 0123", "Freephone 0800 310 2525", "Call 0800 310 2525",
            "Ring +44 20 7946 0999", "The clinic opens at nine.", "Our team will help.", "Contact us today.",
            "A note about the weather.", "Line with 42 numbers in it", "mail me: jo.smith" + "@" + "gmail.com",
            "12 High Street", "Fax 020 7946 0555", "1-800-555-0100 toll free", "(020) 7946 0321 home", ""]


def rand_text(rng, pool, n_max, sep):
    return sep.join(rng.choice(pool) for _ in range(rng.randint(0, n_max)))


class A2(unittest.TestCase):
    rid = "DA-A2-009"

    def test_hand_cases(self):
        ns = card(self.rid)
        for text in ("", "plain", "a\x00b", "a\r\nb", "x\x92s", "\x07then \x92 later", "\x92 then \x07", "Ã\x89ric",
                     "â\x80\x99", "me \x80\x93 let\x80\x99s", "only \xa9 latin-1", "\r", "\x81\x8d\x8f\x90\x9d"):
            self.assertEqual(ns["medicine_a2"](text), old_a2(text, ns), repr(text))

    def test_random_texts(self):
        ns, rng = card(self.rid), random.Random(1)
        for _ in range(N_RANDOM):
            text = rand_text(rng, A2_CHARS, 40, "")
            self.assertEqual(ns["medicine_a2"](text), old_a2(text, ns), repr(text))

    def test_no_control_character_skips_the_c1_steps(self):
        ns = card(self.rid)
        ns["A2_C1"] = spy = Spy(ns["A2_C1"])
        ns["medicine_a2"]("a clean text with curly ’quotes’ and é")
        self.assertEqual(spy.calls, 0)


class C2(unittest.TestCase):
    rid = "DA-C2-005"

    def test_hand_cases(self):
        ns = card(self.rid)
        cases = ["", "Share this article now\nA\nShare this article now\nB\nShare this article now",
                 "cd /etc/openvpn\nx\ncd /etc/openvpn\ny\ncd /etc/openvpn",
                 "cd /etc/openvpn\ncd /etc/openvpn\ncd  /etc/openvpn\nShare this article now",
                 "$ make install now\n$\tmake install now\n$ make install now\n$\tmake install now",
                 "```\nprint the report now\nprint the report now\nprint the report now\n```",
                 "print the report now\n```\nprint the report now\n```\nprint the report now\nprint the report now",
                 "~~~\nRead more about us here\n~~~\nRead more about us here\nRead more about us here"]
        for text in cases:
            self.assertEqual(ns["c2_spans"](text), old_c2_spans(text, ns), repr(text))

    def test_random_texts(self):
        ns, rng = card(self.rid), random.Random(2)
        for _ in range(N_RANDOM):
            text = rand_text(rng, C2_LINES, 30, "\n")
            self.assertEqual(ns["c2_spans"](text), old_c2_spans(text, ns), repr(text))

    def test_code_regex_runs_only_on_repeated_lines(self):
        ns = card(self.rid)
        ns["C2_CODE"] = spy = Spy(ns["C2_CODE"])
        ns["c2_spans"]("A first ordinary line\nA second ordinary line\nA third ordinary line\nx = f();\nx = f();")
        self.assertEqual(spy.calls, 0)
        ns["c2_spans"]("x = f(); here\nx = f(); here\nx = f(); here")
        self.assertEqual(spy.calls, 3)


class F1(unittest.TestCase):
    rid = "DA-F1-007"

    def test_hand_cases(self):
        ns = card(self.rid)
        filler = "\n".join("Line of an ordinary paragraph about the weather." for _ in range(6))
        cases = ["", "Call 020 7946 0123", "Call 020 7946 0123\n" + filler + "\nCall 020 7946 0123\nThe clinic opens.",
                 "The clinic opens.\nCall 020 7946 0123", "Contact us today.\nCall 020 7946 0123\n" + filler +
                 "\nCall 020 7946 0123\nThe clinic opens.", "Freephone 0800 310 2525\n" + filler + "\nThe clinic: 0800 310 2525",
                 "Call 020 7946 0123\nThe clinic opens.\n" + filler + "\nCall 020 7946 0124"]
        for text in cases:
            self.assertEqual(ns["medicine_f1"](text), old_f1(text, ns), repr(text))

    def test_random_texts(self):
        ns, rng = card(self.rid), random.Random(3)
        for _ in range(N_RANDOM):
            text = rand_text(rng, F1_LINES + ["A note about the weather."] * 8, 40, "\n")
            self.assertEqual(ns["medicine_f1"](text), old_f1(text, ns), repr(text))

    def test_masked_numbers_are_found_only_when_an_organisation_line_asks(self):
        ns = card(self.rid)
        ns["TOLL_FREE"] = spy = Spy(ns["TOLL_FREE"])
        spy.match_calls = 0
        real = spy.rx.match

        def match(*a):
            spy.match_calls += 1
            return real(*a)

        spy.match = match
        ns["medicine_f1"]("Call 020 7946 0123\nA note about the weather.")  # no organisation line: one pass, one match
        self.assertEqual(spy.match_calls, 1)


if __name__ == "__main__":
    unittest.main()
