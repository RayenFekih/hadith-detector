# MARISA v2 production integration

Completed before Phase 5 on 2026-10-14. The maintainer approved the prebuilt v2
architecture and accepted the measured initialization cost for long-lived API,
MCP-server and notebook instances. No Phase 5 work, commits, pushes or releases
are included.

## Result and compatibility

The library requires `marisa-trie==1.4.1` alongside `rapidfuzz>=3.14.6,<4`.
The lockfile records both. Two concrete private lookup helpers replace the
normalized-word dictionary and trigram-to-posting-block dictionary with heap-loaded
MARISA `RecordTrie("<I")` files. IDs are stored explicitly: vocabulary IDs retain
first occurrence order, and trigram block IDs retain sorted-triple order. Native
internal IDs are not used. Fuzzy inverse vocabulary/buckets initialize in ID order.

Original records and metadata, identity lookup, posting arrays/directories,
normalization, source/input offsets, exact/fuzzy algorithms, budgets, canonical
alignments, result ranking and public API remain unchanged. There is one production
format and no backend selector, optional accelerator or runtime fallback.

Index format 2 uses `HDIDX002` headers for the existing binary tables and replaces
`vocabulary.json`/`trigram-keys.bin` with `vocabulary.marisa`/`trigrams.marisa`.
Record, token, normalization and manifest versions remain 1. The repository builder
constructs resources offline, records the pinned native version/settings, dependency
lock and code fingerprints, validates in a staging directory, and refuses overwrites.
Detector initialization opens prebuilt resources; it never constructs corpus-dependent
tries, downloads data or converts old resources.

All integrity checks remain enabled: checksums before native loading; complete unique
ID ranges; duplicate mappings; encoding and sorted block order; record identities;
token spans/segments; posting bounds/order, source-token agreement and occurrence
completeness. A temporary compact trigram-key array supports validation and is released
afterwards. No validation was weakened to reduce initialization time.

## Acceptance evidence

- Production matches **168 full-corpus fuzzy oracle cases, 168 exact cases and all
  39 representative cases**, including independently verified long quotations.
  Checks cover complete identities, all occurrences, costs/canonical traces and
  original slicing. Complete original metadata round trips pass for all 14,940
  records. All checks run without network access.
- Two independent production builds are byte-identical, including manifests, and
  each passes full offline integrity verification. Both preserve 14,940 records,
  1,039,600 tokens, 40,949 words, 382,866 trigram keys and 1,009,649 trigram occurrences.
- **148 project tests pass**, including wheel/sdist builds, rebuilding the wheel
  from an sdist without Git, metadata checks and offline clean-wheel detection.
  One isolated library-survey module is skipped in the normal environment; its
  **12 tests pass** separately after adapting experimental native-key iteration.
- **85 normalization, exact/fuzzy and native integrity tests pass in each of eight
  environments:** Windows and Ubuntu 22.04/WSL x86-64, Python 3.11.15, 3.12.13,
  3.13.14 and 3.14.6. Ordinary CI's existing supported-version matrix runs the native
  resource tests with the newly required dependency; no corpus downloads are added.
- Fresh clean environments on all eight combinations install the project and both
  dependencies with `--offline --no-index` from checksum-verified official wheels.
  Probes run outside the checkout with `-I -B`, forbid network sockets, compare
  complete source metadata, verify original slices and repeated exact/fuzzy calls,
  and confirm there are no data-dependent trie constructions or working-directory
  side effects. Every environment reads the same Windows-built v2 resources and
  rejects preserved v1 with an offline rebuild instruction.
- Ruff lint/format, strict mypy for all seven package modules, lock resolution,
  packaging metadata/content checks and whitespace checks pass. Generated corpus,
  native files and the data/benchmark dependencies remain absent from the wheel.

| Production resource | SHA-256 |
| --- | --- |
| Manifest, both builds | `a34ebdd099389594b039a4ac55e667081110c2c192f43eee08095fe1f7d5dcbd` |
| Vocabulary | `faf3d4b7d5d9952e5ea3823d305d29e46d4fcc1a6f52751cdada81a529c655cc` |
| Trigrams | `9bb9eae9fc858f7a5ed9a6675035f407b77f9c561e9cfd441cbcf0b14b49518e` |

The native files have exactly the trial's bytes. The production manifest differs
because it records production code paths/fingerprints and the updated project lock.
Build outputs are `data/runtime-index-v2-a` and `data/runtime-index-v2-b` locally;
names are arbitrary. The original v1 directories, source data and prepared corpus
remain intact. Raw validation and installation reports, wheelhouse and distribution
artifacts remain ignored.

## Initialization, memory and concurrency

The approved controlled [trial](marisa-trial.md) saved **78.04 MiB steady RSS**
(246.2 → 168.2 MiB). Typical paired warm latency increased approximately 1.4% for
exact and 0.2% for fuzzy; difficult short queries and long quotations remained
comparable. Validated loading increased from 2.597 to 3.935 seconds (**+1.338 s**),
and the first fuzzy call increased from 165.6 to 197.0 ms. These are single-machine
results; the integration makes no fixed performance guarantee.

Production full-oracle workers loaded in 4.04 and 4.43 seconds in the initial and final
acceptance passes. These untimed correctness runs are not a repeated controlled startup
benchmark. Their larger 375-case workload has different cache/output allocation
history, so its final RSS is not a controlled replacement for the paired trial.
Keep timing, memory and environment details in ignored measurement reports.

Reuse a loaded detector across sequential calls to amortize initialization. **There
is no concurrency guarantee for a shared instance.** Lazy initialization and mutable
fuzzy caches remain unchanged; no locks or threading contract were added. Applications
should serialize access to a shared instance or use independent instances/workers.

## Rebuild, verification and rollback

From the repository checkout with Python 3.14 and the locked dependencies:

```text
uv sync --locked --group data --group benchmark
uv run python -m tools.build_index --corpus-dir data/prepared-corpus --output-dir data/runtime-index-v2-new
uv run --group benchmark python -m tools.validate_marisa_runtime --index-dir data/runtime-index-v2-new --evidence-dir data/phase4-final --representative-suite data/library-evaluation-final/suite.json --output data/marisa-production-new.json
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src/hadith_detector
uv build --no-sources
uv run twine check dist/*
```

Choose new output paths. Saved oracle evidence is generated by the existing Phase 3/4
benchmark workflows. For independent clean-wheel verification, run
`tools/check_marisa_install.py` with the installed interpreter using `-I -B`, providing
`--index-dir`, `--legacy-dir` and `--report` from a directory outside the checkout.

V1 has no production loading path. Rebuild offline from the prepared corpus into a
separate v2 directory; retain v1 for rollback with the previous library. Native
dependency upgrades require explicit resource-read compatibility and correctness
testing before changing the exact pin. Corpus bundling and public API finalization
remain later milestones. Stop for review before Phase 5.
