Pipeline readiness review — current `g1-pipeline` at `94379a88aa4d769b8465889066b854a77a245950`, Nov 18, 2026.

**Assessment: a working, well-tested integration pipeline, but not yet ready to submit as the first-training-sources job.** PR #46 is merged and main is synced. The remaining work is principally a production clean-job adapter, complete/restartable sharding, unconditional artifact verification, and a pinned approved job configuration. Earlier PR-review findings must not be carried forward as if their fixes had not landed.

The review covers tracked pipeline, cleaner, dedup and shard code at this commit. Tests ran on an isolated `git archive` under `/tmp/pipeline-review-20261118`, leaving the user's unrelated working changes untouched. The latest local G1 export was synced at 2026-11-18 14:35 UTC; the code, rather than older chat claims, determines the implementation status below.

**What runs now**

`clean → overlap → dedup → apply → F2 → survivor loss → ledger → tokenize/shard → reconcile`

| Step | Current behavior | Outputs / limits |
|---|---|---|
| Clean | Run a configured script, script list/wrapper or explicit command, or adopt a previous output folder. The default is the spec-v1 tokenizer-sample runner. `spec_v1_1/use_clean.py` can load the current spec-v1.1 cleaner into a v1 tool. | Cleaned Parquet and cleaning reports. The default runner accepts only the 86-part sample-v0 manifest. Merely wrapping it does not lift that restriction. |
| Overlap | Actual `dedup/overlap.py` is now present. It computes H1/H2 duplicate evidence over cleaned train and held-out documents. Can run locally in the job or adopt returned outputs. | Matches, document-position metadata, matrix and summaries. Default settings expect the existing 38 packs. Input file checksum verification remains deferred in the overlap implementation. |
| Dedup | Actual `dedup/dedup.py` is present. Uses source priority and held-out protection to decide removals. H3 is not enabled in the default v1 config. | `remove_list.csv`, groups, log, summaries and validation evidence. No Parquet is removed at this stage. |
| Apply | Checks each listed position, doc ID and pack ID before filtering. Protects held-out documents, keeps order/schema, hard-links untouched files when possible, processes parts in parallel. | `deduped/` plus counts and input/output hashes. This is where dedup decisions actually change the data. |
| F2 | Separate stage after dedup/apply, using G9's fingerprint rules. Supports a process pool and completed-part reuse. Checks counts, input hashes, one fingerprint set and zero errors. | `final/` Parquet and per-part `.f2.json` reports. It runs on the configured train/held-out splits. Do not also enable F2 inside the clean step. |
| Survivor loss | Counts duplicate groups whose surviving copies F2 subsequently removed. | Report only; it does not restore removed copies. |
| Ledger | Per-document cleaning/dedup/F2 fate and final Parquet position. Mode C starts from cleaned data and has `clean_action: unknown`; mode B includes raw documents and infers keep/fix/drop from raw/cleaned text. | Per-pack/split Parquet, sample CSV and summary. Mode B now requires a matching cleaning report for every part, including input hash, input rows and actions. It does not provide per-rule decision IDs. |
| Tokenize/shard | Uses pinned p1536, required production `dataset_version`, whole documents with EOS, uint32 payload plus index/doc metadata/manifest/quality report. Uses `encode_batch_fast`. Decoded text is checked against tokenizer-normalized text. | One shard per train part, up to `2^26` tokens by default. Held-out parts remain unsharded. Secret-like, empty, special-containing and non-round-tripping documents are explicitly left out. |
| Reconcile | Joins each ledger-kept final position to shard document metadata or a reported exclusion reason. Rejects missing/duplicate/wrong-position documents. Default scope now comes from the ledger. | Per-document shard status and reconciliation summary. A ledger-kept document is not necessarily shipped: the separate reconciliation records downstream exclusions. |

This produces storage shards, not 4k/8k/16k training sequence packing or a training sampler. Those remain loader/training responsibilities.

**The committed default is not the production job**

I ran `run_pipeline.py --config pipeline.json --plan`. It exits successfully but plans only clean through ledger. The actual settings in [pipeline.json](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/pipeline/pipeline.json:12) are:

