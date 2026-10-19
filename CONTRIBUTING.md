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
```

Default resource use and production builds now require offline staging of the approved
bundle. Packaging tests prepare synthetic bundles in isolated source trees, so normal
CI does not fetch the corpus. For real wheel/sdist builds, stage verified resources
first and follow [release readiness](docs/release-readiness.md). Its manual workflow
tests actual bundled candidates on both Linux and Windows, Python 3.11–3.14.

In PowerShell, if wildcard expansion for twine is unavailable, use
`Get-ChildItem dist -File | ForEach-Object { uv run twine check $_.FullName }`.
Packaging tests invoke uv, resolve isolated build dependencies, build a wheel from
an sdist without Git metadata, and install both wheels in fresh environments.
Preparation downloads compatible runtime dependency wheels listed in `uv.lock`
and verifies their SHA-256 hashes. Both clean installations then use that local
wheelhouse with `--offline --no-index --no-cache`, so a warm registry cache cannot
hide missing dependencies. Installed-library probes also block network access.
Build/dependency preparation may access the network; offline installation and
runtime imports do not.
Use `uv run pytest -m "not packaging"` for the fast foundation checks.

Phase 2 preprocessing uses `uv sync --locked --group data`. Run its tests with
`uv run --frozen --group data pytest`; the default environment skips the synthetic
pipeline tests when preprocessing dependencies are absent. Shared normalization
tests run on every supported Python. Full builds require Python 3.14. Ordinary CI
uses synthetic Parquet data and does not fetch the real corpus. See the
[data-preparation guide](docs/data-preparation.md) for full-corpus validation.

Index experiments use `uv sync --locked --group benchmark`. Run the synthetic
worker smoke test with `uv run --frozen --group benchmark pytest tests/test_exact_benchmark.py`.
The exhaustive oracle, retrieval, serialization and randomized reference tests
need no benchmark dependency; only the subprocess memory-measurement smoke test
needs psutil. Full-corpus performance experiments are local and never run in CI.
See [benchmark usage](docs/index-benchmark.md).

Phase 3B runtime and synthetic index-builder tests need no optional dependencies
and run across the supported Python matrix. Full-corpus index construction uses
Python 3.14 and the verified prepared artifacts; see [runtime resources](docs/runtime-index.md).
Fresh-process validation measurements use the separate `benchmark` group.

Phase 4B requires RapidFuzz at runtime; the benchmark group pins 3.14.6 for reproduction.
Run the repository's synthetic
oracle/retrieval/backend checks with `uv run --frozen --group benchmark pytest tests/test_fuzzy_benchmark.py`.
The normal environment skips RapidFuzz parity and subprocess tests if their optional
tools are absent. See [fuzzy experiments](docs/fuzzy-benchmark.md) for full-corpus commands.
Dependencies are assessed on their merits; offline operation is required, while
zero runtime dependencies is not a permanent project rule. The maintainer approved
RapidFuzz as the sole production distance engine and authorized Phase 4B. Python
distance implementations stay in repository tests/benchmarks. Further phase changes
require review and approval.

Ruff handles linting and formatting (100-character lines, Python 3.11 syntax).
Mypy checks package code in strict mode. Regenerate `uv.lock` with `uv lock` only
when dependencies change, then rerun checks. No pre-commit hook is required.

## Review and Git workflow

MCP development uses `uv sync --locked --extra mcp`; retain `--extra mcp` on
`uv run --frozen` commands for tests, Ruff, and mypy. Base installations remain
independent of the SDK. See [MCP checks and packaging](docs/mcp.md#development-checks).

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

Phase 3A proposed commit boundaries:

1. `test: establish exhaustive exact-match oracle`
2. `perf: benchmark positional and n-gram indexes`
3. `docs: record index benchmark and recommendation`

Phase 3B proposed commit boundaries:

1. `feat: add compact offline index resources`
2. `feat: implement provisional exact detector`
3. `docs: record runtime validation and API usage`

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
