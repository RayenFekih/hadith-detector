# Phase 3B runtime validation

## Full-corpus evidence

- 14,940 original records; 1,039,600 tokens; 40,949 vocabulary terms.
- 382,866 trigram keys; 1,009,649 trigram postings and 1,039,600 unigram postings.
- Every original field in all 14,940 records round-trips through `get_hadith().to_dict()`.
- All 168 saved Phase 3A oracle cases agree on input spans, matched words, identities
  and every source occurrence, on both builds and all three repetitions.
- Two independent builds are byte-identical, including their manifests.
- Construction verifies prepared inputs and validates all emitted runtime structures.
- The 375 duplicate-text extra records and 26 nullable URLs remain intact.
- Unchanged Phase 2 warnings: 63 replacement characters, 51 orphan marks and 8 unexpected
  characters across 68 records. No text repair, exclusions or normalization-policy changes.

Construction used the unchanged verified snapshot in `.cache/phase3-corpus`.
Original research and prepared-data directories remain preserved. Ignored outputs
are `data/runtime-index-a` and `data/runtime-index-b`; either can be passed to
`HadithDetector.from_directory()`. These names only distinguish repeat builds.

## Environment and fingerprints

- Python 3.14.6; Unicode 16.0.0; Windows-11-10.0.26200-SP0.
- CPU: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel; logical CPUs: 20.
- psutil 7.2.2 measures processes; runtime dependencies: none.
- uv.lock SHA-256: `9a7c93bb4fe3d6278cc7379b7297ed38c74ad17cb95bb7837887dd74d0b6d1bd`.
- Source corpus fingerprint: `87fd7b7824fe60063026a582a845082f7fc6fe88587cb1d0805dbae372ea01ed`.
- Prepared manifest SHA-256: `f0ee8509b911b7835771de94fe65a97a17098ebba53de57f9c274dd077a5a0e2`.
- Runtime build fingerprint: `efbaeae8851573acfb013876720e40d39774fbacae38ef0e93401c19d87f96f3`.
- Query SHA-256: `afa547346cadd584108ae6e2d942d5abe77465e4082f70bad618bb930c5ba78c`.
- Saved oracle SHA-256: `ce9adad9453edec15901e68244adc85edbe455356473c4893720621d9b47ef31`.
- Measurement summary SHA-256: `319d85b1e65460ac06eb2c8c24154255a5451db11ce76f1ee71a8d72ccf1e6e7`.

The runtime manifest records pinned QuranLab revision/configurations and fingerprints
of the builder, corpus verifier, prototype index builder, codec and normalization.
Deterministic resources contain no timestamp or absolute path.

## Size, startup and memory

**63,963,532 bytes (61.00 MiB)** for the complete resource directory, including original
narrations, metadata, mapped tokens and both posting indexes. Builds took 20.20 and
20.02 seconds, including verification, construction, writing and output validation.

| Fresh process | Load/validation s | First embedded call ms | Peak RSS MiB | Final RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| runtime-index-a | 2.678 | 1.377 | 388.4 | 249.8 |
| runtime-index-b | 2.615 | 1.355 | 388.2 | 250.3 |

Loading validates checksums, schemas and complete binary posting structures without
retokenizing narrations. Peak RSS covers the whole process, including temporary
validation allocations and full result metadata. Final RSS is after the query suite.
Each worker is fresh; OS filesystem caches were not flushed. Times are measurements,
not performance guarantees. Raw reports stay in `data/runtime-validation-final`.

## Warm detection timings

The unchanged seed-42 suite has 20 queries per ordinary category and four per large
category. Median and nearest-rank p95 aggregate all three samples per query.
Timing includes input normalization, retrieval, verification, passage selection and
typed results with copied metadata; oracle projection/hashing is outside timing.

