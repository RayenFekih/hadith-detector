# Phase 4B runtime validation

Validated locally on 2026-10-14. The approved production engine is RapidFuzz, using
complete unigram-anchor retrieval with approximate first-word fallback. Both character
edits and internal source omissions are implemented together. There is no project Python
runtime distance fallback or acceleration extra. Python oracles remain repository-only.
No commit, push, release or corpus bundling was performed.

## Implemented behavior

- Instance `detect()` accepts `max_errors=0` and `max_missing_words=0`, independently
  validated nonnegative integers excluding booleans; minimum words remains positive.
- Two-pass verification discovers/ranks supported input spans without retaining all
  source paths, then recovers all supporting occurrences with canonical traces.
- Whole symbol endpoints, internal-only omissions, barriers, original offsets, eligible
  non-overlapping tails, duplicate identities and nullable URLs retain the agreed semantics.
- Frozen `WordAlignment` and `OmittedSourceToken` models are exported. Detection and
  occurrence models expose costs; occurrence serializers add alignment/omission lists.
  Exact results also include zero-cost traces. Constructor defaults preserve earlier calls.
- RapidFuzz is required as `>=3.14.6,<4`; `uv.lock` and benchmark reproduction use 3.14.6.
  Fuzzy helpers/imports initialize lazily once per instance. Exact zero-budget calls keep
  their existing index path. Distance and weighted-neighbor caches have finite limits.
- Normalization version 1 and index format 1 are unchanged. Existing Phase 3B resources
  load directly, without rebuilding or downloading. Source records are unchanged.

See [behavior and commands](fuzzy-runtime.md) for model fields and cache limits.

## Correctness and installation

The complete pinned corpus contains 14,940 records and 1,039,600 tokens. Every one of the
168 Phase 4A queries agrees with the saved independent exhaustive oracle on selected spans,
costs, identities, source occurrences, word indices, per-word edits and omitted tokens.
Each case was checked on its first call and three warm repetitions. All 168 Phase 3 exact
regressions also agree. Oracle evidence checksums and actual oracle rows were checked
before comparison; source fingerprints agree with the loaded runtime manifest.

Additional real-source cases used 99, 249 and 499 input words, each with one character
insertion and one internal source-word omission. Full input passages were recovered;
the independent exhaustive oracle checked every returned narration and canonical trace.
These three cases each returned one reference. They supplement, rather than replace,
the large-input filler cases from Phase 4A.

Synthetic tests include direct oracle comparisons, randomized alignments, combined
budgets, unknown words, repeated words, duplicate narrations, symbol omissions, barriers,
transpositions, adjacent quotations and eligible tails. Huge budgets are finite internally;
forced distance/neighbor-cache eviction retains identical results. Tests also cover lazy
loading, missing dependency errors, metadata snapshots and old model constructors.

Local production/exact/normalization tests passed on Python 3.11.15, 3.12.13, 3.13.14
and 3.14.6 on both Windows and Ubuntu 22.04 under WSL2. The existing Linux 3.11–3.14
and Windows 3.14 CI test matrix automatically includes the new production tests; hosted
CI has not been run in this session. No CI job downloads the full corpus.

The complete development/data/benchmark suite passes (125 tests). Ruff lint/format,
strict mypy, lock consistency and whitespace checks pass. Packaging tests build wheels
and sdists, rebuild without Git, verify the sole runtime requirement and absence of extras,
install dependencies in clean environments, and perform actual fuzzy detection with
network sockets forbidden. Corpus/index files, repository oracles, PyArrow and downloader
dependencies remain outside the installed wheel.

## Measured performance and memory

Windows 11 build 26200; Python 3.14.6; Intel64 Family 6 Model 183 Stepping 1;
RapidFuzz 3.14.6 selected `rapidfuzz.distance.metrics_cpp_avx2`. Resources loaded and
validated in 2.786 seconds. First fuzzy call, including lazy helpers/import, took 455 ms.
Times include typed result construction and full metadata snapshots; result serialization
and hashing for correctness comparison occur outside detection timing.

