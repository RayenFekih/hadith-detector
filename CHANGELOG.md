# Changelog

Release notes are maintained manually. Versions use Git tags and 0.x development
conventions described in [CONTRIBUTING.md](CONTRIBUTING.md).

## Unreleased

### Added

- Installable `hadith_detector` foundation with metadata-derived version and typing marker.
- Python 3.11–3.14 policy, uv lockfile, Ruff, strict mypy, pytest, and build validation.
- CI covering Linux and Windows, including clean wheel and sdist installation checks.
- Project status, phased roadmap, contribution workflow, and data artifact policy.
- Pinned QuranLab source lock and repository-only fetch/build/verify workflow.
- Shared versioned Arabic tokenization with original spans and matching barriers.
- Canonical JSONL artifacts, build manifests, warning reports, and reproducibility checks.
- Synthetic preprocessing CI and full-corpus acceptance evidence.

### Changed

- Replaced the unused application scaffold with a library using no runtime dependencies.

Detection, annotation, and corpus indexes remain planned. Runtime distributions
contain neither the corpus nor preprocessing dependencies.
