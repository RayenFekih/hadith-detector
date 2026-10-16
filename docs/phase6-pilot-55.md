# Phase 6: 55-input technical pilot

Review completed; see the [final evaluation](phase6-evaluation.md). The instructions
below describe the preserved review workflow. Saved decisions and inputs are unchanged.

## Start or resume

```powershell
uv run --group review jupyter lab notebooks/phase6_review.ipynb
```

Restart the kernel if an earlier review interface is open, then run the two code
cells. Use one active review session. Valid decisions save automatically to
**`data/phase6-pilot-55-progress.json`**; restarting resumes at the first unfinished
input. The original progress file is not overwritten.

The screen shows the **complete original Arabic input**, with all detections
highlighted and grouped on one screen. Each unique input span is paired with a
matching original corpus passage. Duplicate spans across configurations are reviewed
once; differing boundaries remain distinct. Allowed and used character edits and
omissions are shown, edited word pairs are listed, and omitted source words are pink.
Every source identity, occurrence and alignment trace remains in expandable evidence.

For each pair answer only:

- Textual correspondence: **Yes / No / Uncertain**.
- Matching boundaries: **Yes / Correct / Uncertain**.

Correct opens an original-character offset editor with previews. End offsets are
exclusive Python string indices. Incomplete corrections save as drafts; invalid
edits do not replace valid saved progress. Notes save on leaving the notes field
or using navigation. Save & Next completes a screen; Skip saves partial work.
Uncertain is saved but unresolved. Do not judge authenticity or quotation intent.

## Composition and exact review workload

| Group | Frozen inputs | Unique span pairs | Correspondence choices | Boundary choices |
| --- | ---: | ---: | ---: | ---: |
| Controlled exact excerpts | 10 | 10 | 10 | 10 |
| Controlled modified excerpts | 10 | 27 | 27 | 27 |
| General Arabic prose | 15 | 2 | 2 | 2 |
| Religious commentary | 20 | 152 | 152 | 152 |
| **Total** | **55** | **191** | **191** | **191** |

There are **382 judgments plus 13 zero-alert acknowledgements**. Three previously
reviewed pairs, containing six answers, were migrated unchanged. Initially **376
judgment choices remain unanswered**. There are at most 29 pairs on a screen.
The commentary increases review work substantially; no difficult cases, short
matches or configuration variants were removed to reduce that count.

The 13 zero-alert screens are general prose. Save & Next merely acknowledges them;
it does not establish that their text contains no Hadith. Each screen identifies
its group clearly. All 20 frozen commentary paragraphs are included regardless
of detector output or earlier provisional quotation labels.

## Reproducible selection and evidence reuse

The exact subset keeps the existing input-only eligibility rules and hash ranking
`SHA256("phase6-pilot-v1|42|" + original_case_id)`, with ID tie-breaking. Quotas in
the historical stratum order are **3 quote-marked, 3 middle-window, 2 opening-window,
2 long-narration**. Fuzzy quotas are **4 character-edit, 4 omission, 2 combined**,
using the same existing eligible pools and ranking. Both are subsets of the previous
pilot, selected independently of detector success or reviewer answers. General-prose
selection is unchanged: 15 paragraphs with source quotas 4/4/4/3. Commentary takes
all 20 original frozen inputs, with no detector- or annotation-based filtering.

Two independent 55-input freezes are byte-identical. No new examples were collected
or generated. All **330 case/configuration outputs** were reused: 270 from original
Phase 6 evidence and 60 fuzzy outputs from the 50-input pilot. **Zero detector calls,
oracle reruns or benchmark reruns** were required. Complete detection payloads,
including source records and every occurrence, are unchanged from their parents.
Six settings remain compared with `(5,0,0)`; defaults and resources are unchanged.

Frozen inputs: `data/phase6-pilot-55-inputs/`. Capture/review:
`data/phase6-pilot-55/`. The complete evidence is 165,921,880 bytes; it is deliberately
not truncated. Generated resources and annotations remain ignored by Git.
The [selection lock](../tools/evaluation/pilot-selection.json) records every ID and
input checksum; [the original lock](../tools/evaluation/pilot-selection-50.json)
is retained separately.

| Artifact | SHA-256 |
| --- | --- |
| 55-input manifest | `eda4dc5de7cbd963b916984614fe99001ccc998330bb0bb70919d71304250fdc` |
| 55-input capture manifest | `83d592c0892ef1ea89ec5e1709302ffa08322e6fb67511ada172aae62587cca4` |

To reproduce into new directories:

