# Changelog

Release notes are maintained manually. Versions use Git tags and 0.x development
conventions described in [CONTRIBUTING.md](CONTRIBUTING.md).

## Unreleased

### Added

- Independent exhaustive fuzzy alignment oracle and tiny direct path enumeration.
- Complete first-word, guaranteed-anchor and trigram-hybrid retrieval experiments,
  with deterministic word traces, internal source omissions and combined budgets.
- Repository-only RapidFuzz 3.14.6 comparison, isolated timing/memory tooling and
  supported-version backend compatibility checks. Installed dependencies are unchanged.

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

- Dependency policy now requires offline operation while allowing evidence-based
  adoption of maintained dependencies; zero dependencies is a current implementation choice.

- Replaced the unused application scaffold with a library using no runtime dependencies.

Fuzzy matching, annotation and bundled resources remain planned. Runtime distributions
contain neither the corpus nor preprocessing dependencies.
