# Phase 2 acceptance evidence

Validated on 2026-10-12. No corpus/index is included in Git or the Python wheel.

## Full-corpus validation

- Source: QuranLab revision `cc6972dae1f46f5f5e2b65e877d24c4539bc4391`; all seven source-lock hashes verified.
- Records: **14,940** (7,580 Bukhari, 7,360 Muslim), retaining every field, source identity and original text.
- Normalized tokens: **1,039,600**; records without tokens: 0.
- Duplicate-text extra records retained: **375**; nullable URLs retained: **26**.
- Original sequence gaps retained: 9 Bukhari and 203 Muslim; no renumbering or inferred records.
- Text warnings: **63 replacement characters**, **51 orphan marks**, **8 unexpected characters**, across **68 records**. No repairs or record exclusions.

The ignored validation report lists every affected identifier and character span,
plus duplicate-text groups and source sequence gaps. These are source-quality
observations, not semantic Hadith evaluation or detector accuracy measurements.

## Reproducibility and environment

Two new directories (`data/phase2-final-a` and `data/phase2-final-b`) were built
independently. All four files are byte-identical. Both builds ran verification
before acceptance and were verified again with `UV_OFFLINE=1` and
`HF_HUB_OFFLINE=1`. Dependencies and local source files were already present.

- Python: 3.14.6 (CPython); Unicode: 16.0.0.
- huggingface-hub: 2.2.0; PyArrow: 26.0.0.
- uv.lock SHA-256: `e73400dcf6b299555b068585bf7e2d6d52da2b843efd572557468c3578d97dc6`.
- Build fingerprint: `c40cd18c64efcef952cba3f98e98b964257e5bb66e566726510eb3b36ade804e`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `records.jsonl` | 20,570,642 | `9ec8e19aaab80ffbc01aa162122060099bc0a5de3841b544b4afa1c381414246` |
| `tokens.jsonl` | 56,349,001 | `ee07fce76d7862854e069ef81d72255cf3cb616daad9d0c57977e287a4e11f33` |
| `validation.json` | 50,008 | `0e2187d3b4e7abb19de4648de54ff5ec79c595893fc5a8ef659dd8ed5baadbb1` |
| `manifest.json` | 2,134 | `f0ee8509b911b7835771de94fe65a97a17098ebba53de57f9c274dd077a5a0e2` |

The manifest records exact source/configuration and preprocessing-code fingerprints.
The manifest checksum above is external; the manifest itself hashes the other three files.
A changed environment, code fingerprint or dependency lock requires a new acceptance report.

## Automated checks

- **41 tests passed** on Windows/Python 3.14.6 with uv network access disabled.
- **20 normalization tests passed on each of Python 3.11.15, 3.12.13, 3.13.14 and 3.14.6**.
- Ruff lint and formatting checks and strict package mypy passed.
- Wheel/sdist metadata, clean installations, and wheel rebuild without Git metadata passed.
- Packaging tests confirm no runtime dependencies, bundled corpus, or installed downloader tools.
- CI includes the supported Python matrix plus a Python 3.14 synthetic-data job; hosted CI has not been run in this implementation session.

Phase 3 indexing and detection have not started. Review these changes before committing
and approving the next phase. See [data preparation](data-preparation.md) for commands and formats.
