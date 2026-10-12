# Contributing

## Environment and checks

Use Python 3.14 locally and uv (CI pins uv 0.11.26). The supported test matrix is
Python 3.11–3.14 on Linux and 3.14 on Windows. Install the checkout before importing;
do not set `PYTHONPATH` or add the source directory to test paths.

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src/hadith_detector
uv run pytest
uv build --no-sources
uv run twine check dist/*
```

In PowerShell, if wildcard expansion for twine is unavailable, use
`Get-ChildItem dist -File | ForEach-Object { uv run twine check $_.FullName }`.
Packaging tests invoke uv, resolve isolated build dependencies, build a wheel from
an sdist without Git metadata, and install both wheels in fresh environments.
These development operations may access the network; runtime imports do not.
Use `uv run pytest -m "not packaging"` for the fast foundation checks.

Phase 2 preprocessing uses `uv sync --locked --group data`. Run its tests with
`uv run --frozen --group data pytest`; the default environment skips the synthetic
pipeline tests when preprocessing dependencies are absent. Shared normalization
tests run on every supported Python. Full builds require Python 3.14. Ordinary CI
uses synthetic Parquet data and does not fetch the real corpus. See the
[data-preparation guide](docs/data-preparation.md) for full-corpus validation.

Ruff handles linting and formatting (100-character lines, Python 3.11 syntax).
Mypy checks package code in strict mode. Regenerate `uv.lock` with `uv lock` only
when dependencies change, then rerun checks. No pre-commit hook is required.

## Review and Git workflow

Work in independently reviewable phases. Update documentation and the Unreleased
changelog with behavior changes. Run relevant checks before each commit, inspect
the explicit staged diff, and run the complete suite before phase acceptance.
Do not stage ignored research, raw downloads, large artifacts, or unrelated changes.

Phase 1 commit boundaries:

1. `chore: establish installable library foundation`
2. `test: validate package builds and add CI`
3. `docs: document project status and phased roadmap`

Phase 2 proposed commit boundaries:

1. `data: pin QuranLab sources and document provenance`
2. `feat: add mapped Arabic normalization and tokenization`
3. `feat: add reproducible corpus preparation`
4. `docs: record full-corpus preparation validation`

Commit and push when requested. Preserve existing history and origin; never
force-push. Remote changes, destructive Git operations, release tags, public
releases, and PyPI publication require explicit approval. Stop after each phase
for review before implementing the next.

## Versions and releases

Setuptools-scm derives versions from Git; fetch full history and tags in CI.
Untagged builds are development versions, not a stable `0.1.0`. Import
`hadith_detector.__version__` to read installed distribution metadata; runtime
does not need Git or setuptools-scm. Build from a checkout or an official sdist;
arbitrary source copies without Git or sdist metadata are unsupported.

Reserve `v0.1.0` for the first approved usable release. Milestones need no tags.
During 0.x development, minor versions introduce features or breaking changes;
patch versions contain compatible fixes. Document incompatibilities and manually
move Unreleased notes into a dated release section when releasing.

Record schemas, normalization, and index formats have independent versions.
Dataset builds identify pinned upstream revision, preprocessing code fingerprint,
configuration, and checksums. Corpus rights are separate from MIT; source-specific
terms and attribution are documented for the approved Arabic configurations.
No publishing workflow is enabled in Phase 1.

Local notebooks and evaluation files are preserved but are not supported package
code. Use separate environments for their exploratory dependencies; the new
foundation environment intentionally excludes the former web/research dependencies.
