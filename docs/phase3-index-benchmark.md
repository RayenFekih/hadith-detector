# Phase 3A measured index benchmark

## Environment and method

- Python 3.14.6; Windows-11-10.0.26200-SP0.
- CPU: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel; logical CPUs: 20.
- Corpus fingerprint: `87fd7b7824fe60063026a582a845082f7fc6fe88587cb1d0805dbae372ea01ed`.
- Queries SHA-256: `afa547346cadd584108ae6e2d942d5abe77465e4082f70bad618bb930c5ba78c`.
- Seed 42; 20 queries in each of eight categories plus eight larger inputs.
- Three warm repetitions per query; complete results agree with the independent oracle.
- Each candidate runs in a fresh subprocess. Peak RSS includes corpus, index, serialization and result allocation.
- Corpus loading includes checksums and regeneration of mapped tokens for integrity; it is not a production startup estimate.
- Warm times include tokenization, verification, selection and complete result construction; result hashing is outside timing.
- Prototype formats are uncompressed canonical JSONL; n-gram sizes include unigram fallback.

## Build, loading and memory

| Candidate | Build s | Write s | Reload s | First call ms | Index MiB | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| oracle | 0.000 | 0.000 | 0.000 | 977.855 | 0.00 | 284.3 |
| positional | 0.860 | 1.217 | 2.978 | 13.978 | 12.07 | 295.7 |
| ngram2 | 2.698 | 4.106 | 7.099 | 2.294 | 32.97 | 362.9 |
| ngram3 | 3.193 | 6.072 | 8.669 | 2.187 | 41.71 | 413.5 |
| ngram5 | 3.186 | 8.669 | 10.368 | 1.818 | 53.94 | 478.3 |

## Warm query categories

| Candidate | Category | Median ms | p95 ms | Retrieved candidates | Verified source occurrences |
| --- | --- | ---: | ---: | ---: | ---: |
| oracle | bare | 972.093 | 1109.082 | 104,888 | 615 |
| oracle | common | 974.121 | 1092.013 | 48,358 | 48,358 |
| oracle | embedded | 978.829 | 1091.176 | 59,411 | 560 |
| oracle | full | 1134.180 | 1502.529 | 1,560,995 | 22 |
| oracle | large-1024 | 1045.594 | 1278.677 | 20,934 | 12 |
| oracle | large-4096 | 1468.482 | 1580.920 | 131,012 | 8 |
| oracle | multiple | 989.955 | 1135.043 | 127,365 | 280 |
| oracle | negative | 0.535 | 0.645 | 0 | 0 |
| oracle | short | 920.828 | 1279.085 | 152,019 | 152,019 |
| oracle | variants | 959.378 | 1140.454 | 110,857 | 1,769 |
| positional | bare | 12.724 | 193.145 | 333,143 | 615 |
| positional | common | 24.398 | 148.233 | 179,648 | 48,358 |
| positional | embedded | 11.693 | 144.787 | 216,446 | 560 |
| positional | full | 223.133 | 608.938 | 3,305,478 | 22 |
| positional | large-1024 | 50.720 | 267.121 | 84,477 | 12 |
| positional | large-4096 | 483.212 | 639.255 | 334,438 | 8 |
| positional | multiple | 17.555 | 184.033 | 321,209 | 280 |
| positional | negative | 0.664 | 0.913 | 0 | 0 |
| positional | short | 2.356 | 387.900 | 172,977 | 152,019 |
| positional | variants | 0.734 | 217.701 | 272,409 | 1,769 |
| ngram2 | bare | 2.755 | 149.910 | 125,461 | 615 |
| ngram2 | common | 7.672 | 128.696 | 51,622 | 48,358 |
| ngram2 | embedded | 4.044 | 103.462 | 66,818 | 560 |
| ngram2 | full | 158.722 | 503.601 | 1,653,887 | 22 |
| ngram2 | large-1024 | 36.023 | 215.219 | 25,265 | 12 |
| ngram2 | large-4096 | 395.836 | 492.102 | 137,271 | 8 |
| ngram2 | multiple | 6.842 | 147.684 | 137,748 | 280 |
| ngram2 | negative | 0.571 | 0.634 | 0 | 0 |
| ngram2 | short | 1.130 | 406.748 | 152,672 | 152,019 |
| ngram2 | variants | 0.512 | 143.479 | 120,603 | 1,769 |
| ngram3 | bare | 2.641 | 137.575 | 108,086 | 615 |
| ngram3 | common | 7.295 | 136.471 | 48,637 | 48,358 |
| ngram3 | embedded | 2.559 | 95.911 | 60,914 | 560 |
| ngram3 | full | 146.553 | 516.576 | 1,569,117 | 22 |
| ngram3 | large-1024 | 35.075 | 234.830 | 21,678 | 12 |
| ngram3 | large-4096 | 393.518 | 516.568 | 131,990 | 8 |
| ngram3 | multiple | 6.160 | 138.130 | 129,426 | 280 |
| ngram3 | negative | 0.566 | 0.639 | 0 | 0 |
| ngram3 | short | 1.764 | 413.599 | 157,622 | 152,019 |
| ngram3 | variants | 0.578 | 160.821 | 111,844 | 1,769 |
| ngram5 | bare | 2.493 | 137.305 | 104,888 | 615 |
| ngram5 | common | 6.854 | 136.349 | 48,358 | 48,358 |
| ngram5 | embedded | 2.219 | 91.691 | 59,411 | 560 |
| ngram5 | full | 146.875 | 501.482 | 1,560,995 | 22 |
| ngram5 | large-1024 | 32.369 | 208.629 | 20,934 | 12 |
| ngram5 | large-4096 | 404.690 | 491.198 | 131,012 | 8 |
| ngram5 | multiple | 5.117 | 143.807 | 127,365 | 280 |
| ngram5 | negative | 0.573 | 0.658 | 0 | 0 |
| ngram5 | short | 1.706 | 414.315 | 172,977 | 152,019 |
| ngram5 | variants | 0.607 | 139.554 | 110,857 | 1,769 |

