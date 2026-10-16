# Phase 6 evaluation results

Review date: 2026-10-16. Final technical review; Phase 7 is not started.

All 382 required judgments are present: correspondence **191/191 Yes**, boundaries **191/191 Yes**. All 13/13 zero-alert screens are acknowledged.

## Human review — displayed input/source pairs

| Group | Inputs | Correspondence Yes | Boundaries Yes | Uncertain pairs |
| --- | ---: | ---: | ---: | ---: |
| exact | 10 | 10/10 | 10/10 | 0 |
| fuzzy | 10 | 27/27 | 27/27 | 0 |
| natural | 15 | 2/2 | 2/2 | 0 |
| commentary | 20 | 152/152 | 152/152 | 0 |
| **Total** | 55 | 191/191 | 191/191 | 0 |

Reported correspondence mismatches: 0/191; boundary corrections: 0/191. Missing judgments: 0/382.

These are 191 deduplicated spans reviewed once across settings, with one displayed supporting source occurrence per span. They are not 191 independently sampled documents, an audit of every reference, or quotation-intent labels.

## Automated controlled-target recovery and descriptive alerts

Configuration tuples are (minimum words, character edits, source omissions). Fractions below use **all selected inputs**; eligibility is explained afterward.

| Settings | Exact | Edits | Omissions | Combined | Full targets | Recovered target boundaries | General prose: paragraphs / alerts | Commentary: paragraphs / detections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| (3, 0, 0) | 10/10 | 0/4 | 0/4 | 0/2 | 10/20 | 10/10 | 2/15 / 2 | 20/20 / 117 |
| (5, 0, 0) **default** | 10/10 | 0/4 | 0/4 | 0/2 | 10/20 | 10/10 | 0/15 / 0 | 20/20 / 58 |
| (7, 0, 0) | 8/10 | 0/4 | 0/4 | 0/2 | 8/20 | 8/8 | 0/15 / 0 | 17/20 / 38 |
| (5, 1, 0) | 10/10 | 4/4 | 0/4 | 0/2 | 14/20 | 14/14 | 0/15 / 0 | 20/20 / 63 |
| (5, 0, 1) | 10/10 | 0/4 | 4/4 | 0/2 | 14/20 | 14/14 | 0/15 / 0 | 20/20 / 60 |
| (5, 1, 1) | 10/10 | 4/4 | 4/4 | 2/2 | 20/20 | 20/20 | 0/15 / 0 | 20/20 / 65 |

Full recovery requires the complete frozen input target and its originating source identity/occurrence; a matching fragment is not success. Human boundary acceptance of a returned fragment is distinct from recovery of the complete constructed quotation.

### Eligibility, incomplete recovery and differences from defaults

- `(3, 0, 0)`: eligible recovery **10/10**; 10/20 inputs have only partial matches and 0/20 have no detections. Full-target gains/losses: +0/−0; added/removed input spans: +69/−0.
- `(5, 0, 0)`: eligible recovery **10/10**; 6/20 inputs have only partial matches and 4/20 have no detections. Full-target gains/losses: +0/−0; added/removed input spans: +0/−0.
- `(7, 0, 0)`: eligible recovery **8/8**; 4/20 inputs have only partial matches and 8/20 have no detections. Full-target gains/losses: +0/−2; added/removed input spans: +0/−24.
- `(5, 1, 0)`: eligible recovery **14/14**; 5/20 inputs have only partial matches and 1/20 have no detections. Full-target gains/losses: +4/−0; added/removed input spans: +24/−16.
- `(5, 0, 1)`: eligible recovery **14/14**; 4/20 inputs have only partial matches and 2/20 have no detections. Full-target gains/losses: +4/−0; added/removed input spans: +17/−13.
- `(5, 1, 1)`: eligible recovery **20/20**; 0/20 inputs have only partial matches and 0/20 have no detections. Full-target gains/losses: +10/−0; added/removed input spans: +38/−27.

The seven-word setting excludes `S0009` and `S0060`, each with five normalized words. Fuzzy targets are outside zero-error/zero-omission budgets by construction. These are expected limitations, not concealed eligible-case failures. The default returns fragments on six fuzzy inputs and nothing on four. `(5,1,1)` fully recovers all 20 positives with exact target boundaries. Eligible full-target failures: 0; unresolved human-reviewed pairs: 0/191. Detailed missing/partial IDs and paired common-eligibility comparisons are in the machine-readable results.

