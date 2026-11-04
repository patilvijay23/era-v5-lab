# math-megamath (sample)

1 file(s): `math-megamath.parquet` (500 docs, input `07cdf1aa40a5`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 500 | 62 | 10 | 2 | 0 | 488 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `f1_rule.py` | 26 | 0 | 1.0 |
| `DA-A5-002` | 11 | 0 | 0.4 |
| `DA-C5-001` | 0 | 10 | 0.0 |
| `DA-A3-001` | 8 | 0 | 0.0 |
| `DA-B2-001` | 6 | 0 | 0.0 |
| `DA-B4-001` | 5 | 0 | 0.1 |
| `DA-C5-006` | 4 | 0 | 0.1 |
| `DA-D3-005` | 3 | 0 | 0.7 |
| **F2** (G9 fingerprints) | | 2 | |
| `DA-B5-001` | 1 | 0 | 0.1 |

## F2 drops by benchmark

By the first benchmark item each dropped doc matched. Item IDs only.

| benchmark | docs |
|---|---:|
| `mmlu` | 1 |
| `livecodebench` | 1 |

Items that dropped the most docs:

| item | docs |
|---|---:|
| `mmlu:test:5219` | 1 |
| `livecodebench:release_v6:2953` | 1 |
