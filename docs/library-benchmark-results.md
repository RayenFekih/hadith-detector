# Focused library benchmark results

Measured locally on 2026-10-14, before Phase 5. Production Python files, `pyproject.toml`,
`uv.lock`, normalization and runtime resource formats are unchanged. Python 3.11–3.14
support is retained. No adoption, commit, push or release is included.

## Ranked recommendation

1. **MARISA is worth a storage/loading integration proposal for its memory benefit.**
   Steady RSS falls by about 80–82 MiB (30–31%); detection/serialization-harness peak
   falls by about 66 MiB (15–16%). Detection is broadly comparable, slightly slower in
   paired medians. This is a substantial memory benefit, not a detector speedup.
   Prebuild native keys offline; do not adopt the experimental runtime-construction bridge.
   A production proposal must settle format/version compatibility, integrity validation,
   IDs, native loading and legacy resources before changing requirements or artifacts.
2. **Roaring is a conditional candidate for expensive short fuzzy searches.** It improves
   the hardest selected short case by 25%, with only 0.65 MiB of installed files. However,
   typical paired warm gains are about 1%, and overall RSS does not improve. A Python
   sorted-order control explains part of the benefit; Roaring retains a further 16% gain
   on that case versus the ordered control. Consider a narrow temporary candidate-container
   change if this workload matters; do not replace persistent postings based on these results.
3. **RapidFuzz collection lookup is a useful targeted optimization, not a demonstrated
   whole-detector replacement win.** Uncached vocabulary scans improve about 5–14x, but
   cache-cold/warm detector paired medians are essentially unchanged. It adds no new package,
   yet the trial keeps extra bucket mappings and bypasses distance-cache population during
   collection calls. Keep the current implementation unless cold vocabulary scans are a
   demonstrated application bottleneck. Prefer streaming `extract_iter` over collecting and
   sorting scored matches if selected; neither uses result caps.
4. **Prefer msgspec to orjson if a codec is later needed, but keep stdlib JSON now.** Both
   raw kernels improve, but policy-complete adapters give only 2–3% median API-to-JSON
   improvements and no substantial detector initialization gain. msgspec's guarded decoding
   is faster than orjson's conservative numeric adapter. Neither trial replaces public
   dataclasses or schema validation. Do not rewrite canonical artifacts on this evidence.
5. **Defer NumPy for candidate operations.** It improves isolated operations and the
   hardest searches, but median fuzzy gains are only 4%, steady RSS increases about 32 MiB,
   and installed files add 41 MiB. The combined NumPy/Roaring trial does not justify both
   dependencies. NumPy 2.3.5 worked across the retained matrix; there is no reason to drop
   Python 3.11 for the latest NumPy.

A useful separate finding is **sorted candidate verification using existing Python**:
about 3% paired median fuzzy improvement, 7.5% lower total warm workload time, and 10%
improvement on the hardest selected short query, with no new dependency or format.
This control prevents attributing all container speedups to native libraries. It is
also a candidate for a small reviewed optimization; production traversal is unchanged.

No broad component replacement is justified by small median latency differences here.
Choose the memory improvement or a specific expensive-query improvement according to
actual usage; retain complete results and independent correctness tests in either case.

## Method and correctness

See [protocol and reproduction](library-benchmark.md). The full pinned corpus has
14,940 records, 1,039,600 tokens, 40,949 vocabulary terms and 382,866 trigram keys.
Thirty-nine representative queries cover 20 saved Phase 4 cases, three real long
corrupted quotations and 16 saved Phase 3 exact cases. Every candidate agrees on every
timed repetition, including costs, all identities/source occurrences, canonical word
traces and original offsets. Three long expectations were independently recovered by
the exhaustive oracle over the full corpus. No reference/posting caps are used.

Ten library variants, a sorted-Python control and a repeated baseline ran in fresh,
sequential subprocesses. Each query has one application-cache-cold call and three warm
repetitions. OS disk caches are not flushed. A repeated baseline at the end gives a
paired median timing ratio of 0.994 versus the initial baseline (about 0.6% drift).
This is exploratory single-machine evidence, not a statistical confidence interval;
differences of a few percent are not robust grounds for architectural changes.

Hardware/software: Windows 11 build 26200, Intel64 Family 6 Model 183 Stepping 1,
CPython 3.14.6. RapidFuzz uses its native distance engine. Library versions are independently
pinned in the repository-only requirements file; supported project dependency groups
were not changed. Native imports and synthetic adapter/oracle tests passed on Windows
and Ubuntu 22.04/WSL2 x86-64 using Python 3.11.15, 3.12.13, 3.13.14 and 3.14.6.
Each of those eight environments passed 12 checks, including every adapter and JSON
numeric-policy tests; native imports were explicitly checked with network sockets blocked.
All measured workers also forbid network sockets. Hosted CI was not run for these libraries.

## End-to-end results

