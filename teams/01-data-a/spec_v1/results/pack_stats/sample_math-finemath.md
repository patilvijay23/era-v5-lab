# math-finemath (sample)

1 file(s): `math-finemath.parquet` (500 docs, input `99aec0d9ece5`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 177 | 13 | 7 | 0 | 480 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-C1-001` | 97 | 0 | 3.6 |
| `DA-C2-001` | 51 | 0 | 0.1 |
| `DA-A1-005` | 15 | 0 | 0.0 |
| `DA-C3-004` | 0 | 12 | 0.1 |
| `DA-A3-001` | 10 | 0 | 0.0 |
| `DA-B4-001` | 9 | 0 | 0.1 |
| `DA-D3-005` | 7 | 1 | 0.6 |
| `DA-B5-001` | 7 | 0 | 0.1 |
| **F2** (G9 fingerprints) | | 7 | |
| `DA-A5-002` | 6 | 0 | 0.3 |
| `DA-C5-006` | 5 | 0 | 0.1 |
| `DA-C3-005` | 5 | 0 | 0.1 |
| `DA-A6-003` | 5 | 0 | 0.4 |
| `f1_rule.py` | 4 | 0 | 0.7 |
| `DA-B2-001` | 3 | 0 | 0.0 |

## F2 drops by benchmark

By the first benchmark item each dropped doc matched. Item IDs only.

| benchmark | docs |
|---|---:|
| `milu` | 5 |
| `mmlu` | 1 |
| `livecodebench` | 1 |

Items that dropped the most docs:

| item | docs |
|---|---:|
| `mmlu:test:5219` | 1 |
| `milu:test:10689` | 1 |
| `milu:test:16197` | 1 |
| `milu:test:10090` | 1 |
| `milu:test:11752` | 1 |
| `livecodebench:release_v6:3047` | 1 |
| `milu:test:16177` | 1 |
