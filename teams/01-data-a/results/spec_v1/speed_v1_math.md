# clean.py speed log: math packs

Follow-up to [speed_v1.md](speed_v1.md) (English rules) and [speed_v1_code.md](speed_v1_code.md) (code rules), in the same format. Spec v1.1, Gate 2. A log of the slow rules that run on the math packs (`math-finemath`, `math-megamath`) and were sped up: what the fix was, docs/s per core before and after, and the checks showing that nothing else changed. Last updated 12 Nov 2026. Reports counts, hashes and timings only, never document text.

Every fix passes the same three checks before it is logged:

1. **Output sha256 unchanged** on all 13 sample packs (`doc_id`, final action and final cleaned text of every document, in order).
2. **Harm tests unchanged** (every rule and `clean()` on each pack, same harm result and same gold changed/dropped counts).
3. **Pytest suite passes.**

## 1. Where the time went (profile before any fix)

Per-rule profile of the 500-document packs, one core (`spec_v1/run_clean.py`), the rules that ran:

| pack | slowest rules (share of rule time, ms per document) |
|---|---|
| math-finemath | `DA-C1-001` 64.1% (3.974), `f1_rule.py` 10.8% (0.669), `DA-D3-005` 6.0% (0.364), `DA-A6-003` 4.7% (0.287) |
| math-megamath | `f1_rule.py` 43.1% (0.867), `DA-D3-005` 23.9% (0.480), `DA-A5-002` 15.5% (0.306) |

`DA-C1-001` runs on `math-finemath` only and fixes about one document in five, so it was the first target. The megamath profile has no such outlier.

## 2. Speed, docs/s per core, before and after each fix

500-doc sample packs, one core pinned to CPU 0, `clean()` loop only, best of 3 passes, before and after timed back to back on the same machine. The rule time is the per-document time of that rule alone, from the per-rule profile.

| # | rule (what it checks) | math-finemath docs/s | math-megamath docs/s | rule time math-finemath, ms/doc |
|---|---|---|---|---|
| 1 | `DA-C1-001` (site boilerplate lines) | 173.7 to 355.3 (2.05x) | 521.6 to 521.0 (1.00x, rule does not run) | 3.974 to 0.654 |

The other 11 packs of the 13 are unchanged (1.0x to 1.1x, timing noise): the rule runs on `math-finemath` only.

## 3. Status of each fix

| # | rule | output sha256 | harm tests | pytest | documents changed, math-finemath, 500 docs | `clean.py` before | `clean.py` after | commit |
|---|---|---|---|---|---|---|---|---|
| 1 | `DA-C1-001` | same, 13 of 13 | unchanged | 2242 passed | rule ran on 487, fixed 97, dropped 0 | `22d818c72c9f` | `6f99ff4d9ab4` | this commit |

The baseline is `clean.py` `22d818c72c9f` (commit `cc6f4c8`). Pytest counts are the whole suite at that commit (1 test skipped, 42 subtests passed). The output sha256 of each pack is the same as in [speed_v1.md section 6](speed_v1.md#6-output-sha256-of-the-13-sample-packs-identical-before-and-after-every-fix) (`math-finemath` `4e79a08fd226f614`, `math-megamath` `51c5b8452f45d195`), so before and after are byte-identical there too. The rule does not run on `math-megamath`, so the megamath figures show only that nothing else moved.

## 4. What each fix did

1. **`DA-C1-001`, site boilerplate (menus, footers, forum chrome).** The rule deletes a line that is a known chrome phrase, or that contains one of 83 site phrases (`C1_SITE`, one case-insensitive regex) and is at most 120 characters. It searched `C1_SITE` on every line and only then looked at the length, so about two thirds of the searches were on lines that are kept whatever they hold, and each search tries 83 alternatives at every position. The length test now comes first. On a pure-ASCII line the search also uses the lower-cased pattern on the lower-cased line, which gives the same answer as `(?i)` because every escape in the pattern is lower-case and it has no non-ASCII character. A non-ASCII line (about 9% of lines) still uses the original `(?i)` regex, so letters like `İ`, `ſ` and the Kelvin sign `K`, which `(?i)` treats specially, behave as before. The rule is unchanged otherwise. Edited in `specv1.md` and `medicine_math.md`.

The tests are in `tests/spec_v1/test_speed_equivalence_math.py`, against a frozen copy of the old rule in `tests/spec_v1/math_speed_reference.py`: a made-up line for each of the 83 alternatives in upper, lower and mixed case and at several positions, a sweep of line lengths 1 to 124 around the 120 limit, non-ASCII cases, 4,000 random documents (1,500+ fixed, so both outcomes occur), and 20,000 random ASCII strings compared directly against the old regex. Four deliberate breaks of the fix (no ASCII test, limit 119, line not lower-cased, no length limit) each made the new tests fail.

## 5. Next slowest rules

After fix 1, on math-finemath: the shared `f1_rule.py` is now the slowest at 23.1% of the time (0.671 ms/doc), then `DA-C1-001` itself at 22.6% (0.654), `DA-D3-005` 12.9% (0.366) and `DA-A6-003` 10.3% (0.293). On math-megamath (unchanged): `f1_rule.py` 43.1% (0.867 ms/doc), `DA-D3-005` 23.9% (0.480) and `DA-A5-002` 15.5% (0.306). The shared F1 rule already has a code-pack fast path ([speed_v1_code.md](speed_v1_code.md)); the math path has not been looked at yet.

## 6. Method

- **Machine:** x86_64, Python 3.12.15, one run at a time pinned to CPU 0 (`taskset -c 0`). Timings vary by about 5%, so treat ratios under 1.1x as about equal.
- **Versions compared:** `clean.py` at `cc6f4c8` against the rebuilt working copy; only `clean.py` differs between the two trees.
- **Packs:** the 13 original diagnosis packs (500 documents each), in a folder of exactly those 13, as `speed_compare.sh` expects.
- **Tools and command**, from the repository root:

```bash
teams/01-data-a/oneoff/speed_compare.sh --packs <folder with the 13 packs> --work <scratch folder> \
  --rules DA-C1-001 --profile-packs "math-finemath math-megamath"
```

The routine is in [oneoff/speed_handoff.md](../../oneoff/speed_handoff.md).
