# code-go (train)

2 file(s): `part-00000.parquet` (61,393 docs, input `6b7b52e854df`), `part-00001.parquet` (21,874 docs, input `40aedd68c4ec`).
`clean.py` `97c1a55b89f4`; F2 set `2826a3b883210c653979103c09ce1c79e40fc4f7034b54027f2836482370d22a` (full set).

| docs | fixed by `clean.py` | dropped by `clean.py` | dropped by F2 | errors | kept |
|---:|---:|---:|---:|---:|---:|
| 83,267 | 45,098 | 6,312 | 96 | 0 | 76,859 |

## What each medicine did

Docs each rule changed or dropped. A doc fixed by three rules counts under each, so the rows add up to more than the docs fixed.

| rule | fixed | dropped | seconds |
|---|---:|---:|---:|
| `DA-B3-001` | 40,747 | 0 | 0.8 |
| `DA-E4-005` | 9,890 | 5 | 31.1 |
| `DA-E1-001` | 0 | 6,152 | 23.6 |
| `DA-B4-009` | 3,748 | 0 | 0.8 |
| `DA-E4-010` | 673 | 0 | 4.5 |
| `DA-A2-007` | 661 | 0 | 4.4 |
| `DA-C3-002` | 0 | 98 | 234.4 |
| **F2** (G9 fingerprints) | | 96 | |
| `DA-C1-004` | 68 | 0 | 7.0 |
| `DA-E2-001` | 0 | 57 | 42.8 |
| `DA-E3-004` | 39 | 0 | 255.7 |
| `DA-E3-003` | 34 | 0 | 61.2 |
| `DA-A6-001` | 18 | 0 | 54.8 |
| `DA-A1-001` | 5 | 0 | 0.7 |

## F2 drops by benchmark

By the first benchmark item each dropped doc matched. Item IDs only.

| benchmark | docs |
|---|---:|
| `swe_bench_pro` | 58 |
| `swe_bench_live` | 18 |
| `heldout_g5_v1` | 9 |
| `swe_bench_verified` | 4 |
| `livecodebench` | 3 |
| `hle` | 3 |
| `gaia` | 1 |

Items that dropped the most docs:

| item | docs |
|---|---:|
| `swe_bench_pro:test:instance_gravitational__teleport-1316e6728a3ee2fc124e2ea0cc6a02044c87a1` | 12 |
| `swe_bench_pro:test:instance_gravitational__teleport-2bb3bbbd8aff1164a2353381cb79e1dc93b90d` | 10 |
| `swe_bench_live:test:streamlink__streamlink-6111` | 10 |
| `swe_bench_pro:test:instance_flipt-io__flipt-406f9396ad65696d58865b3a6283109cd4eaf40e` | 10 |
| `swe_bench_pro:test:instance_flipt-io__flipt-02e21636c58e86c51119b63e0fb5ca7b813b07b1` | 4 |
| `swe_bench_live:test:icloud-photos-downloader__icloud_photos_downloader-1061` | 4 |
| `swe_bench_verified:test:django__django-16502` | 4 |
| `heldout_g5_v1:heldout:vault-go-test-000041` | 4 |
| `swe_bench_pro:test:instance_flipt-io__flipt-f1bc91a1b999656dbdb2495ccb57bf2105b84920` | 3 |
| `heldout_g5_v1:heldout:vault-go-test-000038` | 3 |
