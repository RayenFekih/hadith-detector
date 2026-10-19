# Changelog

Release notes are maintained manually. Versions use Git tags and 0.x development
conventions described in [CONTRIBUTING.md](CONTRIBUTING.md).

## [0.2.0] - Unreleased

### Added

- Optional local MCP integration through `pip install "hadith-detector[mcp]"`,
  using the official Python MCP SDK without adding dependencies to base installs.
- `hadith-detector-mcp` CLI and `python -m hadith_detector.mcp` entry points,
  using local stdio transport and the existing bundled corpus and shared detector.
- `detect_hadith`, `annotate_hadith`, and `get_hadith` tools with structured schemas,
  strict configuration validation, original character offsets, and matching evidence.
- Explicit match, reference, and occurrence pagination, including totals and next
  offsets, while preserving exact and approximate match details.
- Server instructions and candidate labels explaining contextual review, citation
  evidence, and the limits of textual matching and authenticity claims.
- MCP setup guide, client configuration example, validation report, protocol tests,
  and clean-install checks for both base and MCP-enabled distributions.
- PyPI badge in the README and homepage/changelog links in package metadata.

### Changed

- CI now exercises MCP tests and quality checks with the optional extra installed.
  Existing matching algorithms, default detection settings, and Python APIs are unchanged.

## [0.1.1] - 2026-10-17

### Changed

- Improved the README quick start with a complete Arabic example, source inspection,
  annotation, and clearer guidance on offsets, configuration, and incidental matches.

## [0.1.0] - 2026-10-17

Initial tagged release. The entries below cover the library's development up to this tag.

### Fixed

- Release-readiness probes execute the current README examples without depending
  on variable names from an earlier draft; documentation links also work on PyPI.
- Clean-wheel CI checks now install from hash-verified locked dependency wheels,
  without relying on uv registry metadata left in a developer's cache.

### Added

- One bundled Bukhari/Muslim corpus with prebuilt MARISA v2 resources, optional
  `index_dir` defaults, offline staging and fail-closed distribution builds (Phase 7).
- Manual, non-publishing release-readiness workflow for actual bundled candidates
  on Windows/Linux and Python 3.11–3.14, plus a professional README draft.
- Finalized the 55-input Phase 6 technical pilot with 382 completed human judgments,
  reproducible offline scoring, evidence validation and separate release-description wording.
- Expanded the technical pilot to 55 frozen inputs, including all 20 commentary
  paragraphs, with four-group reporting and explicitly approved, lossless review migration.
- Frozen 50-input technical pilot with source-linked comparisons, 62 deduplicated
  passage pairs and separate automatic review progress; full intent research remains optional.
- Interactive Phase 6 ipywidgets review notebook with exact-offset Arabic previews,
  lazy supporting evidence and atomic, resumable CSV progress saves.
- Repository-only Phase 6 input freezing, six-configuration evidence capture,
  reversible review CSV, candidate-unwanted-alert inventory and offline replay.
- Pinned natural-source provenance and input-first draft spans. Original intent labels
  remain provisional; the smaller technical pilot now has approved correspondence review.

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

- Replaced the unused application scaffold with a supported Python library.

[0.2.0]: https://github.com/RayenFekih/hadith-detector/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/RayenFekih/hadith-detector/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/RayenFekih/hadith-detector/releases/tag/v0.1.0
