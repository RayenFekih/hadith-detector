# Changelog

Release notes are maintained manually. Versions use Git tags and 0.x development
conventions described in [CONTRIBUTING.md](CONTRIBUTING.md).

## Unreleased

### Fixed

- Clean-wheel CI checks now install from hash-verified locked dependency wheels,
  without relying on uv registry metadata left in a developer's cache.

### Added

- Instance and convenience `annotate()` methods returning safely escaped HTML
  fragments with fixed marks, original offsets and best supporting costs (Phase 5B).
- Text/offset round trips, injection, exact/fuzzy parity and annotation concurrency checks.
- Carriage-return preservation and explicit annotation-only rejection of NUL/lone surrogates.

- Frozen `DetectorConfig`, directory constructor, read-only resolved `index_dir`,
  and convenience `detect()`/`get_hadith()` with a synchronized single-entry cache.
- Validated result `from_dict()` methods and isolated JSON metadata round trips.
- Per-instance reentrant locking: concurrent detection and lookup calls execute sequentially.
- Public API, cache/concurrency and deserialization regression checks (Phase 5A).

- Prebuilt MARISA v2 vocabulary/trigram lookups with explicit preserved IDs,
  complete resource validation and deterministic offline construction.
- Native-resource corruption tests, supported-version and offline installation checks.

- Production fuzzy detection with simultaneous character-edit and internal source-word
  omission budgets, complete anchor retrieval and two-pass occurrence recovery.
- Per-occurrence costs, canonical word alignments and omitted-token models; JSON result
  dictionaries now include these fields, including zero-cost traces on exact results.

- Independent exhaustive fuzzy alignment oracle and tiny direct path enumeration.
- Complete first-word, guaranteed-anchor and trigram-hybrid retrieval experiments,
  with deterministic word traces, internal source omissions and combined budgets.
- Repository-only RapidFuzz 3.14.6 comparison, isolated timing/memory tooling and
  supported-version backend compatibility checks (Phase 4A).

- Installable `hadith_detector` foundation with metadata-derived version and typing marker.
- Python 3.11–3.14 policy, uv lockfile, Ruff, strict mypy, pytest, and build validation.
- CI covering Linux and Windows, including clean wheel and sdist installation checks.
- Project status, phased roadmap, contribution workflow, and data artifact policy.
- Pinned QuranLab source lock and repository-only fetch/build/verify workflow.
- Shared versioned Arabic tokenization with original spans and matching barriers.
- Canonical JSONL artifacts, build manifests, warning reports, and reproducibility checks.
- Synthetic preprocessing CI and full-corpus acceptance evidence.
- Repository-only exhaustive exact-match oracle and positional/2-/3-/5-word prototypes.
- Direct substring-enumeration checks, deterministic query generation and isolated memory/latency benchmarks.

- Compact versioned trigram resources with complete unigram fallback, checksums,
  structural validation, and deterministic offline construction.
- Provisional `HadithDetector.from_directory()`, exact detection and source lookup;
  typed serializable results with all supporting references and occurrences.
- Runtime/oracle comparison, corruption tests, metadata isolation and clean-install checks.

### Changed

- Detection settings now inherit defaults when omitted or `None`; explicit zero overrides.
- The provisional constructor now takes a directory; `from_directory()` remains supported.

- Require `marisa-trie==1.4.1` alongside RapidFuzz. Index format v2 replaces v1;
  rebuild into a new directory from the prepared corpus and preserve v1 for rollback.
- Accept increased one-time validated initialization for substantially lower memory
  in long-lived instances. Phase 5A now serializes shared-instance calls.

- RapidFuzz is the sole required production distance engine (`>=3.14.6,<4`);
  Python distance implementations remain repository-only testing/benchmark tools.

- Dependency policy now requires offline operation while allowing evidence-based
  adoption of maintained dependencies.

- Replaced the unused application scaffold with a library using no runtime dependencies.

Annotation and bundled resources remain planned. Runtime distributions
contain neither the corpus nor preprocessing dependencies.
