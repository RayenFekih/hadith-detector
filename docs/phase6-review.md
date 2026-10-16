# Phase 6: review the proposed annotations

This is the **optional full research review**. The required Phase 6 workflow is
now the [55-input technical pilot](phase6-pilot-55.md), which does not ask about
quotation intent and uses a separate progress file. Existing research annotations
are preserved and need not be completed.

This milestone prepares evidence, not gold labels or final quality scores. The
maintainer must review the CSV and explicitly approve the annotations before
precision, recall or confirmed false-positive conclusions are generated.

## What to open

### Interactive notebook (recommended)

From the repository terminal:

```powershell
uv sync --locked --group review
uv run --group review jupyter lab notebooks/phase6_research_review.ipynb
```

Run the setup cell, then the interface cell. In VS Code select the repository
`.venv` Python kernel. The notebook tools are in the repository-only `review`
dependency group; installed-library requirements are unchanged.

The interface reads `data/phase6-review-ready/review.csv` and saves to
`data/phase6-reviewed.csv`. The original export is never overwritten. On restart,
existing progress is validated and the first pending item is selected. No progress
file is created until you save. Use one active review session at a time; an
externally changed progress file is rejected rather than silently overwritten.

Choose **Accept**, **Correct**, **Reject**, or **Uncertain**. Correct reveals the
appropriate case/span classification and correction fields; blank correction
fields inherit the proposal. Notes are available for every decision. A corrected
span preview uses the original Python character offsets, including diacritics
and supplementary characters. Paragraph assessments highlight no individual span.

The main screen focuses on the original Arabic paragraph, the proposed label in
plain language, and **Is this proposed classification correct?** Whole-paragraph
reviews ask about all of the text; highlighted-passage reviews ask about just the
marked words in context. Each label includes a short explanation of what to check.
**Save & Next** sits directly below the decision area. A collapsed help section
and the notebook's quick help give three examples of decisions.

Use **Correct → Not intended** when a meaningful span is wrongly labelled as an
intended quotation. Use **Accept** if the proposal already says Not intended and
you agree. Reserve **Reject** for an unusable proposal that cannot be meaningfully
classified; repair recoverable boundaries with Correct. **Uncertain** records
that you cannot confidently decide. These are review instructions, not automatic
classification or confirmed false-positive conclusions.

Technical IDs, uncertainty flags, sources, configurations, provenance and traces
are collapsed under **Advanced Details**. Filters and jumping are in **Find or
filter review items**. Optional boundary/reference correction fields expand only
when needed; choosing Correct displays the plain-language classification menu.
After updating the notebook tools, restart the notebook kernel and run both cells
to load the revised interface. Existing saved CSV decisions resume unchanged.

**Save & Next** validates and atomically saves the current form before advancing;
**Save Progress** saves without advancing. **Previous** revisits navigation
history. **Skip** discards unsaved form changes and leaves the saved decision
untouched. Other navigation refuses unsaved edits. Filters default to pending;
use all to revisit decisions. Jump accepts a case or proposal ID and clears filters.
Uncertain counts toward reviewed progress but remains an unresolved judgment.

Expand **Supporting references** to load a configuration's saved evidence, then
choose a reference. All source occurrences, complete narration metadata and
alignment details are available in expandable sections. Lists are paginated in
groups of 100 and searchable by key; nothing is truncated. Configurations and
provenance start collapsed. A proposal without detector evidence shows its known
source identities and source context, explicitly distinguished from alignment
evidence. Supporting corpus matches do not establish intended quotation status.

To add a missed quotation, jump to its case, save any current edits, and expand
**Add a quotation**. Enter exclusive-end offsets, check the preview, choose a
classification and optional semicolon-separated references, then **Add & Save**.
These additions use the existing manual-row convention: `decision=correct`,
`manual:CASE:NUMBER` IDs and corrected fields. To express uncertainty on a manual
addition use its `uncertain` classification and notes; keep its correction
decision. Every original row remains present, with immutable fields unchanged.

