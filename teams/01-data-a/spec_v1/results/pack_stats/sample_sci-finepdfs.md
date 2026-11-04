# sci-finepdfs (sample)

1 file(s): `sci-finepdfs.parquet` (500 docs, input `5a3228b797f5`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 45 | 13 | 3 | 0 | 484 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `f1_rule.py` | 15 | 1 | 8.0 |
| `DA-B2-003` | 10 | 0 | 0.1 |
| `DA-C1-007` | 9 | 0 | 0.0 |
| `DA-F1-006` | 0 | 9 | 0.0 |
| `DA-C3-006` | 4 | 1 | 0.0 |
| `DA-C2-004` | 5 | 0 | 0.0 |
| `DA-B5-002` | 4 | 0 | 0.0 |
| **F2** (G9 fingerprints) | | 3 | |
| `DA-C4-003` | 0 | 2 | 0.0 |
| `DA-B4-013` | 1 | 0 | 0.3 |
| `DA-A6-002` | 1 | 0 | 0.0 |

## F2 drops by benchmark

By the first benchmark item each dropped doc matched. Item IDs only.

| benchmark | docs |
|---|---:|
| `hle` | 2 |
| `mmlu` | 1 |

Items that dropped the most docs:

| item | docs |
|---|---:|
| `hle:test:6724d81d42ec04c22a24aa83` | 2 |
| `mmlu:test:5817` | 1 |