Speedup is baseline divided by candidate latency; values below 1 mean slower. Paired
medians compare each query's three-sample warm median, then take the median of those
ratios. Fuzzy and exact results are reported separately. API-to-JSON includes unchanged
dictionary/snapshot conversion plus the selected encoder. Decoder/hashing checks occur
outside detection/serialization timing.

| Candidate | Warm fuzzy speedup | Warm exact speedup | API-to-JSON speedup | Steady RSS (MiB) | Suite peak (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 1.000 | 1.000 | 1.000 | 267.2 | 426.9 |
| RapidFuzz iterator | 0.999 | 0.985 | 0.989 | 274.2 | 429.3 |
| RapidFuzz extract, no limit | 1.005 | 0.989 | 0.998 | 272.6 | 429.5 |
| NumPy | 1.039 | 0.976 | 0.986 | 298.8 | 453.7 |
| Roaring | 1.011 | 0.969 | 0.987 | 277.8 | 432.3 |
| NumPy + Roaring | 1.032 | 0.986 | 0.995 | 295.0 | 454.7 |
| msgspec | 1.004 | 1.004 | 1.022 | 279.7 | 411.7 |
| orjson | 1.011 | 1.006 | 1.033 | 278.0 | 425.3 |
| MARISA heap keys | 0.983 | 0.974 | 0.983 | 187.1 | 361.1 |
| MARISA mapped keys | 0.992 | 0.995 | 0.996 | 185.2 | 360.2 |

Steady RSS is after the detection suite and garbage collection. Suite peak includes
initialization, experimental key construction, serializers and correctness-harness
allocations. It is not pure matcher peak, and it excludes subsequent microbenchmark
peaks, which are separately saved in raw reports. All candidates use the same harness.
RSS allocator retention varies; import delta and installed size are separate measures.

Baseline aggregate fuzzy warm latency is median 71.91 ms and p95 3,445.47 ms across the
69 warm samples. NumPy is 69.22/3,044.44 ms; Roaring 71.14/3,226.17 ms; MARISA mapped
76.37/3,358.10 ms. These aggregate percentiles are affected by the workload mix; paired
comparisons and the named expensive cases below better explain the trade-offs.

| Representative query | Baseline warm (ms) | Python sorted control | NumPy | Roaring | MARISA mapped |
| --- | ---: | ---: | ---: | ---: | ---: |
| Short fuzzy `short-00` | 41.15 | 39.53 | 38.52 | 39.85 | 41.75 |
| Hard short fuzzy `short-19` | 11,436.68 | 10,244.49 | 8,970.86 | 8,626.52 | 11,529.90 |
| Common chain `common-19` | 155.32 | 150.32 | 141.54 | 148.17 | 162.07 |
| Corrupted 499-word quote | 3,379.93 | 3,248.70 | 3,043.58 | 3,182.99 | 3,353.21 |

Summing one warm median per query gives 21.764 seconds for baseline, 20.137 for the
Python ordering control, 18.288 for NumPy, 18.347 for Roaring and 18.086 for the combined
container. These totals weight the hard short case heavily and are not a general traffic
distribution. Native containers still improve that case after accounting for ordering;
their effect is smaller on typical queries. No claim of reduced reference output explains
any gain: every golden result and trace remains identical.

## Cold calls, startup and dependency overhead

| Candidate | Resource load (s) | First fuzzy call (ms) | Import/setup (ms) | Import RSS delta (MiB) | Additional installed package files (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline | 2.609 | 160.4 | approximately 0 | approximately 0 | 0 |
| RapidFuzz iterator | 2.618 | 144.8 | 18.7 | 1.71 | 0 (existing dependency) |
| RapidFuzz extract | 2.577 | 143.3 | 18.5 | 1.69 | 0 (existing dependency) |
| NumPy | 2.612 | 165.1 | 59.0 | 9.70 | 41.08 |
| Roaring | 2.645 | 166.6 | approximately 1.4 | 0.58 | 0.65 |
| msgspec | 2.602 | 163.2 | 9.7 | 0.91 | 0.43 |
| orjson | 2.822 | 160.2 | 2.6 | 0.23 | 0.31 |
| MARISA heap | 2.587 | 215.3 | 1.3 | 0.51 | 0.41 |
| MARISA mapped | 2.574 | 201.5 | 1.1 | 0.50 | 0.41 |

RapidFuzz is pre-imported in collection variants but imported inside the baseline's first
fuzzy call. Add the import stage before comparing startup; the 144 ms figure is not a
standalone startup win. Cache-cold paired fuzzy speedups are 1.001/0.993 for the collection
variants, 1.032 for NumPy, 0.997 for Roaring, 1.008 for msgspec and 1.001 for orjson.

msgspec and orjson load resources in 2.602 and 2.822 seconds respectively. Their recorded
package footprints are 0.43 and 0.31 MiB, with import deltas 0.91 and 0.23 MiB. Full
startup remains dominated by resource construction/validation, not JSON parsing alone.

MARISA additionally builds and checks deterministic prototype keys in 1.113 seconds in
this compatibility bridge. Native key reload is 26.16 ms (heap) or 27.35 ms (mapped),
including replacement of the prior native key objects. Those component times are not
complete detector initialization; the existing corpus/token/posting loader still runs.
A future prebuilt native loader could avoid constructing legacy dictionaries, but its
startup and integrity-check performance have not been measured and are not promised.

## Isolated operations and serialization sizes

Uncached vocabulary scans improve 5.3–13.9x with RapidFuzz iterator across the ten
microbenchmarked terms. These operations are not used for every default-minimum query,
and neighbor caching avoids most repeated scans, explaining the small detector gains.

Median paired candidate-operation speedups, including deterministic materialization,
are NumPy 1.297x, Roaring 0.654x, and NumPy/Roaring 1.054x. Thus Roaring's end-to-end
heavy-query benefit must not be described as uniformly faster candidate insertion.
Ordering, representation and cache/locality effects matter; the control isolates ordering
partly, but does not prove which remaining low-level effect dominates.

| Ten candidate-position samples, combined | Serialized bytes |
| --- | ---: |
| Baseline JSON packed positions | 16,095,222 |
| NumPy little-endian uint64 | 8,684,184 |
| Roaring / combined | 733,068 |

These are temporary candidate-set serialization measurements with verified round trips
and repeated bytes. They are not persistent-index size comparisons: the current posting
arrays are unchanged, and rare posting-block compression might behave differently.

Full source records occupy 20,570,642 bytes with all three canonical encoders on this
pinned corpus; vocabulary/manifest bytes also agree exactly. Raw JSON-kernel timings
below are from separate fresh processes on checksum-verified valid corpus input:

| Codec | Raw decode median (ms) | Raw encode median (ms) | Guarded decode median (ms) | Guarded encode median (ms) |
| --- | ---: | ---: | ---: | ---: |
| Standard JSON | 96.001 | 122.532 | 138.190 | 118.922 |
| msgspec | 46.831 | 51.586 | 116.546 | 78.794 |
| orjson | 50.806 | 52.554 | 288.172 | 77.693 |

Raw kernels intentionally omit numeric-policy guards and are not proposed replacements.
The guarded orjson adapter conservatively scans for long digit runs and falls back to
stdlib for arbitrary integers; both native encoders reject nonfinite values through an
explicit validation walk. Those costs are included in the usable adapter measurements.
Dictionary/dataclass conversion also remains in the API-to-JSON pipeline. The native
kernel speedups therefore do not translate directly into detector or public-API speedups.
Current-corpus byte parity does not prove identical float formatting on all possible JSON;
canonical artifact encoding stays unchanged.

The two MARISA key files total 4,367,248 bytes (4.165 MiB), versus 5,157,485 bytes
(4.919 MiB) for the vocabulary JSON and trigram-key binary they could replace. Trigram
offsets and all posting/token/record files remain necessary. The potential saving is only
790,237 bytes across the whole resource set; the significant benefit is RAM, not disk.
The experimental directory retains the original resources plus native trial files; no
complete replacement artifact format was built. Heap and mapped trials produce identical
native files, and each worker verified repeated native builds before timing detection.

## Evidence and verification

Raw reports, logs, compatibility results and prototype files stay ignored in
`data/library-evaluation-final`; the repeated baseline is in `data/library-evaluation-repeat`.
An earlier exploratory directory is not acceptance evidence. No research data was staged.

| Evidence | SHA-256 |
| --- | --- |
| Query suite | `c5210c086dde3593ba4f60eadc76a4bda2ac71cf0296438b1330de05b7e21678` |
| Baseline report | `3bdf4f6c0fccdaf7bdc548249142e621fc25cce22763cd321a65fd70fe5e8fbe` |
| MARISA mapped report | `6cf4d34bbe16e1f2457eaf95d850c435e7daad396e22bbcf96810e88552b4aec` |
| Repeated baseline | `b681045014e2b0ad41e05edf8d36c33b33ac10c97ee903d8ffa60e920eda55f6` |
| Native vocabulary | `faf3d4b7d5d9952e5ea3823d305d29e46d4fcc1a6f52751cdada81a529c655cc` |
| Native trigrams | `9bb9eae9fc858f7a5ed9a6675035f407b77f9c561e9cfd441cbcf0b14b49518e` |

All main reports carry equal production-file fingerprints and suite checksums. Pins,
wheel metadata, installed-file sizes, OS/CPU/Python and tool fingerprints are recorded
in raw evidence. Matching agreement establishes algorithmic correctness on these cases,
not independent Hadith authentication or an exhaustive real-world evaluation.

Final verification: the existing development/data/benchmark suite passes 125 tests,
with the isolated-library module intentionally skipped there; its 12 tests pass in every
isolated matrix environment. Ruff lint/format and strict package mypy pass. Existing
packaging tests verify clean installations and metadata, and production file/lock
fingerprints still match the benchmark baseline. No installed production requirements
or resource files were modified.

Review these trade-offs before choosing any production change. Keep source records and
normalization fixed, retain Python 3.11–3.14, and require a separately approved integration
plan for native storage. Phase 5 remains unstarted.
