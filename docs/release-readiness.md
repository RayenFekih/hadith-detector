# Bundled distributions and release readiness

Phase 7 prepares candidates for review. It does not create a release, tag, push,
upload to PyPI, or claim a published version. `v0.1.0` remains reserved for the
approved first release; untagged builds retain setuptools-scm development versions.

## Install a candidate

Install the reviewed wheel and its RapidFuzz/MARISA dependencies using pip. No
corpus acquisition or preparation is needed by users. After installation, operations
are offline, including the first call. For an offline installation, acquire wheels
compatible with the target Python/platform before disconnecting:

```sh
python -m pip download --only-binary=:all: --dest wheelhouse /path/to/candidate.whl
python -m pip install --no-index --find-links wheelhouse /path/to/candidate.whl
```

Replace the candidate path with the actual filename. Standard unpacked pip installs
are supported; zip-import installations are not. Binary dependency wheels are
platform-specific even though the package's own wheel is `py3-none-any`.
Do not replace or edit installed resources. Missing/corrupt bundled resources require
reinstallation; an explicitly supplied invalid directory never falls back silently.

## Maintainer preparation

Use Python 3.14.6, Unicode 16.0.0, MARISA 1.4.1 and the frozen uv lock. The resource
payload lock is `src/hadith_detector/_bundle.json`. It pins corpus/index bytes,
counts, source revision, versions and provenance notices. Builder manifests retain
their actual environment/code fingerprints and can differ after tooling changes;
this does not authorize changes to approved payloads.

```sh
uv sync --locked --group data
uv run --frozen --group data python -m tools.prepare_data fetch --source-dir data/release-source
uv run --offline --frozen --group data python -m tools.prepare_data build --source-dir data/release-source --output-dir data/release-prepared
uv run --offline --frozen --group data python -m tools.prepare_data verify --source-dir data/release-source --output-dir data/release-prepared
uv run --offline --frozen python -m tools.build_index --corpus-dir data/release-prepared --output-dir data/release-index
uv run --offline --frozen python -m tools.stage_bundle --index-dir data/release-index
uv build --no-sources
uv run --frozen twine check dist/*
```

If verified prepared/index resources already exist, stage those directly instead of
refetching/rebuilding. Staging verifies every runtime invariant and payload hash,
then publishes a new ignored `_data` directory; it refuses overwrite. Use a fresh
checkout for repeated staging. Existing source/index directories are preserved.
No optional library installation, editable installation, or ordinary build hook
downloads or constructs a corpus. Editable checkouts can use explicit resources
before staging; production wheel/sdist builds fail if staged files are incomplete.

Both wheel and sdist contain the full runtime bundle and notices. The sdist also
contains build/preparation tooling. Neither includes raw Parquet, research notebooks
or evaluation outputs. Original licensing notices and the collection-specific
[redistribution record](../tools/bundle-notices/PROVENANCE.md) accompany the corpus.
Code is MIT; third-party data terms are separate.

## Actual candidate checks

Install the build-system requirements into the checking environment before going
offline (`setuptools>=80`, `setuptools-scm>=8`, plus the locked development group).
This changes the checking environment, not installed runtime requirements.

```sh
python -m tools.release_artifacts --dist-dir dist --rebuild-dir .cache/release-rebuild
python -m tools.release_install --artifacts-dir .cache/candidates --output-dir .cache/installed-checks
```

For the second command, place the original wheel and sdist-rebuilt wheel in separate
subdirectories under `.cache/candidates` (their filenames can be identical).
The tool acquires hash-verified locked dependency wheels, then installs each candidate
in a new isolated environment with `--offline --no-index --no-cache`. Its standalone
probe runs outside the checkout using `-I -B`, blocks network and installed-resource
writes, checks approved saved detection hashes and runs every README Python example.
It records Python/platform, import/init timings, installed size and unchanged resource
hashes. The probe covers saved evidence from exact and all three controlled fuzzy
types; it does not repeat the historical evaluation or performance suite.

The artifact checker verifies sizes below the default PyPI 100 MB/file limit,
notices, payloads and metadata. It rebuilds the sdist wheel without Git and without
dependency resolution/network access, then compares runtime contents and versions.
Dependency-wheel acquisition and initial isolated build preparation may use network;
the sdist rebuild, clean installations and library probes do not.

## CI and approval gates

Ordinary CI builds synthetic distributions in isolated temporary source trees and
runs regressions, Ruff and strict mypy. Synthetic bundles never replace the production
lock or staged full corpus. The manually dispatched **Release readiness (no publishing)**
workflow prepares the real pinned corpus, builds candidates and runs installed
checks on Linux and Windows, Python 3.11–3.14. Artifacts expire after 14 days; download
and preserve reviewed candidates/checksums before expiry. The workflow has read-only
repository permissions and no upload-to-registry or release-creation steps.

Before publication, review:

- Configuration-specific redistribution evidence, notices and attribution; resolve
  any material rights issue rather than treating the MIT code license as data rights.
- Exact source record counts, payload hashes, index v2/normalization v1 and offline checks.
- Actual wheel/sdist sizes, metadata, Git-free version recovery and eight matrix results.
- README draft, executable Arabic examples, configuration guidance and qualified evaluation.
- Candidate checksums and [Phase 7 validation report](phase7-validation.md).
- Explicit approval of release version, ordinary commits/pushes, release tag and publication.

Only after those separate approvals should a maintainer build from the approved tag,
repeat candidate checks on those exact tagged artifacts, and run publication commands
such as `python -m twine upload dist/*`. No credentials, publisher configuration,
publishing workflow or automatic publication is introduced in this phase. PyPI/wheel
badges and public `pip install hadith-detector` instructions follow actual publication.
