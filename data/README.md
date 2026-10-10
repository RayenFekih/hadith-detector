# Data and artifact policy

The planned corpus is [QuranLab Hadith](https://huggingface.co/datasets/quranlab/hadith),
using only `bukhari-ar` and `muslim-ar`. Local inspection reports 7,580 and 7,360
records respectively; these are observations, not hardcoded integrity guarantees.
Duplicate text must retain every original identity, and reference URLs may be null.

No runtime corpus is bundled in Phase 1. Existing local CSVs, archives, inspection
reports, notebooks, and evaluation files remain ignored and untouched. They must
not be silently treated as the pinned source for a reproducible build.

## Rights gate

MIT covers project code, not third-party data. Review the pinned dataset's
[card](https://huggingface.co/datasets/quranlab/hadith),
[LICENSES.md](https://huggingface.co/datasets/quranlab/hadith/blob/main/LICENSES.md),
[SOURCES.md](https://huggingface.co/datasets/quranlab/hadith/blob/main/SOURCES.md),
configuration metadata, and applicable upstream terms. Current summaries disagree
about provenance and where binding terms are stored. Phase 2 must document the
terms for both selected configurations before public corpus redistribution.

## Artifact boundaries (planned)

- Git: preprocessing code, small synthetic fixtures, manifests, checksums, and reports.
- Local build workspace: raw downloads, preserved records, intermediate tokens and offsets.
- Release assets: reproducible large build artifacts, after licensing approval.
- Python distribution: necessary original runtime records, manifest, and prebuilt index only.

Keep source records, preprocessing tools, derived artifacts, and runtime resources
separate. Preserve all original fields and source text without normalization edits.
Version record schema, normalization, and index format independently; pin upstream
and preprocessing revisions and record configuration and checksums.
Do not introduce LFS or DVC or commit large artifacts without discussing tradeoffs.

Existing evaluation material includes 500 source examples and 96 unlabelled review
candidates. Sampling labels are not semantic ground truth; expected references
must be verified against the complete corpus.