All indexed candidates agree before and after reload, and their independent
rebuilds produce identical artifact checksums. Performance is machine/workload
specific; these are exact lexical correctness checks, not semantic accuracy
or fuzzy matching evaluation.

## Recommendation for review

**Recommend the three-word index with unigram fallback.** This is a proposal,
not an approved or implemented production index.

- Default paragraph median: 2.559 ms versus 4.044 ms for two-word and 11.693 ms for positional indexing.
- Five-word indexing improves this median to 2.219 ms, but increases prototype storage from 41.71 to 53.94 MiB and observed process peak from 413.5 to 478.3 MiB.
- Three-word indexing reduces default paragraph median by about 37% versus two-word indexing, at an additional 8.74 MiB of prototype storage and about 50.6 MiB of observed process peak.
- Paragraph p95 is 95.911 ms for three-word versus 91.691 ms for five-word and 103.462 ms for two-word indexing. Shared wording creates expensive tails; median alone is insufficient.
- Positional is the smallest prototype and remains a reasonable low-memory alternative. Two-word retrieval is preferable for some sub-three-word workloads; the chosen priority is balanced paragraphs at the five-word default.

The three-word design retains exact completeness for every positive minimum via
unigram fallback. This benchmark does not establish fuzzy candidate recall or
production memory/startup targets. Future tolerance work must separately validate
retrieval under errors and omissions.

### Short-query detail

Each minimum has five queries and three repetitions per query. Common one-word
inputs necessarily produce large complete result sets; no prototype caps them.

| Candidate | Min 1 median ms | Min 2 median ms | Min 3 median ms | Min 4 median ms |
| --- | ---: | ---: | ---: | ---: |
| oracle | 1145.165 | 914.064 | 929.676 | 915.760 |
| positional | 248.237 | 6.051 | 0.346 | 0.294 |
| ngram2 | 254.302 | 2.188 | 0.267 | 0.256 |
| ngram3 | 255.883 | 5.759 | 0.408 | 0.231 |
| ngram5 | 236.711 | 4.998 | 0.332 | 0.270 |

## Corpus loading, limitations and evidence

- Full corpus: 14,940 records, 1,039,600 tokens and 40,949 normalized word types; all Phase 2 artifact hashes match.
- Corpus validation/loading measured 33.47?34.74 seconds across workers because it regenerates every token. Production runtime loading must use prebuilt compact resources, not this validation path.
- The first call is one embedded query after initialization, not end-to-end cold startup or a cold disk-cache measurement.
- Source excerpts and complete-narration quantiles use records with at least 30 tokens. Short queries are tested separately; semantic Matn/Isnad intent is not labelled.
- Synthetic negatives are novel Arabic words exhaustively confirmed absent. They are not representative hard semantic negatives.
- Larger-input medians remain around 0.39?0.40 seconds for n-gram retrieval. Do not infer linear scaling or optimize this prematurely without a production profile.
- Peak RSS is a whole-process high-water mark and includes validation, result materialization, serialization/reload and rebuild checks. It is not index-only memory.
- Counts in the category table are totals over queries, not over repetitions. Corpus-loading time is excluded from query latency.
- This is one run on a Windows machine with about 32 GiB RAM, 14 physical cores and 20 logical CPUs. Small timing differences may reflect run-to-run noise.

- psutil: 7.2.2; Unicode: 16.0.0; uv.lock SHA-256: `9a7c93bb4fe3d6278cc7379b7297ed38c74ad17cb95bb7837887dd74d0b6d1bd`.
- Complete per-query samples, counters, result fingerprints, code fingerprints and experimental artifacts are retained in the ignored `data/phase3-benchmark` directory.
- The worker corpus snapshot is an unchanged ignored cache copy because sandbox access to the renamed prepared directory was restricted. Original prepared data was not altered.

