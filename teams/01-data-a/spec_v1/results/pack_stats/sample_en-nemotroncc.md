# en-nemotroncc (sample)

1 file(s): `en-nemotroncc.parquet` (500 docs, input `6eae1507bc68`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 62 | 17 | 0 | 0 | 483 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-C1-006` | 26 | 0 | 0.0 |
| `DA-C2-003` | 16 | 0 | 0.1 |
| `DA-A1-004` | 14 | 0 | 0.0 |
| `DA-C3-003` | 0 | 12 | 0.3 |
| `DA-C3-001` | 0 | 5 | 0.0 |
| `DA-C5-005` | 4 | 0 | 0.0 |
| `DA-D3-003` | 3 | 0 | 1.1 |
| `DA-F1-005` | 1 | 0 | 7.5 |