- spec-v1 `clean.json`, not the spec-v1.1 wrapper;
- tokenizer-sample-v0 input and manifest assumptions;
- real overlap/dedup stages;
- pooled F2 with 16 workers, apply with 4;
- intermediate Parquet retained;
- no enabled shard or reconcile stage, no actual `ledger.raw`, and no expected inventory.

`--plan` explicitly says `inventory: none` and `not a production run`. It does not prove input availability, runtime sample compatibility or a successful execution. A missing input folder does not make this syntactic plan fail.

There is no first-training-shards job request/config, `shards.template.json` or `expected_inventory.json` under `teams/01-data-a/jobs/` on this branch. Materials on another branch must be integrated and updated before pinning the final job.

**Protections already implemented**

- Input/output overlap checks, output-folder locks for apply/ledger/reconcile, temporary-file replacement, and ledger staging/rollback with ownership markers.
- Persistent file-identity-aware hashes; resumed stages must match recorded output digests. Settings and generated configs are recorded; wrapper commands can record tool hashes.
- Independent expected inventory before shards and after reconcile. With it the run requires raw-ledger mode B, both downstream stages and an end at reconcile. It checks listed/unlisted parts and packs, raw hashes and row counts, clean input-manifest identity and expected shard statuses.
- p1536 pin, required dataset-version plumbing, licence fields in shard manifests, and a stop on any truncated part. A truncated writer output can no longer be recorded as successful by the runner.
- `intermediates: keep` retains every stage's Parquet. `drop` is post-run cleanup: after reconciliation it verifies candidate shard files, hashes, header/size, index and metadata counts before removing covered `deduped/` and `final/` parts. It preserves cleaned input, held-out/unselected parts and reports. It does not reduce peak intermediate disk use or implement a single streaming raw-to-shard pass. A run after deletion is deliberately not resumable in place.

**Earlier review findings: current disposition**

| Earlier issue | Current result |
|---|---|
| Deleting inputs at `ledger.partial` / `ledger.old` | Guards and regression tests present. |
| Mixed short/long dictionary text inflating reads | Fixed for the reproduced case. Fresh-process rerun: largest batch **15.83 MiB**, peak Arrow allocation **50.20 MiB**, 727 kept; formerly 114 MiB / 230 MiB. |
| Ownership marker lost after cleanup failure | Fixed: marker remains while other children remain. Recovery regressions pass. |
| Deleting Parquet when shard payload/index is missing | Fixed for deletion: the new check refuses `drop` before deletion. Independently reproduced the refusal. |
| Missing pack quietly treated as unselected | Default ledger-derived scope and independent inventory checks now reject it. |
| Hard-coded sample dataset identity | Fixed: explicit `stages.shards.dataset_version` is required for pinned-tokenizer runs and passed through to the writer. Test-only tokenizer mode remains `test`. |

**What is missing, in priority order**

1. **General-input spec-v1.1 clean adapter — required for the actual training job.** [stage_args.py:26](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/pipeline/stage_args.py:26) still defaults to `run_tokenizer_sample.py`; its [manifest guard](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/spec_v1/run_tokenizer_sample.py:80) requires exactly 86 parts. The standalone `spec_v1/run_clean.py` accepts arbitrary supported pack files, but takes `--pack/--pack-id/--out`, writes flattened `<pack>_<part>_clean.parquet` names and a per-file summary, and reads whole packs into memory. It does not emit the aggregate `job_summary.json`, canonical split/pack layout and `reports/<split>/<part>.json` protocol the runner, raw ledger and shard provenance require. The adapter must reuse `spec_v1_1/use_clean.py` / the approved cleaner, preserve the input inventory/layout, write all required hashes/counts/provenance, handle every approved pack including the seven currently without family rules under an explicit policy, and leave F2 to its later stage. Simply changing a script path is insufficient. Owner: Sourav with Aneesha.

