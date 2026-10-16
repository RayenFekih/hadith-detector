# Phase 7: bundled package and release-readiness review

Validated locally on 2026-10-16. **Implementation is ready for maintainer review;
no release, tag, commit, push or publication was performed.** The manual GitHub
readiness workflow is prepared but has not been dispatched.

## Delivered behavior

`detect(text)`, `annotate(text)`, `get_hadith(key)` and `HadithDetector()` use the
installed combined Bukhari/Muslim bundle. Explicit directories remain supported;
`from_directory()` still requires one. The single-entry cache, configuration
precedence, sequential shared-instance contract and result models are unchanged.
Matching algorithms, RapidFuzz/MARISA dependencies, normalization and index formats
are unchanged. Imports load no corpus. Runtime never downloads or constructs resources.

The bundle retains **14,940 records**, **1,039,600 tokens**, **40,949 vocabulary
terms** and **382,866 trigram keys**. All approved runtime payload hashes match
the existing validated index. Original record fields, duplicate identities, source
occurrences, offsets and nullable URLs are preserved.

## Distribution and installed checks

Candidate version: `0.1.dev27+gf8e724de2.d20261016`, an untagged development build,
not stable `0.1.0`. Reserve `v0.1.0` for a separately approved release.

| Artifact | Bytes | MiB | Location |
| --- | ---: | ---: | --- |
| Original wheel | 18,858,175 | 17.98 | `.cache/phase7-final-dist/` |
| Self-contained sdist | 19,015,940 | 18.14 | `.cache/phase7-final-dist/` |
| Git-free sdist-rebuilt wheel | 18,858,175 | 17.98 | `.cache/phase7-reviewed-rebuilt/` |
| Uncompressed distribution members | 63,384,301 | 60.45 | Wheel contents |
| Installed package directory | 63,366,112 | 60.43 | Excludes dist-info, dependencies and bytecode |

Both archives are comfortably below the current default PyPI 100 MB/file limit.
The original wheel and sdist-rebuilt wheel have identical runtime contents and
versions. Wheel ZIP timestamps are not required to be identical. The final rebuilt
wheel's complete member contents, including metadata and RECORD, also match the
matrix-tested rebuilt wheel; the delivered original and final rebuilt wheel were
additionally clean-installed and probed on Windows/Python 3.14.

SHA-256:

- Original wheel: `cc1abd1c2bf64268fec42bf62bdc56e48a4db64a4689e5da15f9b55ac217c629`.
- Sdist: `bb57c27197c564b5d2ede0f4b82ec91f222d4f8c0df15f7773db90c906513f64`.
- Final rebuilt wheel: `0889d254ef2437bda3273d789a140cbe8fa07dc9c02a0b3f80a180ed1f1480d1`.

The sdist rebuild runs without Git metadata, with preinstalled build requirements,
`--no-isolation`, `UV_OFFLINE=1`, `PIP_NO_INDEX=1` and `HF_HUB_OFFLINE=1`. It needs
neither data-preparation dependencies nor corpus/index construction. Twine accepts
all three delivered artifacts. Wheel metadata retains only RapidFuzz and MARISA
runtime requirements, Python >=3.11, the MIT code license and no extras.

## Compatibility and offline evidence

| Python | Windows 11 x86-64 | Ubuntu 22.04 / WSL2 x86-64 |
| --- | --- | --- |
| 3.11.15 | Passed | Passed |
| 3.12.13 | Passed | Passed |
| 3.13.14 | Passed | Passed |
| 3.14.6 | Passed | Passed |

All eight combinations clean-installed both original and Git-free rebuilt wheel
contents: **16 matrix installations/probes**, **64 saved-result comparisons** and
**96 README example executions**. Each probe runs outside the checkout using `-I -B`,
blocks network operations and writes into the installed package, and verifies
unchanged hashes for all 18 bundled files. The standalone probe imports no repository
tooling. Installed-package code and metadata are used, not a source-path override.

Saved-result comparisons reuse approved Phase 6 evidence: one exact case and one
case each for edits, omissions and combined budgets, selected by first stable ID.
Complete serialized result hashes cover references, every occurrence, costs, traces
and original substrings; source slices are also checked directly. These are targeted
packaging checks, not a repeated recall evaluation or a new independent oracle.
Synthetic regression/oracle fixtures separately cover barriers, ligatures, overlaps,
duplicate identities, nullable URLs, serialization and concurrency.

The supported-version runtime/resource tests passed on every platform/version
(142–143 checks per run as the final staging test was added). The complete final
repository run passed **260 tests**, with **one isolated library-benchmark module
skipped**. That optional performance experiment was intentionally not rerun. The final
five bundle-specific tests passed again after bounded cleanup hardening. Ruff lint,
formatting, strict mypy and frozen lock consistency checks passed.

