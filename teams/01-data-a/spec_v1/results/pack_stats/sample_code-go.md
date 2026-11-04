# code-go (sample)

1 file(s): `code-go.parquet` (500 docs, input `30fc352199a6`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 260 | 44 | 0 | 0 | 456 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-B3-001` | 247 | 0 | 0.0 |
| `DA-E4-005` | 47 | 1 | 0.1 |
| `DA-E1-001` | 0 | 42 | 0.1 |
| `DA-B4-009` | 18 | 0 | 0.0 |
| `DA-C1-004` | 2 | 0 | 0.0 |
| `DA-A6-001` | 2 | 0 | 0.2 |
| `DA-E4-010` | 2 | 0 | 0.0 |
| `DA-E3-003` | 1 | 0 | 0.2 |
| `DA-A4-002` | 1 | 0 | 0.1 |
| `DA-C3-002` | 0 | 1 | 0.7 |
| `DA-A2-007` | 1 | 0 | 0.0 |
