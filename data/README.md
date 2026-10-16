# Data and artifact policy

The bundled corpus is [QuranLab Hadith](https://huggingface.co/datasets/quranlab/hadith),
using only `bukhari-ar` and `muslim-ar`. Local inspection reports 7,580 and 7,360
records respectively; these are observations, not hardcoded integrity guarantees.
Duplicate text must retain every original identity, and reference URLs may be null.

Phase 7 stages the approved runtime corpus and MARISA v2 index into ignored package
data for wheel/sdist builds. See [release readiness](../docs/release-readiness.md) and
the [preserved redistribution record](../tools/bundle-notices/PROVENANCE.md).
No runtime corpus was bundled in Phase 2. Existing local CSVs, archives, inspection
reports, notebooks, and evaluation files remain ignored and untouched. They must
not be silently treated as the pinned source for a reproducible build.

## Approved provenance

MIT covers project code, not third-party data. Review the pinned dataset's
[card](https://huggingface.co/datasets/quranlab/hadith),
[LICENSES.md](https://huggingface.co/datasets/quranlab/hadith/blob/main/LICENSES.md),
[SOURCES.md](https://huggingface.co/datasets/quranlab/hadith/blob/main/SOURCES.md),
configuration metadata, and applicable upstream terms. The maintainer confirmed
that licenses are acceptable and authorized proceeding with both Arabic configurations.
Their pinned configuration metadata identifies classical Arabic text as public domain,
compilation via `fawazahmed0/hadith-api`, and commercial use as allowed. The upstream
[license](https://github.com/fawazahmed0/hadith-api/blob/1/LICENSE) is the Unlicense.
Credit QuranLab and fawazahmed0/hadith-api and retain the original provenance notices.
Translations and unrelated configurations are outside this build.

The general LICENSES summary mentions the ODbL source broadly; configuration metadata
and SOURCES distinguish it as the source for Ahmad/Darimi, which are not included.
These facts and the maintainer's decision are recorded rather than rewriting upstream notices.

All seven downloaded files are pinned by revision and SHA-256 in
[`tools/source-lock.json`](../tools/source-lock.json). The raw provenance documents
are retained with the ignored source snapshot. See
[data preparation](../docs/data-preparation.md) and the
[acceptance report](../docs/phase2-validation.md).

## Artifact boundaries

- Git: preprocessing code, small synthetic fixtures, manifests, checksums, and reports.
- Local build workspace: raw downloads, preserved records, intermediate tokens and offsets.
- Release assets: reproducible large build artifacts, after licensing approval.
- Python distribution: necessary original runtime records, manifest, and prebuilt index only.

Keep source records, preprocessing tools, derived artifacts, and runtime resources
separate. Preserve all original fields and source text without normalization edits.
Version record schema, normalization and index format independently. Phase 3B used
index format 1; MARISA production uses v2. Generated directories remain ignored;
Phase 7 includes only approved runtime resources and notices in distributions.
See [runtime resources](../docs/runtime-index.md).
Pin upstream
and preprocessing revisions and record configuration and checksums.
Do not introduce LFS or DVC or commit large artifacts without discussing tradeoffs.

Existing evaluation material includes 500 source examples and 96 unlabelled review
candidates. Sampling labels are not semantic ground truth; expected references
must be verified against the complete corpus.
