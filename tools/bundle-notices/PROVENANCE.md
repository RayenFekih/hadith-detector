# Bundled corpus provenance and redistribution record

This package includes 34,153 Arabic records from QuranLab Hadith revision
`cc6972dae1f46f5f5e2b65e877d24c4539bc4391`.
The configurations are `abudawud-ar` (5,272), `bukhari-ar` (7,580),
`ibnmajah-ar` (4,338), `muslim-ar` (7,360), `nasai-ar` (5,679), and
`tirmidhi-ar` (3,924). Original fields, identities, duplicate narrations,
nullable URLs and source text are preserved. Tokens and the prebuilt MARISA v2
index are derived resources; normalization version is 1.

Credit **QuranLab** (<https://huggingface.co/datasets/quranlab/hadith>) and
**fawazahmed0/hadith-api** (<https://github.com/fawazahmed0/hadith-api>).
The pinned `configs.csv` attributes all six configurations to hadith-api,
describes classical Arabic text as public domain, and marks commercial use as
allowed. Upstream's Unlicense permits copying, modification and redistribution.
Its preserved text was retrieved at commit
`df57907be35291c91ad6a6691180e22ca9920784`; this pins the licensing evidence, not
the unknown upstream data revision used by QuranLab.

## Distinguishing the available evidence

The broad QuranLab `LICENSES.md` summary attributes Arabic material to
Open-Hadith-Data and mentions ODbL/DbCL. The selected configuration rows instead
identify hadith-api. `SOURCES.md` identifies Open-Hadith-Data with Ahmad/Darimi,
which are not bundled. Both notices are preserved verbatim, alongside the full
pinned configuration and collection metadata. Configuration-specific attribution
follows the same evidence used for Bukhari and Muslim in Phase 2.

The four added files include grade labels and named grader attributions as supplied
by QuranLab. Their Parquet schema has no per-row license field. The configuration
metadata identifies public-domain Arabic matn and the hadith-api compilation.
The upstream Unlicense documents the compilation's terms, while the metadata does
not independently establish rights for each grader's annotations. Confirm the
redistribution basis for these fields before public release.

Only the selected Arabic records are redistributed: no translations, HadeethEnc
text, Ahmad/Darimi records, or text scraped from sunnah.com. Source links and
numbering are retained as supplied; links do not establish rights to linked pages.
No independent authentication or grader endorsement is asserted.

The project code is MIT licensed. This does not relicense third-party data.
`UPSTREAM-UNLICENSE.txt`, QuranLab `README.md`, `LICENSES.md`, `SOURCES.md`,
`configs.csv` and `collections.csv` accompany the data. Preserve these notices
when redistributing this bundle. Consult the original notices for attribution,
correction and removal contact information.

## Integrity and build provenance

`_bundle.json` records approved resource payload hashes, counts, versions and
source revision. `_data/manifest.json` records source preparation and builder
fingerprints; `_data/bundle.json` records every staged file and its checksum.
The builder manifest may differ when code or environment provenance changes,
while approved resource payloads must remain byte-identical. No runtime resource
construction or download is performed.