Warm values below aggregate three samples per query; p95 uses nearest rank.
Ordinary cases exclude short and large inputs: median 14.789 ms, p95 1,328.855 ms.

| Category | Warm median (ms) | Warm p95 (ms) |
| --- | ---: | ---: |
| Character edits | 11.834 | 130.882 |
| Omissions | 7.535 | 101.034 |
| Combined budgets | 12.572 | 587.391 |
| Destroyed seeds | 0.866 | 32.640 |
| Common phrases | 315.280 | 1,211.150 |
| Short/no guaranteed anchor | 589.349 | 13,009.454 |
| Mixed/full/normalized | 34.340 | 1,753.616 |
| Adversarial/barrier/negative | 2.744 | 1,923.918 |
| Approximately 1,024-token inputs | 72.513 | 85.796 |
| Approximately 4,096-token inputs | 232.899 | 248.704 |

The three long corrupted quotations took 1.163, 2.143 and 3.571 seconds respectively
on their measured calls. No universal numerical performance promise follows from these
samples. Common short phrases are expensive because every valid reference/occurrence is
returned; bounded character distance does not remove that retrieval and output cost.

A separate fresh-process memory probe loads no oracle trace files and runs no oracle
algorithms. It checked `edits-00`, `short-19` and `large-4096-0` against saved hashes,
including typed results and serialization. Baseline RSS was 26.8 MiB, post-load RSS
214.8 MiB, final RSS 258.8 MiB and peak working set 355.8 MiB. This is a representative
three-case process peak, not the full suite's production memory maximum.

The full validation process peaked at 479.2 MiB and ended at 303.5 MiB, including reading
large oracle evidence and running the independent long-case oracle. Its final distance
cache contained 50,000 entries; neighbor cache contained 15 keys and 77,637 word IDs.
Forced small-cache tests separately verify both key and total-word limits. Memory and
timings are machine/workload evidence, not cross-platform guarantees.

## Fingerprints and artifacts

Raw timing/report files stay ignored in `data/phase4b-validation`; existing prepared
corpus, runtime resources and research files are preserved. Reports contain operational
measurements; no persistent fuzzy index or new runtime data artifact is necessary.

| Evidence | SHA-256 |
| --- | --- |
| Corpus fingerprint | `87fd7b7824fe60063026a582a845082f7fc6fe88587cb1d0805dbae372ea01ed` |
| Runtime manifest | `925d19aff64d8ad0b8b9d732d060bbfabb3191f99b1b68e3fce5e09738dbf091` |
| Phase 4A queries | `55edff14c522104e15eb2a2ea93052aa1ea0ce35ad07c40c9438c9e0ce2f4aca` |
| Independent oracle rows | `3d64d68bd9e37fe10bac00f008cf398fa8ecf93505afb8b0680660a0f7971514` |
| Full validation report | `9b9635be292a0d0881139f3f306acb2e976cd01c78ffaf43660544c450dcbd75` |
| Fresh memory report | `65f10bc5ff8d77c8357a8281f7f5dfd3461399ffc377440f567a3ee8b256a2f5` |
| Dependency lock | `fc8695d4cd24d9b2fb95c87fad1efe8425620de1a0c95a85dff14aa2405b5391` |

The memory report records package-code fingerprints as well. Reproduce the full checks
with the command in [the guide](fuzzy-runtime.md); pass `--memory-only` in a new process
with a different output filename for the representative memory probe.

## Review boundary

Phase 4B remains provisional until review. Oracle agreement establishes matching
correctness on these cases, not real-world quotation accuracy or independent Hadith
authentication. Exhaustive large-budget/common-word searches can be costly; there is
no silent cap, concurrent-use guarantee, character edit script or word splitting/joining.
Final API configuration/serialization contracts and safe annotation belong to Phase 5.

Proposed commit boundaries, only when requested:

1. `feat: implement bounded fuzzy matching with RapidFuzz`
2. `test: validate fuzzy runtime and offline installations`
3. `docs: document fuzzy behavior and full-corpus validation`

Stop for review before Phase 5. No remote change, commit or release is implied.