Saves use a flushed temporary sibling followed by atomic replacement. If saving
fails, the previous file and in-memory decisions remain intact. The existing
`check-review` command below still validates the resulting CSV. No gold approval
or quality scores are produced by the notebook. See
[notebook validation](phase6-notebook-validation.md) for checks and limitations.

### CSV alternative

Open **`data/phase6-review-ready/review.csv`**. It is the single review workbook
interchange file: UTF-8 with BOM, comma-separated, with original Arabic text and
embedded newlines quoted correctly. In Excel use **Data > From Text/CSV**, select
UTF-8 and comma, and import columns as Text. Save your edits to a new UTF-8 CSV,
for example `data/phase6-reviewed.csv`; preserve the original export.

There are 136 cases: the original 96 corpus-derived candidates and 40 natural
paragraphs. Use `group` to filter them separately. `row_kind=case` assesses the
whole input; `row_kind=span` assesses a proposed quotation or detector-selected
span. Each paragraph has exactly one case row. Identical start/end spans across
configurations appear only once. Overlapping spans with different boundaries
remain separate proposals.

The first seven columns are editable. All `decision` cells are initially blank:

| Decision | Meaning |
| --- | --- |
| `accept` | Accept the proposed classification/boundaries as a draft review decision. |
| `correct` | Supply at least one correction in the adjacent correction fields. |
| `reject` | Reject this proposal; do not delete its row. |
| `uncertain` | Evidence or boundaries remain unresolved; explain in notes. |

For case rows, use `corrected_case_label`: `contains_quotation`, `quotation_free`,
`uncertain` or `out_of_corpus`. Assess the entire paragraph, not just the proposed
spans. For span rows, use `corrected_intent`: `intended_quotation`,
`not_intended_quotation`, `incidental_chain`, `quranic_wording`, `uncertain` or
`out_of_corpus`. A correct textual corpus match does not establish quotation
intent or authenticate a narration.

## Correcting or adding spans

`span_start`/`span_end` use exclusive-end **Python character offsets in `input_text`**,
not bytes, normalized words or JavaScript UTF-16. The `span_text` column is the
exact original slice. To correct it, fill both `corrected_start` and `corrected_end`
(including an explicit `0` if needed), set `decision=correct`, and explain any
boundary uncertainty. Do not edit the original text or original offset columns.

To add a quotation missed by every configuration:

1. Copy that case's **case row** and append it to the CSV.
2. Change `row_kind` to `span` and `proposal_id` to a unique value such as
   `manual:N0005:1`. Retain `case_id`, `group`, provenance and original input.
3. Fill `corrected_start`, `corrected_end` and `corrected_intent`; use
   `decision=correct`. If the classification remains unclear, use
   `corrected_intent=uncertain` and explain the uncertainty in notes.
4. Optionally provide confirmed corpus keys separated by semicolons in
   `corrected_references`; put external/out-of-corpus references in notes.

Blank correction cells inherit original proposals; notes alone do not change a
classification. Correction fields require `decision=correct`. An accepted
`uncertain` proposal remains uncertain; accepting it does not resolve ambiguity.

## Understanding the evidence

- `corpus_support` distinguishes detector support, a verified original source
  slice, and unestablished support. Source-slice support alone does not assert
  budget-valid matching across barriers.
- `supporting_references` previews up to 50 identities from the union across
  configurations, prioritizing the known source for imported proposals.
  `supporting_reference_count` gives the complete count and `reference_union_id`
  locates all identities in `reference-unions.jsonl`. `reference_preview_note`
  explicitly identifies any shortened display. Full records/occurrences remain
  untruncated in evidence. This is not exclusive attribution or a human-complete gold set.
- `configurations` lists configurations returning exactly that span.
  `config_costs` records each configuration's best `[errors, omissions]` pair.
- `evidence_ids` have `case_id:configuration:detection_index` form. Find the matching
  case/configuration row and zero-based detection index in `evidence.jsonl` to
  inspect complete original records, every occurrence and canonical traces.
- `source_context` contains the source narration for imported cases and the
  original extracted paragraph for natural cases. Natural `source_start/end`
  refer to the concatenated extracted page paragraphs archived in source snapshots.
- Input-first quotation suggestions and detector suggestions remain distinguishable
  through uncertainty flags and `default_comparison`. No reviewer decision has
  been supplied automatically.

