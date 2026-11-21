"""Tests for the rules in sheets/proposals_english.md, loaded the way harmtest/harm_test.py loads them. All text is made up;
the phone numbers are in the UK range kept for drama (020 7946 0xxx).

  python3 -m unittest discover -s spec_v1_1/tests      (from teams/01-data-a)
"""
import sys
import unittest
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SPEC.parent / "harmtest"))
import harm_test  # noqa: E402  (only its loader is used; the file is not changed)

SHEET = SPEC / "sheets" / "proposals_english.md"
RULES, _ = harm_test.load_rules(SHEET)
RULES = RULES["RULES_BY_ID"]
FILLER = "\n".join(f"Line {k} of an ordinary paragraph about the weather." for k in range(6))


def doc(text, pack="en-dclm"):
    return {"doc_id": "0" * 16, "text": text, "url": "", "lang_label": "en", "pack_id": pack}


def run(rule_id, text, pack="en-dclm"):
    return RULES[rule_id](doc(text, pack))


class Sheet(unittest.TestCase):
    def test_the_five_proposals(self):
        self.assertEqual(sorted(RULES), ["DA-A2-009", "DA-B3-002", "DA-B4-014", "DA-C2-005", "DA-F1-007"])

    def test_every_rule_is_off_outside_the_english_packs(self):
        text = "the children\x92s <s>old</s> ${8,16}$\nCall 020 7946 0123"
        for rid in RULES:
            for pack in ("math-finemath", "code-go", None):
                self.assertEqual(run(rid, text, pack), ("keep", text), (rid, pack))


class A2(unittest.TestCase):
    def test_cp1252_quotes_become_characters(self):
        self.assertEqual(run("DA-A2-009", "the children\x92s books, \x93quoted\x94 \x96 here"),
                         ("fix", "the children’s books, “quoted” – here"))

    def test_utf8_punctuation_that_lost_its_first_byte(self):
        self.assertEqual(run("DA-A2-009", "you hate me \x80\x93 let\x80\x99s go"), ("fix", "you hate me – let’s go"))

    def test_utf8_punctuation_read_as_latin1(self):  # including \x9d, which cp1252 leaves undefined
        self.assertEqual(run("DA-A2-009", "Clayâ\x80\x99s â\x80\x9cliveâ\x80\x9d"), ("fix", "Clay’s “live”"))

    def test_a_two_byte_letter_read_as_latin1(self):  # a legit Latin-1 pair with no C1 control is left alone
        self.assertEqual(run("DA-A2-009", "Vyncke, Ã\x89ric Â© 2019"), ("fix", "Vyncke, Éric Â© 2019"))

    def test_a_euro_sign_and_a_dagger(self):
        self.assertEqual(run("DA-A2-009", "200\x80 or so \x86 note"), ("fix", "200€ or so † note"))

    def test_other_controls_still_go(self):
        self.assertEqual(run("DA-A2-009", "a\x00b\x81c\x07d\r\ne"), ("fix", "abcd\ne"))

    def test_clean_text_is_kept(self):
        self.assertEqual(run("DA-A2-009", "plain text, no controls"), ("keep", "plain text, no controls"))


class C2(unittest.TestCase):
    def test_repeated_boilerplate_still_goes(self):
        text = "Share this article now\nA\nShare this article now\nB\nShare this article now"
        self.assertEqual(run("DA-C2-005", text), ("fix", "Share this article now\nA\n\nB\n"))

    def test_dates_urls_and_separators_are_not_code(self):  # forum and blog furniture still goes
        for line in ("Joined: 02/15/2010", "Twitter: https://example.org/someone", "Amy :: permalink"):
            text = f"{line}\nA\n{line}\nB\n{line}"
            self.assertEqual(run("DA-C2-005", text), ("fix", f"{line}\nA\n\nB\n"), line)

    def test_repeated_code_and_config_lines_stay(self):
        text = "cd /etc/openvpn\nup ./start.sh\ncd /etc/openvpn\ndown ./stop.sh\ncd /etc/openvpn"
        self.assertEqual(run("DA-C2-005", text), ("keep", text))
        text = "# up ip route add via gw\nx\n# up ip route add via gw\ny\n# up ip route add via gw"
        self.assertEqual(run("DA-C2-005", text), ("keep", text))

    def test_lines_in_a_code_fence_stay(self):
        text = "```\nprint the report now\nprint the report now\nprint the report now\n```"
        self.assertEqual(run("DA-C2-005", text), ("keep", text))


class B4(unittest.TestCase):
    def test_math_after_a_dollar_stays(self):
        for text in ("Multiples of $8$ are: ${8,16,24,32}$ and so on.", "a vector ${\\bf a}$ here", "the set ${}^* N$ of"):
            self.assertEqual(run("DA-B4-014", text), ("keep", text), text)

    def test_a_template_expression_still_goes(self):
        self.assertEqual(run("DA-B4-014", "Hello ${user.name}, welcome."), ("fix", "Hello , welcome."))
        text = "The build sets the path ${@srctree} for each recipe, and the report shows ${.project.name} in its title."
        want = "The build sets the path  for each recipe, and the report shows  in its title."
        self.assertEqual(run("DA-B4-014", text), ("fix", want))


class F1(unittest.TestCase):
    def test_a_number_masked_on_one_line_is_masked_on_every_line(self):
        # line 0 is too far from "clinic" on line 8; line 7 is near it. Spec v1.1 masks line 0 only.
        text = "Call 020 7946 0123\n" + FILLER + "\nCall 020 7946 0123\nThe clinic opens at nine."
        want = "Call <PHONE>\n" + FILLER + "\nCall <PHONE>\nThe clinic opens at nine."
        self.assertEqual(run("DA-F1-007", text), ("fix", want))

    def test_a_number_only_near_an_organisation_stays(self):
        text = "The clinic opens at nine.\nCall 020 7946 0123"
        self.assertEqual(run("DA-F1-007", text), ("keep", text))

    def test_a_private_number_is_masked_on_every_line(self):
        text = "My number is 020 7946 0123\nagain: 020 7946 0123"
        self.assertEqual(run("DA-F1-007", text), ("fix", "My number is <PHONE>\nagain: <PHONE>"))

    def test_a_uk_freephone_number_is_toll_free(self):
        text = "Freephone 0800 310 2525"
        self.assertEqual(run("DA-F1-007", text), ("keep", text))


class B3(unittest.TestCase):
    def test_s_markers_go_and_the_text_stays(self):
        self.assertEqual(run("DA-B3-002", "keep <s>this old note</s> and this"), ("fix", "keep this old note and this"))

    def test_a_lone_s_tag_stays(self):  # an HTML reference list, not markup
        text = "<span> Defines a section\n<s> Defines strikethrough text\n<strike> Defines strikethrough"
        self.assertEqual(run("DA-B3-002", text), ("keep", text))

    def test_other_tags_are_not_touched(self):
        text = "a <strong>bold</strong> word and <span>x</span>"
        self.assertEqual(run("DA-B3-002", text), ("keep", text))


if __name__ == "__main__":
    unittest.main()