General-prose alerts occur only at the three-word minimum, on two paragraphs. Religious-commentary detections are descriptive textual support: neither their presence nor human acceptance establishes intended quotation, authentication or false-positive status. Different spans added/removed across settings include boundary replacements, not just new quotations. Defaults remain unchanged.

The two general-prose alerts at `(3,0,0)` are `N0040[705:716]`: **هو عبد الله**, supported by `bukhari:563`, `muslim:804`, `muslim:3366`; and `N0032[857:868]`: **كاد أن يكون**, supported by `bukhari:4757`. Both were accepted as textual correspondences. They are incidental alerts, not independently established quotation-intent false positives.

Common wording can have very broad support: `N0017[496:514]`, **صلى الله عليه وسلم**, has 13,037 supporting identities at `(3,0,0)`. This is not unique attribution; references were not truncated.

## Validation, provenance and existing evidence

Frozen input/capture hashes, review snapshot, scoring-code fingerprints and result checksums are retained in the final artifact manifest. Selection used input-only hash ranking and included all 20 commentary paragraphs. Existing six-answer migration and excluded S0002 judgments remain archived, unchanged; excluded judgments are not scored here.

The review projection was reproduced from checksummed saved outputs. Every returned reference was checked against the pinned original corpus, and all input/source offsets, mapped word traces, barriers, whole-symbol endpoints, omissions and recorded character costs were checked. These checks validate supplied evidence; they do not search for missing candidates or rerun an independent exhaustive oracle.

Evidence validation covered 330 case/configuration outputs, 512 detections, 66,586 reference entries and 83,206 source occurrences. This automated integrity coverage is separate from the 191 displayed pairs reviewed by a human.

Independent oracle agreement, latency, memory, packaging and compatibility results are reused from [Phase 3B](phase3b-validation.md), [Phase 4B](phase4b-validation.md), [MARISA production](marisa-production.md) and [Phase 5B](phase5b-validation.md). Phase 5B records 168 exact, 168 fuzzy and 39 representative oracle cases plus Python 3.11–3.14 Windows/Linux checks. Those are automated historical evaluations, separate from this maintainer's 191-pair review; none were rerun for Phase 6 finalization.

## Limitations and initial-release assessment

This is a small, reused convenience sample: 10 exact, 10 controlled fuzzy (4/4/2), 15 general prose and 20 related religious-commentary paragraphs. One maintainer reviewed representative source passages. Controlled examples are artificial; natural-text gold quotation spans and independently verified intent labels do not exist. There is no deployment-wide precision/recall estimate, false-positive rate, per-reference human completeness claim or Hadith authenticity claim. No new performance claim or automatic configuration recommendation follows.

**Assessment:** sufficient technical evaluation for an initial release within the documented exact/fuzzy textual-matching scope, combined with the previous oracle and compatibility evidence. Phase 7 still must package the approved corpus/index and attribution, verify the actual bundled wheel/sdist and offline installations, and complete release review. No Phase 7 work, commit, push or publication is authorized by this report.

## Reproducing the evaluation

With the preserved local frozen inputs, evidence and review decisions, run:

```sh
uv run python -m tools.evaluation.finalize --approve-reviewed-results --review-date 2026-10-16 --output-dir data/phase6-evaluation-rebuild
```

Use a new output directory; existing outputs are never overwritten. The command validates saved traces and scores saved results without detector calls. The output includes results.json, the review snapshot and a checksummed manifest. Determinism requires the same frozen inputs, annotations, code and recorded environment.

## Finalization checks

- Two independent offline finalization runs produced byte-identical results, reports, review snapshots and manifests; no detector calls or historical benchmark runs.
- 43 focused evaluation/notebook tests passed; repository-wide Ruff lint/format checks and strict package mypy passed.
- All 29 fingerprinted source/review/backup artifacts remained unchanged. Production code, defaults, resources, dependencies and public API were not changed.
- Final artifacts: `data/phase6-evaluation-final-20261016/`; reproducibility run: `data/phase6-evaluation-repro-20261016/`. These generated directories remain ignored.
- Final manifest SHA-256: `091a5645ec54eebac541c706dc5bf7d82ac7f2a4a5a87f09088eb934b36db81a`.
- Saved review SHA-256: `065b7d93939e0fe262cb22af0f96ce743d11421b1a1b64d3c15befc128b475ca`.