Observed validated initialization across the 16 final matrix probes was
**4.20–4.54 seconds on Windows**, **3.96–4.69 seconds on Linux/WSL**. These are
diagnostic first-load observations under concurrent validation activity, not a new
latency benchmark or service guarantee. Long-lived instances reuse loaded resources.
Historical memory, latency and oracle evidence remains in the Phase 3–5 reports.

## Reproducibility, provenance and safeguards

- Fresh offline preparation and verification from the existing checksum-pinned
  downloads passed. Fresh Windows and Linux native index builds matched every
  approved runtime payload hash. No original prepared/index directory was modified.
- Staging is deterministic, validates resources before publication, refuses overwrite,
  and removes failed temporary outputs only within the verified staging parent.
  Repeated synthetic staging produced byte-identical files.
- Real production builds reject absent resources with an actionable staging error;
  a fresh editable checkout without staged resources still installs successfully.
- Build guards verify the bundle lock, payloads, notices, receipt and complete file
  inventory. Runtime still performs the original full integrity checks; none were
  weakened for startup speed. Native tries are only loaded from prebuilt files.
- The selected configuration metadata names hadith-api, describes classical Arabic
  text as public domain and allows commercial use. All 14,940 retained records were
  inspected: their fields are the expected original schema, with zero graded records
  and no translation or overriding per-record licensing fields.
- QuranLab's broad ODbL summary conflicts with collection-specific attribution;
  both original notices are preserved. The existing approved provenance decision and
  upstream Unlicense evidence are recorded in the [redistribution record](../tools/bundle-notices/PROVENANCE.md).
  This is evidence-based attribution, not a claim that MIT relicenses third-party data.
- Git attributes preserve the checksum-pinned notices verbatim, including on Windows.
  Generated bundles remain ignored; no LFS, corpus commits or runtime downloads.
- All 29 fingerprinted Phase 6 input/review/backup artifacts and both final evaluation
  manifests still match. No human decisions or evaluation conclusions were altered.

## README review deliverable

The initial [README draft](../README.md) included the title, description, three justified
badges, installation, quick start, features, realistic Arabic examples, configuration,
HTML annotation, qualified evaluation, limitations and attribution. Its six Python
examples executed successfully against installed bundled wheels, including exact,
spelling variation, omission, two passages in longer prose, source lookup/serialization
and escaped annotation. Output is computed, not fabricated.

PyPI's Markdown renderer successfully renders Arabic, tables, headings and code.
The rendered preview is `.cache/phase7-readme.html`; repository link targets resolve
locally. GitHub links refer to the eventual committed main-branch documentation;
no remote update was made. CI is a real dynamic workflow badge; supported versions
and MIT code licensing are accurate static badges. No passing-count, coverage,
download, PyPI-version or wheel-availability badge was invented.

The maintainer subsequently approved a shorter public-facing README with four
Python examples. All four pass against the installed bundled wheel with networking
and resource writes blocked; the same probe also passes its four saved-result checks.
The probe now executes the examples without assumptions about local variable names,
rejects a README with no Python examples, and propagates example failures. Three
focused regression tests pass. Repository documentation links are absolute GitHub
URLs for correct PyPI rendering; all targets resolve to existing repository files.
Fresh verification distributions are under `.cache/phase7-readme-fixes-dist/`;
the earlier archive hashes and six-example matrix totals above remain historical
evidence. The actual `v0.1.0` artifacts must still be built and checked from the
separately approved release tag.

## Reproducing and release gate

Follow [release readiness](release-readiness.md) for staging, builds, clean checks
and the manual non-publishing workflow. Build tools used here include setuptools
84.0.0, setuptools-scm 10.3.4, vcs-versioning 2.6.0 and uv 0.11.26. Native runtime
checks use MARISA 1.4.1 and RapidFuzz 3.14.6 from the frozen lock.

Machine-readable evidence remains ignored in `data/phase7-final-artifacts.json`,
`data/phase7-installed-matrix.json`, `data/phase7-resource-rebuilds.json` and
`.cache/phase7-final-installed-*/probe-*.json`. Logs and both candidate generations
are preserved under `.cache/phase7-*`; the delivered paths are the ones above.
The validation report is intentionally excluded from the sdist whose checksum it records.

**Assessment:** locally ready for initial-release review within the documented
textual-matching scope. Hosted GitHub Actions has not run; local Linux evidence is
WSL2, not a claim of tests on every Linux distribution. macOS, ARM and dependency
source-build environments remain unverified. No deployment-wide precision/recall
claim follows from packaging checks or the small Phase 6 pilot.

Before publication, approve the README/candidates, run the hosted readiness workflow
after approved ordinary commits/pushes, choose the release tag, and validate the exact
tagged release artifacts. Add public installation/version/wheel badges only after
publication. All remote operations and publication require separate instructions.
