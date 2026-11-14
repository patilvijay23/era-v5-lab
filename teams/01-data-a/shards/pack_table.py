"""What a shard manifest says about a pack: language, script, domain and capability lane, from pack_table.json.

  row("code-go")  ->  {"language": "go", "script": "Latn", "domain": "code", "lane": "code"}

A pack that is not in the table, or has a null field (the lane is null until the training plan names it), is an error:
nothing is guessed, because a manifest never changes after it is written.
"""
import json
from pathlib import Path

TABLE = Path(__file__).with_name("pack_table.json")
FIELDS = ("language", "script", "domain", "lane")


class PackTableError(Exception):
    pass


def load(path=TABLE):
    """The table as {pack_id: {language, script, domain, lane}}; every row has exactly FIELDS, each a string or null."""
    packs = json.loads(Path(path).read_text(encoding="utf-8"))["packs"]
    for pack, r in packs.items():
        if set(r) != set(FIELDS):
            raise PackTableError(f"{path}: {pack} has fields {sorted(r)}, expected {sorted(FIELDS)}")
        for field, value in r.items():
            if value is not None and not (isinstance(value, str) and value):
                raise PackTableError(f"{path}: {pack}.{field} must be a non-empty string or null, not {value!r}")
    return packs


def row(pack_id, table=None):
    """The pack's row, with no null field; PackTableError says what is missing."""
    table = load() if table is None else table
    if pack_id not in table:
        raise PackTableError(f"{pack_id} is not in pack_table.json")
    missing = [f for f in FIELDS if table[pack_id][f] is None]
    if missing:
        raise PackTableError(f"{pack_id} has no {' or '.join(missing)} in pack_table.json")
    return dict(table[pack_id])