```powershell
uv run python -m tools.evaluation.pilot freeze --profile 55 --index-dir data/runtime-index-v2-a --output-dir data/phase6-pilot-55-inputs-new
uv run python -m tools.evaluation.pilot capture --inputs-dir data/phase6-pilot-55-inputs-new --index-dir data/runtime-index-v2-a --reuse-inputs data/phase6-pilot-inputs --reuse-run data/phase6-pilot --output-dir data/phase6-pilot-55-new
```

Input freezing is a separate step before outcomes are projected. Existing output
directories are never overwritten. `--profile 50` retains the historical composition.

## Preserved annotations and approved migration

The original dataset, 453-row research CSV, evidence and annotations are unchanged.
The original 50-input directories and `data/phase6-pilot-progress.json` also remain
byte-for-byte intact. A full backup at **`data/phase6-pilot-50-backup/`** contains their
inputs, capture, saved progress, notebook and supporting tool versions with checksums.
The [50-input notebook](../notebooks/phase6_review_50.ipynb) still uses the old paths.
See its [historical handoff](phase6-pilot-50.md).

Migration copied the complete saved answers for these identical pairs:

- `S0001:span:2:455`
- `S0009:span:2:51`
- `S0060:span:2:46`

The pair **`S0002:span:2:84`** cannot be included: its input is outside the reduced,
deterministically selected exact subset. Its **two original judgments** are preserved
in the backup, the unchanged old progress, and the lossless migration report; they
are not reinterpreted or counted in the new sample. The maintainer explicitly
approved activating 55 inputs while retaining these excluded judgments in backup.

`data/phase6-pilot-55-migration/` contains the original progress, proposed progress,
report and checksummed manifest. `data/phase6-pilot-55-activation.json` records that
approval and initial hashes. Migration checks the entire frozen input, displayed
source/occurrence/costs and every linked detection payload, not just matching IDs
or offsets. Changed support is reported for review. Stale source edits or existing
destination progress prevent activation; activation never overwrites annotations.

## Validation and metrics

```powershell
uv run python -m tools.evaluation.pilot check --inputs-dir data/phase6-pilot-55-inputs --run-dir data/phase6-pilot-55 --progress data/phase6-pilot-55-progress.json
uv run python -m tools.evaluation.pilot metrics --inputs-dir data/phase6-pilot-55-inputs --run-dir data/phase6-pilot-55 --progress data/phase6-pilot-55-progress.json
```

Metrics retain the four groups separately, with input denominators **10 / 10 / 15 / 20**:

- Exact controlled recovery and boundary agreement out of ten, also showing
  configuration-eligible denominators.
- Modified controlled recovery out of ten, split into **4 edits / 4 omissions /
  2 combined**, with explicit ineligible and partial-match counts.
- General-prose alerts out of 15 paragraphs, separately from commentary alerts
  out of 20, including affected IDs, text spans and complete reference identities.
- Configuration gains/losses, added/removed spans and boundary differences within
  each group; controlled paired comparisons use common eligible examples.
- Review progress and, after maintainer review/approval, correspondence and boundary
  issues within each group's inspected pairs, separating uncertainty and pending work.

Outputs record input/capture/progress fingerprints. No commentary recall or
precision is inferred: commentary has no independent exhaustive textual gold spans.
Neither prose group supplies quotation-intent or false-positive labels. Checking a
representative source passage does not validate every returned reference. Reused,
narrow samples do not establish deployment-wide precision/recall or performance.
The tool withholds final human-reviewed scores until the maintainer's review.

Validation covers deterministic 55-input selection and unconditional commentary
inclusion, source-preserving evidence reuse, strict migration identities, excluded
answer retention, activation approval gates, stale-writer protection, save/resume,
Arabic offsets, four-group denominators and notebook callbacks. The notebook is
delivered with cleared outputs; fresh-kernel execution uses scratch copies of real
progress. Live browser visual inspection is not claimed. No production changes,
dependency changes, commits, pushes, releases or Phase 7 work are part of this update.

All **38 focused tests passed**, as did Ruff lint/format and strict package mypy.
Fresh-kernel notebook execution rendered all 55 input screens and verified each
group label, the three migrated pairs, automatic scratch saving and resume.
CLI validation accepted the real migrated state. Actual metric output verified
the four denominators and retained its explicit human-score withholding flag.
Every one of the 330 complete reused detection payloads was compared with its
saved parent; all original artifacts, judgments and backup checksums remained
unchanged. No test decisions were written to real progress.
