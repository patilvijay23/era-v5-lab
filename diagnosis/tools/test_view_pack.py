import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("view_pack.py")
spec = importlib.util.spec_from_file_location("view_pack", MODULE_PATH)
vp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vp)


def test_unicode_range_keeps_ascii_inside_indic():
    s = "कs् १0७"
    out = vp.unicode_range(s, 0, len(s))
    assert "U+0073" in out and "LATIN SMALL LETTER S" in out
    assert "U+0030" in out and "DIGIT ZERO" in out
    assert "U+094D" in out and "DEVANAGARI SIGN VIRAMA" in out


def test_control_name_carriage_return():
    assert vp.unicode_name("\r") == "CARRIAGE RETURN"
    out = vp.audit_report("a\rb")
    assert "U+000D CARRIAGE RETURN" in out


def test_nfc_candidate_ra_nukta():
    s = "शेतकऱ्यांना"
    found = vp.nfc_candidates(s)
    assert any(src.startswith("ऱ") and "ऱ" in dst for _, src, dst in found)


def test_nfc_does_not_call_spaced_matra_a5():
    s = "क ि"
    assert vp.nfc_candidates(s) == []


def test_g1_space_before_matra():
    s = "क ि"
    found = vp.g1_candidates(s)
    assert any(i == 2 and ch == "ि" and prev == " " for i, ch, prev in found)


def test_g1_ascii_before_virama():
    s = "कs्"
    found = vp.g1_candidates(s)
    assert any(ch == "्" and prev == "s" for _, ch, prev in found)


def test_joiners_not_replaced_or_called_hidden_damage():
    s = "क्\u200dष"
    # Raw text remains byte/code-point identical; diagnostics may report the joiner,
    # but the G1 candidate detector must not call the virama/joiner sequence broken.
    assert s == "क्\u200dष"
    assert not vp.g1_candidates(s)
    hidden = vp.hidden_characters(s)
    assert any(ch == "\u200d" for _, ch in hidden)


def test_mixed_digit_candidate():
    s = "सन 2026 आणि १0७"
    assert vp.mixed_digit_candidates(s) == [(s.index("१0७"), "१0७")]


def test_no_2000_character_cutoff():
    s = "अ" * 2437 + "ऱ"
    report = vp.audit_report(s)
    assert "2437" in report
    assert "U+0930" in report


def test_validate_row_errors_cleanly():
    try:
        vp.validate_row({"doc_id": "x", "source": "s", "lang_label": "mr"}, 0)
    except ValueError as e:
        assert "missing required columns" in str(e)
    else:
        raise AssertionError("expected ValueError")


def run_all():
    tests = [obj for name, obj in globals().items() if name.startswith("test_") and callable(obj)]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"\n{len(tests)} tests passed")


if __name__ == "__main__":
    run_all()