2. **Multi-shard rollover and complete coverage — required or an explicitly approved input-size restriction.** [shard_writer.py:181](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/shards/shard_writer.py:181) stops at the first whole document that would exceed the budget; it never opens another shard. The runner now fails safely on that truncation, but failing safely does not complete a large input. Allocate unique shard IDs across parts/rollovers, record part-to-multiple-shards coverage and update reconciliation, which currently reads one `shard_id` per part. Define handling for a single oversized document. Do not increase the storage budget merely to hide the missing rollover. Owner: Tejaskumar with Sourav for runner/reconcile changes.

3. **Atomic shard publication and restart — required for the scale run.** Payload, index, metadata and reports are currently written directly to their final names. The writer publishes a manifest before its final assertions, and [run_shards.py:114](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/shards/run_shards.py:114) refuses a run if any selected shard manifest already exists. It does not verify/reuse completed shards and continue unfinished work. Implement temporary artifact publication, completion last, compatible-output verification/reuse, and explicit handling of interrupted partial files. Apply/F2/ledger recovery must not be presented as shard-stage restart support.

4. **Explicit empty-part outcomes.** A final part emptied by dedup/F2 reaches [provenance.py:198](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/shards/provenance.py:198), where an empty pack-ID set fails the expected pack check. A nonempty part whose documents are all excluded during tokenization exits with `no document fits in --tokens`. Neither has a successful explicit empty/fully-excluded status with reconciled counts. Add those outcomes without creating invalid zero-token training shards.

5. **Unconditional artifact verification before declaring success — independently reproduced gap.** The new byte-level checks are called only by [drop():1141](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/pipeline/run_pipeline.py:1141). With `intermediates: keep`, the real runner and actual reconciliation/inventory checkpoints accepted complete document metadata but deliberately missing `.bin` and `.idx.npy` files from an external-writer stand-in. Every recorded check passed. `drop` correctly refused the same missing artifacts. The actual writer does self-check its outputs on ordinary successful writes, but the runner's independent acceptance is still metadata-based when files are retained. Make verification of all written shards part of successful completion in both modes; extend semantic checks as needed for tokenizer/release identity, token range/EOS and metadata offsets. Retaining Parquet is an audit/storage choice, not permission to skip shard validation. Suggested owner: Smita/Tejaskumar with Sourav.

6. **Bind adopted overlap/dedup results to the exact cleaned inputs — independently reproduced gap for adopt mode.** [counts_overlap():745](/home/vijay/projects/erav5/era-v5-lab/teams/01-data-a/pipeline/run_pipeline.py:745) checks names/counts and hashes of the overlap outputs, but not hashes of the cleaned input files. Replacing cleaned text while preserving positions, IDs and row counts still lets the runner accept the old adopted overlap/dedup fixtures and complete apply. The overlap implementation explicitly says input checksum verification is deferred. This is not a claim that a fresh all-stages run necessarily uses stale data; it is a provenance gap in the supported adoption path. Record and compare a cleaned-input manifest/per-part SHA-256 inventory, or require a separately verified binding before adoption. Rerun overlap/dedup after changing cleaner outputs instead of substituting the old sample results. Owner: Kunal/Sourav.

7. **Approved and complete job/config/metadata — required for submission.** Put the approved first-source manifest, independent expected inventory, raw roots, clean settings/pin, dedup policy, p1536 artifact/hash, production dataset version, full pack table, worker/resources and exact final commit together on this branch. The committed pack table contains **38 packs, 32 null lanes and zero licence fields**. `pack_table.py` permits omitting both licence fields, even with an inventory; it is not a release-admission gate. Dedup's default `licence_usable` is empty with `default_licence_usable: true`, and pack order/expected packs are the sample's frozen 38. Supply approved source eligibility and metadata rather than infer admission from the presence of licence text. Preflight those fields and tokenizer identity before spending hours on earlier stages. Owners: Vijay plus stage owners, G10/TSAI for admission.

