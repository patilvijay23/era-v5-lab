# en-fineweb-edu (sample)

1 file(s): `en-fineweb-edu.parquet` (500 docs, input `3a0ad16983c0`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 12 | 1 | 1 | 0 | 498 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-C2-003` | 4 | 0 | 0.1 |
| `DA-C1-006` | 2 | 0 | 0.0 |
| `DA-C5-005` | 2 | 0 | 0.0 |
| `DA-B4-010` | 1 | 0 | 0.4 |
| `DA-C3-003` | 0 | 1 | 0.1 |
| `DA-D3-003` | 1 | 0 | 1.3 |
| `DA-A3-002` | 1 | 0 | 0.1 |
| `DA-B2-002` | 1 | 0 | 0.3 |
| **F2** (G9 fingerprints) | | 1 | |

## F2 drops by benchmark

By the first benchmark item each dropped doc matched. Item IDs only.

| benchmark | docs |
|---|---:|
| `milu` | 1 |

Items that dropped the most docs:

| item | docs |
|---|---:|
| `milu:test:19374` | 1 |
