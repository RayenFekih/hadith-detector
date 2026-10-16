# Historical Phase 6: original 50-input pilot

Status: preparation is implemented and ready for maintainer review. Human-reviewed
scores remain withheld. This pilot asks about textual correspondence and boundaries,
not authenticity or scholarly quotation intent.

## Open and review

From the repository terminal:

```powershell
uv run --group review jupyter lab notebooks/phase6_review_50.ipynb
```

If notebook tools are not installed, first run `uv sync --locked --group review`.
In VS Code select the repository `.venv` kernel. Restart an older notebook kernel,
then run the setup cell and the review cell. The notebook loads prepared evidence;
it does not initialize a detector, rebuild resources, download data or rerun matching.

Each screen contains one original Arabic input, highlighted detections and all its
relevant passage pairs. Compare the matched input with the original corpus passage
beside it. The screen states both the allowed edits/omissions for the shown support
and the actual changes used; changed word pairs are listed, and omitted source words
are pink. Source characters are never rewritten. Diacritics and equivalent Arabic
letter forms can differ without consuming character edits.

For every pair answer:

- **Correspondence: Yes / No / Uncertain.** Do the texts correspond within the stated
  changes?
- **Boundaries: Yes / Correct / Uncertain.** Are the input and source boundaries
  appropriate? Correct opens an editor with original-character offset previews.

Valid choices save automatically to **`data/phase6-pilot-progress.json`**. Notes save
when you leave the notes field or use a navigation button. Save & Next moves on after
all pairs on that input are answered. Skip saves valid partial answers and moves on;
Previous and All inputs let you revisit decisions. Restart and run both cells to
resume at the first unfinished input. Uncertain is reviewed but unresolved.

Selecting Correct saves that choice as an unfinished draft until at least one
valid boundary changes. Offsets count Python string characters, with exclusive ends;
source offsets refer to the complete original narration. Invalid edits do not replace
the last valid saved state, and navigation reports the problem until corrected.
Saves flush a temporary sibling before atomic replacement. Use one active review
session; stale external edits are detected rather than silently overwritten.

Advanced evidence is optional: it retains every configuration's full records,
identities, source occurrences, costs and traces. The displayed representative is
identified explicitly; you do not review each occurrence or configuration again.

## Exact review workload

| Selected inputs | Unique displayed/detected pairs | Correspondence choices | Boundary choices |
| --- | ---: | ---: | ---: |
| 20 exact | 20 | 20 | 20 |
| 15 controlled fuzzy | 40 | 40 | 40 |
| 15 natural candidates | 2 | 2 | 2 |
| **50 total** | **62** | **62** | **62** |

That is **124 technical judgments**, plus **13 simple zero-alert acknowledgements**.
There are 50 input screens, with at most five pairs on a screen. A zero-alert screen
only needs Save & Next; it does not certify that the paragraph contains no quotation.
Different span boundaries remain separate pairs, while identical input spans across
settings are shown once. No complete expected target was absent from all settings;
the tooling nevertheless retains a separate expected-target check if that occurs
in a future reproducible run. Partial recoveries under individual settings remain
in the evidence and controlled measurements.

## Selection and preservation

The approved [plan](phase6-pilot-plan-50.md) freezes 20 existing Phase 6 source excerpts,
15 previously frozen Phase 4 mutations (6 edit, 6 omission, 3 combined), and 15 existing
Phase 6 general-Arabic paragraphs. It uses input-only eligibility and seeded hash
ranking, with five exact examples per historical stratum and natural-source quotas
4/4/4/3. IDs are recorded in [the compact selection lock](../tools/evaluation/pilot-selection-50.json).

Three quote-marked inputs (`S0004`, `S0057`, `S0059`) failed the declared five-aligned-word
input eligibility rule before selection. No other input-integrity exclusions occurred.
No difficult or failed outcome was replaced. All 50 selected raw input texts are distinct.
The 35 positive cases carry 17 Bukhari and 18 Muslim source associations.
Natural sources are four related convenience samples, not representative deployment text.

The selection was published before capture read outcomes. Independent input builds
are byte-identical. The corpus is the same pinned 14,940-record corpus used previously.
For the selected 35 Phase 6 inputs, **210 existing case/configuration outputs** were
reused with all detection fields unchanged. The 15 fuzzy inputs needed **90 missing
case/configuration captures**. Their 15 applicable saved-oracle results agreed exactly;
the oracle algorithm and historical benchmarks were not rerun.

Frozen inputs: `data/phase6-pilot-inputs/` (`cases.jsonl`, `selection.json`, `manifest.json`).
Prepared review: `data/phase6-pilot/` (`evidence.jsonl`, `review.json`, `manifest.json`).
These generated files remain ignored. The complete pilot evidence is 2,244,688 bytes.
The capture manifest distinguishes historical evidence from new selected fuzzy calls.