## Proposed runtime artifact format (Phase 3B, awaiting approval)

Use a directory with a small JSON manifest and standard-library-readable resources:

- `records.jsonl`: unchanged original source records, copied from the verified preparation output.
- `vocabulary.json`: deterministic normalized-word IDs, ordered by first corpus occurrence.
- `tokens.bin` and `record-offsets.bin`: explicit little-endian uint32 token fields (word ID, original start/end, segment) and uint64 record boundaries.
- `unigram-offsets.bin` plus `unigram-postings.bin`: a vocabulary-indexed directory of uint64 offsets/uint32 counts and packed uint64 record/token positions.
- `trigram-keys.bin`, `trigram-offsets.bin`, and `trigram-postings.bin`: sorted three-word uint32 keys, block offsets/counts, and packed uint64 positions.
- `manifest.json`: independent index format version 1, normalization/record/token format versions, source artifact fingerprints, per-file SHA-256 checksums, counts, and build configuration.

All binary files have explicit magic/version headers, byte order and declared
element counts; no pickle, native-endian file layouts, SQLite, mmap dependency,
or third-party runtime dependency. Validate counts, bounds, compatible versions
and checksums when loading. Runtime must neither normalize the whole corpus nor
download or rebuild resources. Reject unsupported bounds instead of overflowing.

The builder streams original records and writes stable sorted keys/postings into
a new directory, validating before atomic acceptance. Rebuilding twice must give
identical files. These large resources remain ignored by Git and are not bundled
into wheels until the packaging milestone. The compact format must be measured
again; the JSONL prototype timings are not predictions of its startup or memory.

## Concrete Phase 3B proposal (not implemented)

1. Add the separate deterministic runtime-index builder for the approved three-word/unigram design, consuming verified Phase 2 artifacts.
2. Add a reusable offline loader with one corpus/index instance per detector. Validate resources once, keep search structures private, and reuse them across calls.
3. Expose provisional `HadithDetector.from_directory(index_dir)`, `detect(text, *, min_match_words=5)`, and `get_hadith(hadith_key)`. Reject non-positive/non-integer minima (including bool), reject non-string input, return an empty list for empty input, and raise clear exceptions for missing/corrupt/incompatible resources or unknown identities.
4. Introduce typed dataclasses: `HadithRecord` with original fields/additional metadata, `SourceOccurrence(start, end, text)`, `HadithReference(record, occurrences)`, and `Detection(start, end, text, matched_words, references)`. Results provide dictionary serialization; returned mutable metadata must be independent of internal records.
5. Preserve the tested selection semantics: rank supported substrings by words, character length and earlier start; retain valid disjoint fragments after overlap selection. Do not merge source evidence. Recover every reference and occurrence, including support from suppressed larger alignments.
6. Sort detections by input offset, references by collection/original sequence, and source occurrences by start/end. Preserve nullable URLs, duplicate narration identities, barriers and complete symbol expansions.
7. Compare production results to the independent oracle on all 168 queries, before/after index rebuild/reload. Test supported Python versions, repeated calls, instance isolation, offsets, complete references, unknown keys, malformed resources and no network/rebuild side effects.
8. Measure compact-resource size, initialization, memory and paragraph/large-query latency; update documentation with working provisional examples and remaining limitations.

Top-level convenience functions, annotation, fuzzy options, omission tolerance
and final API stabilization stay in their later phases. Phase 3B begins only
after review and approval of the index choice, format and provisional interface.

## Validation and Git boundary

Final local checks: **64 tests passed** on Python 3.14.6, including the isolated
synthetic worker pipeline. The 22 oracle/prototype tests also passed on Python
3.11.15, 3.12.13 and 3.13.14; their psutil-dependent smoke test was skipped in
those minimal environments. Ruff lint/format, strict package mypy, lockfile
consistency, wheel/sdist builds, clean installations, sdist-to-wheel rebuilds,
Twine metadata checks and Git whitespace checks passed. Hosted CI has not been
run in this implementation session.

Manual and randomized tests compare the oracle and prototypes to direct substring
enumeration. Automated checks include deterministic serialization, corruption
rejection, complete references, repeated occurrences, barriers, whole-symbol
matching, short minima, and an isolated synthetic end-to-end benchmark in CI.

Proposed commits (only when requested):

1. `test: establish exhaustive exact-match oracle`
2. `perf: benchmark positional and n-gram indexes`
3. `docs: record index benchmark and recommendation`

No production index selection, Phase 3B implementation, commits or pushes were
performed in this milestone. See [benchmark usage](index-benchmark.md).
