"""Tests for pack_table.py and pack_table.json (the real table, plus made-up tables for the errors).

  python -m pytest teams/01-data-a/shards/tests/test_pack_table.py
"""
import json
import sys
from pathlib import Path

import pytest

SHARDS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SHARDS))
sys.path.insert(0, str(SHARDS.parent / "spec_v1"))
import pack_table  # noqa: E402

SCRIPT = {"bn": "Beng", "gu": "Gujr", "hi": "Deva", "kn": "Knda", "ml": "Mlym", "mr": "Deva", "or": "Orya", "sa": "Deva",
          "ta": "Taml", "te": "Telu"}


@pytest.fixture(scope="module")
def table():
    return pack_table.load()


def test_table_has_the_38_week2_packs(table):
    kinds = {k: sorted(p for p in table if p.startswith(k + "-")) for k in ("cadj", "code", "en", "ind", "math", "sci")}
    assert [len(v) for v in kinds.values()] == [3, 6, 4, 22, 2, 1]
    assert sum(len(v) for v in kinds.values()) == len(table) == 38


def test_domain_agrees_with_clean_py(table):
    clean = pytest.importorskip("clean")
    for pack, family in clean._FAMILY.items():
        assert table[pack]["domain"] == family, pack


def test_indic_rows_follow_the_pack_name(table):
    for pack, r in table.items():
        if pack.startswith("ind-"):
            lang = pack.split("-")[1]
            assert (r["language"], r["script"], r["domain"]) == (lang, SCRIPT[lang], "indic"), pack


def test_code_rows_follow_the_pack_name(table):
    for pack, r in table.items():
        if pack.startswith("code-"):
            assert r == {"language": pack[5:], "script": "Latn", "domain": "code", "lane": "code"}, pack


def test_row_matches_the_committed_sample():
    sample = json.loads((SHARDS / "sample" / "code-go-train-000000.json").read_text(encoding="utf-8"))
    r = pack_table.row("code-go")
    assert r == {k: sample[v] for k, v in (("language", "language"), ("script", "script"), ("domain", "domain"),
                                           ("lane", "capability_lane"))}


def test_a_null_lane_is_refused(table):
    assert table["en-dclm"]["lane"] is None  # until the training plan names the lanes
    with pytest.raises(pack_table.PackTableError, match="en-dclm has no lane"):
        pack_table.row("en-dclm", table)


def test_an_unknown_pack_is_refused(table):
    with pytest.raises(pack_table.PackTableError, match="no-such-pack is not in pack_table.json"):
        pack_table.row("no-such-pack", table)


def test_row_is_a_copy(table):
    pack_table.row("code-go", table)["lane"] = "changed"
    assert table["code-go"]["lane"] == "code"


@pytest.mark.parametrize("bad, message", [
    ({"language": "go", "script": "Latn", "domain": "code"}, "has fields"),
    ({"language": "go", "script": "Latn", "domain": "code", "lane": "code", "x": "y"}, "has fields"),
    ({"language": "", "script": "Latn", "domain": "code", "lane": "code"}, "non-empty string or null"),
    ({"language": "go", "script": 7, "domain": "code", "lane": "code"}, "non-empty string or null"),
])
def test_a_malformed_row_is_refused(tmp_path, bad, message):
    path = tmp_path / "t.json"
    path.write_text(json.dumps({"packs": {"code-go": bad}}), encoding="utf-8")
    with pytest.raises(pack_table.PackTableError, match=message):
        pack_table.load(path)
