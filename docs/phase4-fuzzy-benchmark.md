# Phase 4A fuzzy benchmark and dependency recommendation

Validated on 2026-10-13. These are repository experiments, not a public fuzzy API.
Installed runtime dependencies remain unchanged. No acceleration extra, Phase 4B
implementation, commit, push, publication or corpus bundling was performed.

## Recommendation

Use **guaranteed exact unigram anchors with approximate first-word fallback** for
fuzzy retrieval, retaining the existing trigram index for the exact fast path.
The hybrid remains complete but does not offer a consistent advantage here; the
anchor strategy is simpler and retrieves fewer candidate starts in this suite.

The maintainer selected **RapidFuzz as the sole required production distance engine**
on 2026-10-14. The independent Python oracle and bounded Python benchmark implementation
remain repository-only correctness and performance tools. No project-maintained Python
runtime fallback or acceleration extra is planned.

The original benchmark recommendation was optional acceleration: the scalar speedup is
substantial and cold vocabulary comparisons benefit, while warm end-to-end anchor timings
are similar. The selected design also prioritizes maintaining one production engine and
delegating the distance kernel to upstream. This decision does not imply a measured warm
detector speedup. The measurements below are unchanged; Phase 4B implementation still
requires approval.

## Evidence and method

- Complete pinned corpus: 14,940 records, 1,039,600 tokens, 40,949 normalized words.
- Source revision: `cc6972dae1f46f5f5e2b65e877d24c4539bc4391`.
- Corpus fingerprint: `87fd7b7824fe60063026a582a845082f7fc6fe88587cb1d0805dbae372ea01ed`.
- Seed 42; 160 ordinary fuzzy cases in eight categories plus eight larger inputs.
- All six strategy/backend combinations match the independent oracle on selected
  input spans, costs, identities, every source occurrence and canonical word traces.
- Agreement is checked before timing, on all three warm repetitions, and after
  posting-index serialization/reload. All 168 saved exact cases pass at zero budgets.
- Six independently constructed posting artifacts are byte-identical.
- Query and 10,000-pair scalar workload rebuilds are byte-identical.
- The oracle uses independent unbounded character distance and jump alignment;
  prototypes use bounded distance and separate align/skip transitions. Tiny direct
  path enumeration independently checks matching, costs and trace canonicalization.
- Both share established normalization and presentation. Exact zero-budget checks
  reuse the independent Phase 3 oracle and exact prototype verifier, then add traces.
- Each combination runs sequentially in a fresh process. Python workers never import
  RapidFuzz. Neither backend changes retrieval order, cache policy or logical work.
- Source/input segment endpoints are precomputed for all strategies. Preliminary
  runs with repeated endpoint scans were discarded; only final matching code is measured.

Environment: Python 3.14.6; Unicode 16.0.0;
Windows-11-10.0.26200-SP0; Intel64 Family 6 Model 183 Stepping 1, GenuineIntel;
20 logical CPUs; psutil 7.2.2;
RapidFuzz 3.14.6; uv 0.11.26.
Native backend on tested systems: `rapidfuzz.distance.metrics_cpp_avx2`.

## Scalar distance and memory

The uncached microbenchmark includes identical wrapper short circuits and returned-score
checks. Three repetitions compare the same 10,000 pairs. Long synthetic 64/128-character
cases and unrestricted cutoffs heavily influence the aggregate; this is not a detector
speedup or a claim about typical Arabic word lengths.

| Strategy process | Backend | 10k pairs median ms | Pairs/s | Import ms | Import RSS MiB | Peak RSS MiB | Final RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| first | python | 574.784 | 17,398 | 0.005 | 0.00 | 441.3 | 307.3 |
| first | rapidfuzz | 2.943 | 3,398,240 | 15.317 | 1.55 | 442.4 | 306.3 |
| anchors | python | 569.177 | 17,569 | 0.005 | 0.00 | 441.5 | 302.2 |
| anchors | rapidfuzz | 3.033 | 3,296,740 | 17.874 | 1.68 | 442.9 | 303.8 |
| hybrid | python | 578.162 | 17,296 | 0.005 | 0.00 | 443.6 | 301.2 |
| hybrid | rapidfuzz | 3.110 | 3,215,848 | 15.946 | 1.74 | 441.6 | 302.9 |