Rare formula-like text cells are protected with a leading apostrophe and listed
in `csv_escaped_fields`. The checker reverses that representation before comparing
original text. Do not edit these protection flags or the protected proposal columns.

## Candidate unwanted alerts

`preparation-summary.json` separates the two evaluation groups and compares all
six settings against `(5,0,0)`. On paragraphs **proposed** as quotation-free it
lists affected paragraph IDs/counts, total candidate unwanted detections and
new/removed spans relative to defaults. `candidate-alerts.jsonl` includes every
offending original substring, offsets and supporting corpus identities.

These are provisional preparation counts, **not confirmed false positives or
precision/recall estimates**. Quotation-free status and usefulness require your
review. The 20 general paragraphs were not selected because the detector found
nothing; selection was frozen before any configuration run.

## Validate your edits

```sh
uv run python -m tools.evaluation check-review --dataset-dir data/phase6-inputs --run-dir data/phase6-review-ready --review-csv data/phase6-reviewed.csv
```

The checker validates structure, decisions, correction offsets, reference keys,
configuration membership and immutable inputs. It never approves gold or computes
quality conclusions, even if all decisions are populated. Keep unresolved cases
explicit. The eventual scoring stage must distinguish known supporting references
from independently established complete reference sets.

## Reproduce preparation offline

```sh
uv run python -m tools.evaluation freeze --legacy-csv others/hadith_eval_review/manual_labels.csv --source-dir data/phase6-frozen-sources --output-dir data/phase6-inputs-repeat
uv run python -m tools.evaluation replay --dataset-dir data/phase6-inputs --run-dir data/phase6-review-ready --output-dir data/phase6-review-repeat
```

`freeze` uses only local source snapshots and never loads a detector. `replay`
rebuilds the CSV, complete reference unions, alerts and count summary from captured complete results with
zero detector calls; it requires byte-identical outputs. New output directories
are required; no existing review or research file is overwritten.

To make a new capture rather than replay saved results:

```sh
uv run python -m tools.evaluation run --dataset-dir data/phase6-inputs --index-dir data/runtime-index-v2-a --output-dir data/phase6-new-capture
```

This runs only the six approved configurations, not historical benchmarks. Its
manifest records corpus/index checksums, inputs, configuration, code/lock hashes
and Python/Unicode/dependency versions. Complete results retain every source field,
identity and occurrence. Failed captures leave no accepted partial output.

## Source selection and rights

Natural text comes from the first five eligible paragraphs on each of eight
pages listed in `tools/evaluation/natural-source-lock.json`: four chapters of
Ibn Rajab's *Jami al-Ulum wa-al-Hikam* on Arabic Wikisource, and Arabic Wikipedia
articles on the water cycle, photosynthesis, the Solar System and printing.
Eligibility is 20-260 whitespace words and 120-2200 characters; quotation-rich
selection additionally requires a Prophet/Messenger mention. This is an enriched
small pilot, not a representative sample of production traffic. The four commentary
chapters are related material, not twenty independent source documents.

Pinned revision URLs, history links, checksums, paragraph indices and extraction
boundaries are recorded per page. API HTML snapshots are authoritative for offline
rebuilds. Extraction removes tags and reference superscripts and turns `<br>` into
LF; extracted text is subsequently unchanged. No matching normalization is used
to prepare inputs. Draft spans are recorded before detection and guarded by input
hashes; they do not claim scholarly authentication.

Wikimedia text follows [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
and the [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use).
Natural-source text retains those terms; our added natural-text draft annotations
are also offered under CC BY-SA 4.0. Attribution appears in the CSV and source lock.
No images are collected. Corpus-derived records retain the separately approved
[QuranLab/upstream provenance](../data/README.md). The project MIT license applies
to code, not all evaluation data.

Remote refetching can use `fetch --selection tools/evaluation/natural-source-lock.json`
and a new output directory. A different rendering at the same page revision is
rejected by checksum: templates/renderers can change, so retain archived snapshots.
Generated data and captures remain ignored; code, small manifests, draft-offset
metadata and reports can be committed only when requested.