| Artifact | SHA-256 |
| --- | --- |
| Frozen input manifest | `adcd9eded857050ce08cf04c1361f1e7cb8cf1fcd5b5a30dfa9110ddf8f7f641` |
| Capture manifest | `3ccc7d74f4c64aa4950a8eb506edddacbdb9bc30a6a92d02c3589b40cd9afbc0` |

The original 136-input dataset, 453-row CSV, complete evidence and previous annotations
are unchanged. The [original research notebook](../notebooks/phase6_research_review.ipynb)
and its [CSV review guide](phase6-review.md) remain optional. Technical progress is a
separate version-1 JSON record: it links input/capture manifest hashes and contains
two answers, optional corrected offsets and notes for each stable pair ID, plus
zero-alert acknowledgements. It never imports or reinterprets intent decisions.
The original CSV schema and `tools.evaluation check-review` remain unchanged.

## Commands and reproducibility

To rebuild, use new output directories; existing directories are never overwritten.
Freeze completes separately before capture is allowed:

```powershell
uv run python -m tools.evaluation.pilot freeze --index-dir data/runtime-index-v2-a --output-dir data/phase6-pilot-inputs-new
uv run python -m tools.evaluation.pilot capture --inputs-dir data/phase6-pilot-inputs-new --index-dir data/runtime-index-v2-a --output-dir data/phase6-pilot-new
```

Capture reads the saved parent evidence and only executes missing selected fuzzy
configurations. It verifies parent checksums, corpus identity and applicable saved
oracle results. An outcome disagreement fails capture, without substituting another
case. On managed Windows filesystems that prohibit directory renames, files are
published with the manifest last; incomplete directories are not accepted.

Validate saved pilot progress separately from the original CSV:

```powershell
uv run python -m tools.evaluation.pilot check --inputs-dir data/phase6-pilot-inputs --run-dir data/phase6-pilot --progress data/phase6-pilot-progress.json
uv run python -m tools.evaluation.pilot metrics --inputs-dir data/phase6-pilot-inputs --run-dir data/phase6-pilot --progress data/phase6-pilot-progress.json
```

With no progress file yet, these commands report pending judgments without creating
human decisions. `metrics` produces controlled/descriptive measurements and progress
counts only; it explicitly withholds human-reviewed error scores. It never approves
labels or claims precision/recall.

## Measurements after review

Report exact known-source target recovery out of 20, fuzzy recovery out of 15
(split 6/6/3), and original-boundary agreement. Use both all-input yields and
construction-eligible denominators; show ineligible counts. Do not count a partial
match as a full recovery. Canonical alternative internal alignments of repeated
words do not invalidate recovery of the same complete source occurrence.

Compare all six settings with `(5,0,0)`: gained/lost full targets, added/removed spans
and boundary variants, including common-eligible paired comparisons. Settings and
defaults remain unchanged. Three exact inputs have fewer than seven normalized words;
the seven-word configuration is not expected to recover them.

Natural alerts are descriptive: affected paragraphs out of 15, detection counts,
original spans and references. After review and approval, count correspondence
issues among decisively reviewed displayed pairs and boundary corrections among
reviewed spans, keeping pending/uncertain judgments separate. Show concrete examples.
Do not attribute one representative's correctness to every retained source occurrence,
or equate a bad displayed reference with an invalid detection if other support exists.

This small reused sample does not establish quotation-intent precision, natural-text
recall, false-positive rates, authenticity or deployment-wide performance. No new
latency, memory, dependency or compatibility benchmark is performed; reuse
[Phase 3B](phase3b-validation.md), [Phase 4B](phase4b-validation.md),
[MARISA production](marisa-production.md) and [Phase 5B](phase5b-validation.md).

## Validation and stop point

**32 focused tests passed**, covering deterministic input-only selection,
deduplication, full occurrence preservation, all answer types, incomplete corrections,
strict offsets, atomic failure recovery, stale writers, resuming, configuration
denominators, missing-target fixtures, safe Arabic/emoji/symbol rendering and the
unchanged research workflow. Both selection builds and the saved-evidence review
projection reproduced byte-for-byte. All 210 reused output payloads were compared
to their originals without changes.

The updated notebook executed in a fresh local Jupyter kernel. All 50 screens rendered;
automatic saving, restoration and CLI validation passed using scratch-only decisions.
Every original dataset/review artifact checksum remained unchanged. No real human pilot
progress was created by these checks. Live browser visual testing is not claimed.

Stop for maintainer review. No human-reviewed scores are finalized, and no production
code, matching settings, resources, dependencies or public APIs change for this pilot.
No commits, pushes, releases or Phase 7 work are authorized here.
