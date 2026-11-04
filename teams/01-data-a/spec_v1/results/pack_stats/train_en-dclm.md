# en-dclm (train)

2 file(s): `part-00000.parquet` (46,245 docs, input `67b305d60aa0`), `part-00001.parquet` (15,122 docs, input `0dec2d4fc09d`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 61,367 | 8,401 | 1,155 | 37 | 0 | 60,175 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-C2-003` | 3,290 | 0 | 13.5 |
| `DA-C1-006` | 2,131 | 0 | 5.3 |
| `DA-A1-004` | 1,046 | 0 | 3.0 |
| `DA-C5-005` | 732 | 34 | 2.7 |
| `DA-C3-003` | 0 | 707 | 44.3 |
| `DA-D3-003` | 537 | 1 | 208.8 |
| `DA-F1-005` | 532 | 0 | 1984.9 |
| `DA-A2-008` | 269 | 0 | 2.6 |
| `DA-C3-001` | 0 | 261 | 0.5 |
| `DA-A3-002` | 241 | 4 | 15.9 |
| `DA-B1-002` | 230 | 0 | 0.6 |
| `DA-B4-010` | 93 | 4 | 77.1 |
| `DA-A5-001` | 94 | 0 | 1.5 |
| `DA-D4-001` | 0 | 88 | 18.5 |
| `DA-B2-002` | 80 | 0 | 50.6 |
| `DA-C5-002` | 0 | 56 | 125.8 |
| `DA-B4-012` | 54 | 0 | 6.9 |
| **F2** (G9 fingerprints) | | 37 | |
| `DA-B4-008` | 22 | 0 | 42.8 |
| `DA-B4-007` | 10 | 0 | 19.3 |

## F2 drops by benchmark

By the first benchmark item each dropped doc matched. Item IDs only.

| benchmark | docs |
|---|---:|
| `mmlu` | 13 |
| `milu` | 10 |
| `heldout_g5_v1` | 9 |
| `gaia` | 1 |
| `bfcl_v3` | 1 |
| `swe_bench_live` | 1 |
| `flores200` | 1 |
| `hle` | 1 |

Items that dropped the most docs:

| item | docs |
|---|---:|
| `heldout_g5_v1:heldout:fw2-ta-test-000028` | 8 |
| `mmlu:test:3828` | 7 |
| `milu:test:19996` | 1 |
| `milu:test:10567` | 1 |
| `milu:test:18206` | 1 |
| `heldout_g5_v1:heldout:fw2-kn-test-000019` | 1 |
| `milu:test:13908` | 1 |
| `mmlu:test:5681` | 1 |
| `gaia:2023:2b3ef98c-cc05-450b-a719-711aee40ac65` | 1 |
| `mmlu:test:5934` | 1 |