Across process samples, aggregate scalar acceleration is **188.2x**.
Import-only RSS overhead is approximately 1.6-1.7 MiB on this Windows machine.
Recorded installed RapidFuzz files total 6,559,647 bytes
(6.26 MiB), excluding unrecorded bytecode caches. Whole-process peak differences are
small and include allocators, corpus loading, caches, traces, serialization and reload;
they should not be interpreted as precise native-kernel allocation differences.

| Word length / cutoff | Pairs | Python median batch ms | RapidFuzz median batch ms | Speedup |
| --- | ---: | ---: | ---: | ---: |
| length=1-4/cutoff=0 | 326 | 0.146 | 0.064 | 2.30x |
| length=1-4/cutoff=1 | 351 | 0.642 | 0.098 | 6.58x |
| length=1-4/cutoff=2 | 346 | 0.746 | 0.097 | 7.67x |
| length=1-4/cutoff=3 | 403 | 0.836 | 0.118 | 7.10x |
| length=1-4/cutoff=unrestricted | 237 | 0.569 | 0.083 | 6.87x |
| length=17+/cutoff=0 | 286 | 33.649 | 0.118 | 285.65x |
| length=17+/cutoff=1 | 285 | 41.440 | 0.125 | 330.99x |
| length=17+/cutoff=2 | 286 | 47.926 | 0.128 | 373.84x |
| length=17+/cutoff=3 | 285 | 53.275 | 0.130 | 408.86x |
| length=17+/cutoff=unrestricted | 286 | 372.825 | 0.137 | 2729.32x |
| length=5-8/cutoff=0 | 1358 | 0.668 | 0.243 | 2.75x |
| length=5-8/cutoff=1 | 1325 | 3.629 | 0.363 | 10.00x |
| length=5-8/cutoff=2 | 1340 | 4.848 | 0.390 | 12.44x |
| length=5-8/cutoff=3 | 1336 | 5.791 | 0.400 | 14.46x |
| length=5-8/cutoff=unrestricted | 1372 | 6.906 | 0.479 | 14.41x |
| length=9-16/cutoff=0 | 30 | 0.010 | 0.005 | 1.85x |
| length=9-16/cutoff=1 | 40 | 0.186 | 0.012 | 15.39x |
| length=9-16/cutoff=2 | 32 | 0.218 | 0.011 | 20.39x |
| length=9-16/cutoff=3 | 41 | 0.284 | 0.012 | 22.91x |
| length=9-16/cutoff=unrestricted | 35 | 0.343 | 0.014 | 25.21x |

## End-to-end detection

Warm median and nearest-rank p95 aggregate three samples per query. Timed calls include
normalization, retrieval, verification, passage selection and complete experimental
traces; JSON hashing is outside timing. Full narration metadata is referenced by identity
rather than copied into each result, so Phase 4B typed-model costs require remeasurement.

The first correctness-pass times use progressively populated caches; they are not fresh
processes per query. The separate first-call column below measures the first case with
empty application caches. Cache limits are 50,000 distance entries and 4,096 neighbor
lists on both backends. Raw `kernel_calls` counts cache misses, including shared
short circuits. OS file caches were not flushed and timing noise remains.

| Strategy | Backend | Corpus verification s | Index/helper setup s | Reload s | First call ms | Retrieved starts (one pass) | Final distance entries | Evictions including regression checks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| first | python | 15.599 | 1.815 | 3.327 | 74.449 | 36,525,170 | 50,000 | 28,142,248 |
| first | rapidfuzz | 14.851 | 1.413 | 3.297 | 32.232 | 36,525,170 | 50,000 | 28,142,248 |
| anchors | python | 14.723 | 1.415 | 3.329 | 6.727 | 10,634,876 | 50,000 | 5,599,269 |
| anchors | rapidfuzz | 14.800 | 1.394 | 3.394 | 5.889 | 10,634,876 | 50,000 | 5,599,269 |
| hybrid | python | 14.778 | 1.421 | 3.340 | 5.908 | 10,945,283 | 50,000 | 5,620,557 |
| hybrid | rapidfuzz | 14.742 | 1.442 | 3.436 | 6.054 | 10,945,283 | 50,000 | 5,620,557 |

