# Phase 5A review report

Phase 5A implements the [approved public API](public-api.md). Phase 5B annotation
and Phase 7 corpus bundling remain outside this work. No commit, push or release
has been performed.

## Changes and compatibility

- Frozen validated `DetectorConfig` and directory-based construction, retaining
  `from_directory()`; read-only configuration and resolved `index_dir` properties.
- Omitted/`None` detection settings inherit defaults; explicit zero overrides.
- Top-level detection and lookup require a directory and reuse one synchronized
  cache entry. Configuration remains per-call; `clear_cache()` forgets the entry.
- Reentrant instance locking serializes detection and lookup, including lazy fuzzy
  cache updates. Independent instances retain independent caches.
- All six result models gain structural `from_dict()` validation while retaining
  existing fields, dictionary shapes, tuple collections and isolated metadata.
- Updated guides, roadmap, changelog and three runnable repository examples.

The provisional direct constructor now accepts a directory rather than internal
`Resources`. Existing factory calls remain valid. Explicit `None` for settings
now inherits instead of raising. Deserialization adds no matching or authentication.
The exact engine, retrieval and result-selection method bodies are AST-identical
to the preceding implementation. Resource validation, fuzzy algorithms, MARISA,
normalization, source artifacts, dependency requirements and lockfile are unchanged.

## Verification

The complete local suite passed **186 tests**. The optional library-survey module
was skipped there and passed **12 tests** in its existing isolated environment.
Checks include synthetic preprocessing, independent exact/fuzzy correctness,
configuration, caches, concurrency, exception recovery, serialization, resource
corruption and packaging.

Offline full-corpus validation passed **168 exact**, **168 fuzzy** and **39
representative** cases against saved independent oracle evidence. Results retained
all input spans, references, source occurrences, costs and canonical traces.
Every result also passed structural restoration. All **14,940** original records
round-tripped through `HadithRecord.from_dict()` without losing metadata.

Supported-version checks use the final wheel, shared prebuilt v2 resources and
network-blocked installed-wheel probes outside the repository. Each matrix run
executes **123** API, normalization, exact/fuzzy and resource-integrity tests.

| Python | Windows 11 | Linux/WSL Ubuntu 22.04 |
| --- | --- | --- |
| 3.11.15 | Passed | Passed |
| 3.12.13 | Passed | Passed |
| 3.13.14 | Passed | Passed |
| 3.14.6 | Passed | Passed |

Wheel/sdist metadata and contents checks passed, including a wheel rebuilt from
the sdist without Git and clean offline installation of both wheels. Native tries
were only read, never constructed during initialization; v1 resources were
rejected with offline rebuild guidance. Runtime metadata still requires only
RapidFuzz and MARISA, with no extra or serialization dependency. Generated corpus
and indexes remain excluded from distributions. Ruff, formatting, strict mypy
and Twine checks passed. All three documented examples ran against the corpus.

Generated evidence remains ignored under `data/phase5a-final-oracles.json`,
`data/phase5-final-installed-*.json` and `.cache/phase5-final-*.log`.
The preserved v2 manifest SHA-256 is
`a34ebdd099389594b039a4ac55e667081110c2c192f43eee08095fe1f7d5dcbd`.

## Limits and review boundary

Same-instance calls are sequential, not parallel. Mutable result metadata is an
isolated snapshot, not deeply immutable. Resource directories must remain unchanged;
cache clearing is explicit. No new latency or memory benchmark is claimed here;
the approximately 78 MiB saving and 1.34-second initialization cost remain historical
MARISA measurements. Oracle agreement establishes algorithmic behavior, not independent
Hadith authentication or real-world precision. No annotation API is exported.

Phase 5A was accepted by the maintainer after review. Its implementation and
validation milestone is complete. Phase 5B has not begun; annotation requires
separate plan approval and an instruction to implement. No commit, push or
release is authorized by milestone acceptance alone.