| Process | Category | Median ms | p95 ms | Source occurrences (one pass) |
| --- | --- | ---: | ---: | ---: |
| runtime-index-a | bare | 2.290 | 76.940 | 615 |
| runtime-index-a | common | 10.857 | 151.298 | 48,358 |
| runtime-index-a | embedded | 1.290 | 55.386 | 560 |
| runtime-index-a | full | 81.097 | 281.673 | 22 |
| runtime-index-a | large-1024 | 12.965 | 115.095 | 12 |
| runtime-index-a | large-4096 | 193.817 | 225.001 | 8 |
| runtime-index-a | multiple | 3.882 | 74.057 | 280 |
| runtime-index-a | negative | 0.205 | 0.211 | 0 |
| runtime-index-a | short | 3.318 | 354.642 | 152,019 |
| runtime-index-a | variants | 0.234 | 82.122 | 1,769 |
| runtime-index-b | bare | 2.133 | 75.383 | 615 |
| runtime-index-b | common | 11.113 | 147.826 | 48,358 |
| runtime-index-b | embedded | 1.254 | 53.583 | 560 |
| runtime-index-b | full | 81.672 | 282.130 | 22 |
| runtime-index-b | large-1024 | 12.873 | 118.047 | 12 |
| runtime-index-b | large-4096 | 195.050 | 235.385 | 8 |
| runtime-index-b | multiple | 3.808 | 72.665 | 280 |
| runtime-index-b | negative | 0.207 | 0.249 | 0 |
| runtime-index-b | short | 3.336 | 358.362 | 152,019 |
| runtime-index-b | variants | 0.230 | 80.627 | 1,769 |

Compact loading is substantially faster than Phase 3A corpus regeneration plus JSON
reload. Size totals are not directly comparable: the prototype report lists index-only
bytes; this report includes records and mapped tokens. Runtime models include copied
complete metadata, while prototypes returned identities and spans. Common short queries
can return thousands of references, and no cap hides that cost. Full narrations and
large inputs cost more than typical paragraphs. Perturbations test exact matching only.

## Artifact inventory

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `manifest.json` | 2,313 | `925d19aff64d8ad0b8b9d732d060bbfabb3191f99b1b68e3fce5e09738dbf091` |
| `record-offsets.bin` | 119,560 | `b1083f3375f2b9dd72ed825822d34d78229d010afe1a6c1954933dc49dcaad34` |
| `records.jsonl` | 20,570,642 | `9ec8e19aaab80ffbc01aa162122060099bc0a5de3841b544b4afa1c381414246` |
| `tokens.bin` | 16,633,632 | `eabaed153d0e5e49c56921fab4acc339e11aeaca14d9beacf9c7a5f71f093faf` |
| `trigram-keys.bin` | 4,594,424 | `9ccfbfc8dcd439eaf095991f4bcdde365d70348ac100835c4f212d64f1538adb` |
| `trigram-offsets.bin` | 4,594,424 | `26931a226a937bb33decf038b46af66b4d96d898921c051788ebfdb99ed66b8e` |
| `trigram-postings.bin` | 8,077,224 | `4e30a1853fb5bd30896fbc831f9fb5d99038f6c79bb4aa4d87ef99473a3e9bd0` |
| `unigram-offsets.bin` | 491,420 | `a483e85522d8aafdc85e60e2422d1a1f90b29cfeaf73540dd177d7fd32f0e453` |
| `unigram-postings.bin` | 8,316,832 | `9ac864f33261b3ec4012a410dc39ba2cb3a22a77e410fdaf4aac61b9168050a1` |
| `vocabulary.json` | 563,061 | `73b9a9815dfc1f09f168003c8331a971c3a15a7d24ef2ebb841935171da96e1f` |

## Automated checks and limitations

- 87 tests passed on Windows/Python 3.14.6, including synthetic preprocessing, benchmark,
  runtime/oracle, randomized fixtures, malformed resources and packaging checks.
- 65 normalization, oracle and detector tests passed from installed wheels on each of
  Python 3.11.15, 3.12.13 and 3.13.14; the psutil smoke test was deselected there.
- Ruff lint/format, strict mypy, lock consistency and Git whitespace checks passed.
- Wheel/sdist builds, clean installations, no-Git sdist rebuilds and Twine checks passed.
- Installed wheels exclude corpus/binary resources, repository tools and optional
  downloader/benchmark dependencies. Synthetic tests use the existing CI matrix.
- Hosted CI was not run in this session. Full corpus downloads never run in ordinary CI.
- Runtime tests prohibit network/resource writes, verify resource reuse across calls
  and protect internal metadata from mutation of returned snapshots.

Oracle agreement verifies algorithmic behavior on these cases, not semantic accuracy
or authentication. Checksums detect accidental changes, not publisher authenticity.
The API and format are provisional. Fuzzy matching, omission tolerance, annotation,
convenience functions and bundled resources remain later milestones.

## Review and proposed commits

1. `feat: add compact offline index resources`
2. `feat: implement provisional exact detector`
3. `docs: record runtime validation and API usage`

Commit or push only when requested. Review Phase 3B before planning Phase 4.
See [the runtime guide](runtime-index.md) for commands and model contracts.