Corpus verification regenerates prepared tokens; this is not a production startup
estimate. All strategies retain both unigram and trigram tables. The anchor strategy
reduces retrieved starts from 36,525,170 to 10,634,876 in this workload; the hybrid
retrieves 10,945,283. Short cases requiring approximate fallback account for much of
the remaining work. Posting artifacts contain no new fuzzy-specific persistent index.

| Strategy | Category | Python median / p95 ms | RapidFuzz median / p95 ms | Warm speedup | First-pass median Python / RapidFuzz ms |
| --- | --- | ---: | ---: | ---: | ---: |
| first | adversarial | 87.022 / 6716.084 | 89.719 / 6559.067 | 0.97x | 130.991 / 105.330 |
| first | combined | 435.815 / 2295.182 | 422.654 / 2235.370 | 1.03x | 620.039 / 496.183 |
| first | common | 312.085 / 1339.402 | 311.634 / 1320.266 | 1.00x | 389.858 / 325.804 |
| first | destroyed-seeds | 71.620 / 1030.699 | 71.839 / 1094.978 | 1.00x | 116.914 / 81.642 |
| first | edits | 495.875 / 4311.751 | 443.283 / 3198.876 | 1.12x | 529.431 / 451.788 |
| first | large-1024 | 1002.308 / 2962.872 | 978.456 / 2821.583 | 1.02x | 1117.029 / 1025.523 |
| first | large-4096 | 1235.276 / 4276.798 | 1269.924 / 4148.488 | 0.97x | 1450.519 / 1305.355 |
| first | mixed | 1437.596 / 12864.050 | 1442.390 / 12583.948 | 1.00x | 1616.145 / 1465.176 |
| first | omissions | 204.677 / 3484.880 | 166.646 / 1584.595 | 1.23x | 311.604 / 190.126 |
| first | short | 295.068 / 5798.983 | 294.329 / 5375.753 | 1.00x | 351.266 / 266.709 |
| anchors | adversarial | 3.922 / 1855.113 | 3.878 / 1858.686 | 1.01x | 4.966 / 4.790 |
| anchors | combined | 13.158 / 633.058 | 14.136 / 630.833 | 0.93x | 16.628 / 14.137 |
| anchors | common | 184.462 / 676.364 | 182.279 / 698.576 | 1.01x | 204.110 / 158.941 |
| anchors | destroyed-seeds | 2.322 / 20.400 | 2.343 / 22.064 | 0.99x | 2.571 / 2.448 |
| anchors | edits | 10.881 / 156.405 | 10.590 / 161.470 | 1.03x | 12.396 / 10.828 |
| anchors | large-1024 | 72.941 / 90.533 | 74.501 / 88.554 | 0.98x | 76.232 / 73.961 |
| anchors | large-4096 | 235.633 / 255.486 | 237.382 / 252.980 | 0.99x | 236.096 / 239.295 |
| anchors | mixed | 42.234 / 1920.448 | 44.398 / 1864.645 | 0.95x | 44.791 / 44.282 |
| anchors | omissions | 8.852 / 100.992 | 8.710 / 98.795 | 1.02x | 9.384 / 9.589 |
| anchors | short | 298.076 / 5885.919 | 296.142 / 5472.274 | 1.01x | 369.739 / 306.769 |
| hybrid | adversarial | 3.809 / 1869.710 | 3.855 / 1864.675 | 0.99x | 4.716 / 4.920 |
| hybrid | combined | 15.987 / 677.253 | 14.551 / 671.352 | 1.10x | 18.554 / 15.402 |
| hybrid | common | 186.827 / 695.837 | 183.385 / 680.263 | 1.02x | 170.212 / 190.309 |
| hybrid | destroyed-seeds | 2.440 / 20.442 | 2.372 / 21.974 | 1.03x | 2.616 / 2.576 |
| hybrid | edits | 10.511 / 163.874 | 9.643 / 159.384 | 1.09x | 11.902 / 10.213 |
| hybrid | large-1024 | 73.760 / 88.235 | 75.460 / 88.739 | 0.98x | 75.640 / 76.553 |
| hybrid | large-4096 | 238.700 / 255.959 | 242.105 / 254.416 | 0.99x | 239.905 / 241.768 |
| hybrid | mixed | 41.741 / 1936.645 | 42.463 / 1899.932 | 0.98x | 45.655 / 43.205 |
| hybrid | omissions | 6.866 / 100.339 | 5.973 / 100.671 | 1.15x | 7.887 / 6.040 |
| hybrid | short | 292.087 / 5923.833 | 287.284 / 5428.685 | 1.02x | 312.935 / 296.530 |

