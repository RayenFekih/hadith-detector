# Phase 6 preparation handoff

Status: proposed dataset and labels are ready for maintainer review. No gold
labels, precision/recall scores, confirmed false-positive conclusions or production
setting recommendations have been finalized. No production files, dependencies,
normalization, resources or public interfaces were changed. No commits or pushes
were made.

## Review deliverable

Open **`data/phase6-review-ready/review.csv`** using the
[review instructions](phase6-review.md). It contains **453 rows**: **136 paragraph
assessments** and **317 deduplicated span proposals**. All **453 decision cells
are blank**. Editable decision/correction columns appear first.

The two groups remain separate:

- **96 corpus-derived candidates**, imported without altering their identities,
  query text, source text, source offsets or original research file. The 500-record
  source sample remains a reserve and was not evaluated again.
- **40 natural paragraphs**, twenty from four quotation-rich classical commentary
  pages and twenty from four general Arabic encyclopedia articles. Input-first
  draft spans include intended quotations, explicit Quranic wording and uncertainty.
  These are enriched related sources, not a representative sample of deployment traffic.

Inputs and proposed spans were frozen before detection. The CSV shows up to 50
reference identities per span, explicitly counted and labeled, so even common
phrases fit spreadsheet cells. Known original references are prioritized in the
preview. **Complete identity unions are retained in `reference-unions.jsonl`; every
record, occurrence and canonical trace remains in `evidence.jsonl`.** No detection
or supporting evidence was capped.

The final CSV is 1,226,465 bytes; its largest cell contains 3,720 characters.
The raw complete evidence is approximately 165 MiB because common phrases support
many source identities and each configuration retains full original metadata.
It stays ignored alongside generated inputs and outputs.

## Six-configuration evidence

The capture includes **816 case/configuration results**, including empty results.
All six settings are compared against `(5,0,0)` within each group. No defaults
were changed. Source identities and original input/source slices were validated
while capturing results.

The following are **candidate unwanted-alert counts on 22 natural paragraphs
provisionally proposed as quotation-free**, including two commentary paragraphs.
They are review aids, not confirmed false positives or quality scores:

| Minimum / edits / omissions | Affected paragraphs | Candidate unwanted detections | Detection-count difference from default |
| --- | ---: | ---: | ---: |
| 3 / 0 / 0 | 5 | 10 | +7 |
| **5 / 0 / 0** | **2** | **3** | **0** |
| 7 / 0 / 0 | 1 | 1 | -2 |
| 5 / 1 / 0 | 2 | 4 | +1 |
| 5 / 0 / 1 | 2 | 3 | 0 |
| 5 / 1 / 1 | 2 | 4 | +1 |

`preparation-summary.json` records affected paragraph identities, counts and
added/removed spans relative to defaults. `candidate-alerts.jsonl` lists every
offending original text span, offsets, configuration and complete supporting
identity list. CSV uncertainty flags identify the corresponding review proposals.
No corpus-derived paragraph was preclassified as quotation-free; zero entries in
that inventory do not imply zero false positives for that group.

## Reproducibility and checks

- All eight public pages have pinned revision IDs, response checksums, source/history
  URLs, extraction boundaries and attribution/reuse terms in the compact source lock.
  Only acquisition accesses the network; freeze, capture and replay operate locally.
- Repeated input freezing produced byte-identical case and manifest files.
- Replaying saved results reproduced the final CSV, complete reference unions,
  candidate-alert inventory and count summary byte-for-byte, with **zero detector calls**.
  The spreadsheet-friendly layout was rebuilt from captured evidence without another
  evaluation run; its manifest retains original capture fingerprints separately.
- Review validation confirms all decisions remain pending, immutable texts and
  proposal fields are intact, configuration/reference IDs exist and offsets slice
  original strings correctly. It never marks gold approved.
- **14 focused tests pass** for source extraction/pinning, 96+40 freezing,
  deduplication, full record/occurrence preservation, formula-safe CSV round trips,
  correction fields, missing spans, uncertainties, corruption, failed-capture cleanup,
  bounded reference previews and complete offline replay.
- Ruff lint/format and strict package mypy pass. Production Python files,
  `pyproject.toml` and `uv.lock` are unchanged. Historical algorithm, performance,
  memory, dependency, compatibility and annotation benchmarks were not rerun.

| Final artifact | SHA-256 |
| --- | --- |
| `review.csv` | `3c0b2361c4efdcd4730286765397cfe3e0c8789d1b7fe12886afcaedbaf10471` |
| Review manifest | `e4998d9e5fb421dd5a0788eefd2d0748e05b31b65bfe0c9b26379dedfa3e8521` |
| Complete evidence | `947661a2d12e8f797c89ab3998857758d443839a025f6a7ffc3479d59f6bbfa2` |
| Complete reference unions | `5302cb62c8af1a2b281cf7f918ba723054b6ae3870fbd924dc3665ea575cb0c1` |
| Preparation count summary | `df4ed2ba975f95c3a1ec973e13c3eb6cef79781ccdbab723238bd0ef918b7178` |

The manifest records dataset/index fingerprints, the six configurations,
preprocessing code/lock hashes and Python/Unicode/RapidFuzz/MARISA versions.
The source and draft metadata remain distinct from final human-approved labels.

## Stop point

Review paragraph status, quotation intent, boundaries, references and unresolved
cases in the CSV. A correct corpus-supported string can still be an unwanted
alert; intended quotation judgments must not be inferred from detector support.
No final gold or quality conclusions are generated until the maintainer approves
the reviewed annotations. Phase 7, commits, pushes and releases remain outside
this work.