8. **A reproducible environment and scale/resource envelope.** `spec_v1/requirements.txt` pins PyArrow **23.0.1**; `dedup/requirements_overlap.txt` pins **19.0.1**. They cannot both be satisfied as written by one environment. This review ran the listed suites successfully on 19.0.1, but the project needs one tested pipeline environment/lock, including `pandas`, CPU tokenizer/torch dependencies and offline tokenizer staging. The shard writer holds a whole part's text, Python token lists and flattened token output in memory; `run_clean.py` also loads the entire input part. The pipeline helpers' bounded batches do not bound those stages. Size representative parts, measure RSS and disk, set concurrency from the job's resources, and document remaining limits. Final raw-to-shards execution still needs intermediate Parquet space even if cleanup is enabled.

9. **Final rehearsal and release evidence.** On the exact final code/config/environment, run the approved cleaner, actual overlap/dedup/F2 and pinned p1536 through ledger/shards/reconcile/inventory. Include forced rollover, empty and all-excluded parts, an interruption/restart during shard writing, and negative cases for a missing/corrupt shard, unexpected input and mismatched pin. Keep before/after Parquet for the agreed audit. Archive logs, identities, hashes, counts and resource measurements; follow with independent decoded-text/G9 checks and the canonical shard inventory/handoff. Existing 40-check code-go evidence in the README is useful but refers to an older commit and test-only tokenizer mode; it does not discharge those production gates. Owners: Sourav/Tejaskumar; Vijay coordinates evidence and submission.

10. **Documentation and acceptance cleanup.** README/open-items still claim `dedup/` and `spec_v1_1/` are absent; both are now present. Example shard commands/config snippets need the newly required dataset version. The spec-v1.1 cleaner documentation records 27 harm PASS / 4 initial FAIL packs with proposed gold-contradiction exclusions; carry the approved disposition and remaining limitations into release evidence. Passing synthetic unit tests is not a new gold/admission approval. These are distinct from the missing adapter and writer functionality.

**Independent checks performed**

| Suite / check | Result |
|---|---|
| Pipeline suite | **480 passed, 2 skipped**, 5 Python fork warnings |
| Complete shard suite, including actual writer/runner | **92 passed** |
| Dedup suite | **158 passed, 2 skipped** |
| Spec-v1.1 suite | **1,874 passed**, 9 subtests passed |
| Real F2-runner and tokenizer-sample job tests | **17 passed** |
| Additional readiness probes | **2 failed, 1 passed**: success with missing shard payloads in keep mode; accepting stale adopted overlap after a text change; drop mode correctly refuses missing payloads |
| Previous mixed-width memory reproducer | **50.20 MiB** peak Arrow allocation; **15.83 MiB** largest batch; 727 kept |
| Generic `--plan` | Exit 0; only seven stages through ledger; explicitly not a production run |

Environment: Linux / Python 3.12.3, PyArrow 19.0.1, NumPy 2.2.6, pandas 2.3.3, SciPy 1.15.3, tokenizers 0.23.3, CPU PyTorch 2.5.0, tree-sitter 0.26.0, tree-sitter-language-pack 1.22.1. The shard suite used its intended public baseline tokenizer with `any_tokenizer`, downloaded at its pinned revision and verified against SHA-256 `01d968a7970b029c071b29f060abf6104b66168dedf2ff3b1a0290a545739fff`. Only its cache path was redirected to `/tmp` in the test harness; repo code was not changed. This was not a full job on the frozen p1536 artifact or real approved training corpus. Pipeline runner tests use stand-ins where documented; the shard suite exercises real writer code on synthetic data.

Supplemental probes are saved alongside this report in `test_pipeline_current_readiness_2026-11-18.py`; copy the file into the reviewed checkout's pipeline tests directory to reuse its fixtures. They run the actual runner/checkpoints and simulate an incomplete external writer or a changed cleaned file. No source fixes, commits, merges or external messages were made. All unrelated working changes were preserved.

**Completion order**

First land the production clean adapter and a real job template/inventory. In parallel implement rollover, empty statuses and atomic restart in the writer and its downstream map. Add unconditional artifact checks and bind adoption provenance. Freeze and validate metadata/environment, then perform the full failure-and-recovery rehearsal on the final commit. After that, pin the submission and collect the returned artifacts for independent release checks.
