# code-python (sample)

1 file(s): `code-python.parquet` (500 docs, input `b79698620cd7`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 319 | 16 | 0 | 0 | 484 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-B3-001` | 272 | 0 | 0.0 |
| `DA-E4-010` | 59 | 0 | 0.0 |
| `DA-B4-009` | 59 | 0 | 0.0 |
| `DA-A2-007` | 17 | 0 | 0.0 |
| `DA-E1-004` | 0 | 16 | 0.0 |
| `f1_rule.py` | 2 | 0 | 1.9 |