For ordinary categories excluding short and larger-input cases, warm anchor medians
are 13.763 ms (Python) and 14.605 ms (RapidFuzz). This difference does not demonstrate
a reliable native speed advantage. Anchor short-case first-pass medians improve from
369.739 ms to 306.769 ms; typical edit first-pass medians improve from 12.396 ms to
10.828 ms. Many warm word costs are cached; retrieval/alignment/evidence work remains.
The hybrid helps omission-only cases but offers no consistent overall improvement.
No unsupported latency target or guarantee is introduced.

## Compatibility and maintenance

Local clean wheel installations and 18 small parity/correctness tests passed on each
of CPython 3.11.15, 3.12.13, 3.13.14 and 3.14.6 on Windows x86-64 and Ubuntu 22.04
WSL2 x86-64 (glibc 2.35). Native imports and Arabic cutoff calls also passed with
socket creation forbidden. Linux wheels were tagged manylinux 2.27/2.28; Windows
wheels used the matching CPython ABI and win_amd64. Other architectures/macOS were
not locally exercised. Hosted CI was configured, not run in this session.

RapidFuzz 3.14.6 declares Python >=3.11 and MIT licensing. Default installation has
no mandatory Python transitive dependencies; NumPy is only requested by its unused
`all` extra. Windows native use requires the documented Visual C++ redistributable;
source installation requires a C++17-capable compiler. Prebuilt wheels were used
here; source builds and machines without the redistributable were not tested.
See [pinned release/installation metadata](https://pypi.org/project/RapidFuzz/3.14.6/)
and [bounded Levenshtein API](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html).

| Adoption | Benefits | Costs / assessment |
| --- | --- | --- |
| Required runtime dependency (selected by maintainer) | One maintained production character kernel; strong scalar performance; avoids maintaining two runtime backends | Adds installation/platform requirements; warm anchor timings alone do not demonstrate a detector speedup |
| Optional acceleration (original benchmark recommendation) | Useful cold/fallback acceleration; default installs remain portable; identical semantics tested | Requires maintaining and testing two backends, clear import behavior and upgrade parity; not selected |
| Benchmark-only | Smallest production dependency/dispatch surface | Gives up measured cold-call improvements and leaves the custom bounded kernel as the sole production implementation |

The package is a maintained upstream implementation with a recent pinned release,
but future compatibility must be tested, not assumed. Phase 4B should add the required
runtime dependency `rapidfuzz>=3.14.6,<4`; benchmark reproduction stays pinned to 3.14.6. Upgrade
checks must retain scalar cutoff parity, Unicode tests and full matching agreement.
The independent oracle remains Python regardless of production backend.

## Concrete Phase 4B proposal (requires approval)

1. Reuse compact resource format 1 and normalization version 1. Keep the existing
   exact path when both budgets are zero. No runtime download or persistent rebuild.
2. Add complete guaranteed-anchor retrieval with approximate first-word fallback
   when `min_match_words <= max_errors`, and bounded ordered alignment for both
   budgets simultaneously. Recover every budget-valid occurrence independently.
3. Add `max_errors=0` and `max_missing_words=0` to instance `detect()`. Retain the
   agreed nonnegative integer validation, barriers, symbol endpoints, cost ranking
   and canonical trace policy. No new top-level functions, annotation or modes.
4. Add RapidFuzz as a required dependency with the version range above, using it as
   the sole production character-distance engine. Import it on first fuzzy use;
   exact-only calls do not initialize fuzzy helpers. Missing or broken required
   dependencies produce a clear error without downloads or a project Python fallback.
   Retain both Python implementations under repository tooling for correctness tests,
   benchmarks and upgrade parity checks, outside the installed library.
5. Initialize vocabulary length buckets and source segment endpoints once on first
   fuzzy use. Keep 50,000 distance LRU entries; limit neighbor caching to 4,096 keys
   and 100,000 total stored word IDs so large budgets cannot multiply full-vocabulary
   lists indefinitely. Eviction only causes recomputation, never dropped candidates.
6. Extend `Detection` with its best `errors`/`missing_words` pair and each
   `SourceOccurrence` with its own costs, aligned word trace and omitted tokens.
   Add frozen `WordAlignment` and `OmittedSourceToken` dataclasses using the
   experimental field names. New occurrence fields have defaults to preserve old
   constructor calls; dictionary serialization uses lists. Document new JSON keys.
   Source records, lookup and metadata snapshots remain unchanged.
7. Use two passes: first aggregate the best supporting cost for each legal input
   start/end pair, retaining shorter endpoints for overlap/tail selection without
   storing every source alignment. After selection, independently retrieve/verify
   each entire selected passage with the original budgets and recover all source
   intervals and canonical traces. Retain path information only for active verifier
   states and selected-occurrence recovery, not every supported substring. Compare
   this runtime to the oracle and all zero-budget expectations.
8. Measure typed results/full metadata, weighted-cache behavior and genuinely long
   fuzzy narrations before acceptance. Maintain supported-version tests, clean
   installs, repeated-call/instance isolation and offline checks.

The maintainer has selected the dependency design. Implementation of this Phase 4B
proposal, including the actual runtime requirement change, remains pending approval.
Final API stabilization, HTML annotation and data bundling remain later.

## Artifact fingerprints and limits

Detailed metrics and complete query/oracle evidence remain ignored in
`data/phase4-measured`. The accepted preparation was generated in `data/phase4-final`
and copied unchanged for the final worker run. Preliminary worker outputs are not
acceptance measurements. The metadata-only common-phrase source hints were corrected
to null; matching inputs and oracle results were unchanged and query rebuilds agree.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `queries.json` | 1,051,258 | `55edff14c522104e15eb2a2ea93052aa1ea0ce35ad07c40c9438c9e0ce2f4aca` |
| `micro.json` | 1,118,409 | `a1ed186cd993a7da38a4c087ef8f48a36bb3920ed17518a88af495cc1a78a65a` |
| `oracle-results.jsonl` | 111,932,412 | `3d64d68bd9e37fe10bac00f008cf398fa8ecf93505afb8b0680660a0f7971514` |
| `ready.json` | 339 | `828f01745ba56efe0f7e3147d6cef6e7cabe135b87c3439e623450eb02d16270` |
| `summary.json` | 764,606 | `7a7969f83e8a13805febd0191db34de2b63e7f83936db55934c1ec96fb9991d4` |
| Posting index (six identical files) | 43,734,859 | `1962c297dd7c6f1de4f090a6880ec68323122f64bec590829e30d19bede5201b` |

Lock SHA-256: `e4af3f71fd9374f338b9607cd5f69a717946c78b3b4001f96fa000b999a77579`. The summary records experiment source-file
fingerprints and machine details separately from deterministic evidence.

The mutations are provisional algorithmic tests, not semantic gold labels. Full-record
fuzzy examples use normalized narrations up to 35 tokens; large inputs contain short
quotations surrounded by deliberately distant repeated filler. They do not establish
performance on long corrupted narrations or diverse natural paragraphs. Three warm
samples and this single machine are limited performance evidence. Broad budgets and
common phrases may produce many matches; no caps or authentication claims hide that.
The shared renderer/normalizer is checked through independent slice/cost invariants
and existing normalization tests; oracle agreement alone cannot prove all inputs correct.

## Checks and Git boundary

- **106 tests passed** on Windows/Python 3.14.6, including all six isolated synthetic workers.
- **18 fuzzy parity/invariant tests passed on each supported Python version on both Windows and Linux**; the larger subprocess smoke test is run on Windows/Python 3.14 and configured in Linux CI.
- Ruff lint/format, strict package mypy and offline lock consistency passed.
- Wheel/sdist builds and metadata, isolated clean installs, no-Git sdist rebuilds and Twine checks passed.
- Installed-wheel tests prove that RapidFuzz is absent, runtime requirements and extras are unchanged, and no corpus or prototype artifacts are bundled.
- Hosted CI was not run. Linux verification used the existing local Ubuntu WSL environment.
- Library code, exact benchmark code, normalization and preprocessing implementations remain unchanged.

Proposed commits, only when requested:

1. `test: establish exhaustive fuzzy alignment oracle`
2. `perf: benchmark fuzzy retrieval and RapidFuzz distance`
3. `docs: record fuzzy benchmark and dependency recommendation`

Review Phase 4A and approve the remaining API/implementation proposal before Phase 4B. See
[benchmark usage](fuzzy-benchmark.md) and [the roadmap](roadmap.md).
