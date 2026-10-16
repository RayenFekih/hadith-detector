# Phase 6 revised plan: a small technical quality pilot

Status: approved by the maintainer and implemented for review. See the
[pilot handoff](phase6-pilot.md) for frozen artifacts, exact workload and validation.
Human-reviewed scores remain withheld. Phase 7 remains outside scope.

## Purpose and retained research

Check a small sample of textual correspondence and matching boundaries. Do not
ask the reviewer to authenticate Hadith or infer scholarly quotation intent.
Reuse the completed algorithm, oracle, performance, memory, compatibility,
serialization, concurrency and annotation evaluations as historical evidence.
They do not establish deployment-wide precision or recall.

Preserve the complete 136-input dataset, 453-row review exports, saved decisions,
complete evidence, reference unions, provenance and checksums. These become
optional research material, not a required annotation backlog. Do not reinterpret
existing intent decisions as technical correspondence labels.

## Fifty frozen inputs, selected without detector outcomes

Selection uses input/source metadata only. Within each stratum sort by
`SHA256(UTF8("phase6-pilot-v1|42|" + original_case_id))`, breaking ties by the
original ID, then take the required count. Record the entire eligibility rule,
eligible IDs, selected IDs, input hashes and parent artifact hashes before
opening results for the selected cases. Never replace a case because it fails,
has many references, or is inconvenient to review. Report any input-integrity
problem explicitly rather than silently replacing it after observing outputs.

| Group | Count | Existing material and selection |
| --- | ---: | --- |
| Exact positives | 20 | From the 96 frozen Phase 6 corpus-derived inputs: five each from quote-marked, middle-window, opening-window and long-narration strata. Require a verified source substring, at least five aligned words, one matching segment and legal whole-symbol endpoints. These are input-only eligibility checks. |
| Controlled fuzzy positives | 15 | Reuse the authoritative saved Phase 4 suite: six character-edit, six omission and three combined cases, selected from actual recorded mutations. Require minimum five, a known source/start, at least five input words, budgets no greater than one edit and one omission, and valid source construction. |
| Natural negative candidates | 15 | From the 20 frozen Phase 6 general-Arabic paragraphs, not the commentary subset. Sort their four pinned source URLs and take 4, 4, 4 and 3 paragraphs respectively using the same within-source hash ranking. Do not consult alerts or proposed quotation labels to select them. |

Important: all 96 Phase 6 source-derived inputs are unchanged source excerpts;
there are no controlled fuzzy mutations in that dataset. Therefore this is a
combined pilot reusing **35 Phase 6 inputs and 15 existing Phase 4 inputs**, not
a literal 50-case subset of Phase 6 alone. This avoids generating new queries.
If all 50 must come from Phase 6 inputs, the alternative requires creating 15
controlled variants; that is a separate choice, not assumed here.

The authoritative fuzzy file is `data/phase4-final/queries.json`, SHA-256
`55edff14c522104e15eb2a2ea93052aa1ea0ce35ad07c40c9438c9e0ce2f4aca`.
Read-only inspection found 10 eligible edit candidates, seven omission candidates
and three combined candidates under the recorded category/mutation/budget rules.
The combined subset consequently includes all three, with no selection by success.
Source-span and whole-symbol integrity still need checking before freezing IDs.
All suites reference the same pinned corpus fingerprint. Preserve the original
Phase 4 IDs, mutations and source hints alongside the Phase 6 case identities.

Report collection distribution, input lengths, eligibility exclusions and actual
counts. Selection is reproducible, not representative random sampling of users.
The four natural sources are related convenience samples; do not treat them as
15 independently sampled deployment situations.

## Evidence reuse and configuration comparison

Keep the six existing configurations: `(3,0,0)`, **`(5,0,0)`**, `(7,0,0)`,
`(5,1,0)`, `(5,0,1)` and `(5,1,1)`. Never change production defaults automatically.

Reuse all six saved Phase 6 outputs for the 35 selected Phase 6 cases. Reuse the
saved Phase 4 query construction, source associations, full oracle traces and
available compatible detection outputs for the 15 fuzzy cases. A missing
case/configuration output may be captured once with the current detector after
approval: at most 90 small case/configuration calls, not another benchmark suite.
Do not assume a historical Phase 4 result used one of these six configurations;
check actual parameters and fingerprints before reusing it. Label historical and
new capture versions separately, even where previous regression evidence agrees.

Derive the intended target and originating source occurrence from the frozen
source extraction or recorded mutation construction, not from successful detector
outputs. Preserve original source text, identities, all returned occurrences,
costs, traces and offsets. Use the existing saved oracle only where its query and
parameters apply; diagnose discrepancies specifically rather than rerunning it
for every configuration.

## Small review experience

One input card, visited once, with the original Arabic text and its detections.
Deduplicate identical input spans across configurations. Different boundaries
remain distinct; do not merge them into a span the detector never returned.
Keep expected positive boundaries visible even when every configuration misses
them. Show the default prominently, with other configurations' distinct spans
as additional suggestions within the same input, not separate review sessions.

For each relevant span show the corresponding original corpus passage, highlighting
source alignment and internal omissions without repairing or replacing its text.
Use the known originating occurrence for a positive when it supports that result;
otherwise choose the first supporting reference in deterministic corpus order and
its earliest occurrence. Make the choice explicit. Other references, occurrences
and alignment profiles stay expandable, complete and unchanged.

The reviewer checks only:

1. Does the highlighted input correspond textually to the displayed source passage,
   allowing the stated edits and omissions? Yes / No / Uncertain.
2. Are the input and source boundaries appropriate? Yes / Correct / Uncertain.

Allow notes and identification of a missing known target. No separate paragraph
intent assessment, no repeated review per configuration or occurrence, and no
authenticity question. Zero-alert natural inputs require only an acknowledgement,
not a claim that they contain no Hadith. Report the actual number of unique spans
and displayed input/source pairs; 50 inputs need not mean exactly 50 span judgments.

Retain atomic progress saves, resume, exact Python offsets and escaped RTL rendering.
Technical pilot decisions must be saved separately from the existing intent CSV;
do not change that CSV's schema, overwrite it, or coerce its decisions into a new
meaning. Define the small technical-review record during implementation, with
stable links to original case/proposal/evidence IDs. Preserve optional access to
the full research review. A pilot validator must explicitly distinguish the two
review types; the old `check-review` remains valid for the original CSV only.

## Exactly which metrics can be reported

Always show counts and denominators, separately by group and fuzzy mutation type.
No pooled exact/fuzzy/natural headline score. Final reviewed-error counts wait for
review completion; unresolved items remain visible and are not counted as correct.

| Metric | Definition and permitted interpretation |
| --- | --- |
| Exact known-target recovery | Number of the 20 exact positives with a returned passage covering the complete expected normalized-word target and the originating source identity/occurrence, divided by the configuration-eligible positives. Original character boundaries are checked separately. This measures controlled sample success, not deployment recall. |
| Fuzzy known-target recovery | The same measure for 15 controlled positives, separately for 6 edits, 6 omissions and 3 combined cases. State whether the recorded source construction fits the configuration's word minimum and budgets. Missing full targets and partial recoveries remain explicit; any short match is not a full-target success. |
| Positive boundary agreement | Exact agreement with the frozen expected input/source character boundaries, with reviewed corrections reported separately. Define expected spans from mapped tokens, excluding surrounding punctuation/whitespace that is not part of those token spans. Do not require a match to include unrelated paragraph text. |
| Configuration differences | Paired full-target gains/losses versus `(5,0,0)`, plus added/removed spans and changed boundaries. Report all 35 positives as an all-input recovery yield, and eligible-only rates with ineligible counts. Compare rates on common eligible cases; do not call a below-minimum or over-budget construction a detector defect. A smaller budget can still find a legitimate alternative support. |
| Natural-text alerts | For each configuration, affected paragraphs `k/15`, total detections, deduplicated span count and differences from defaults, with original offending/alert text and source references. These are alerts, not false positives. Zero alerts do not prove absence of quotations. |
| Reviewed correspondence issues | Number of displayed input/source pairs judged textually incorrect divided by decisively reviewed displayed pairs, alongside the full Yes/No/Uncertain/pending counts. This is a sample inspection result, not precision for every returned reference or detection. |
| Reviewed boundary issues | Number of reviewed unique spans whose displayed boundaries need correction, divided by decisively reviewed spans, with uncertainty and pending counts and concrete examples. Keep correspondence and boundary issues separate; a span can have both. |

A bad displayed reference is not automatically a false detection: another retained
reference may support the span. Conversely, checking one displayed occurrence does
not validate every occurrence. Do not extrapolate representative-passage review
to reference completeness; the previous exhaustive oracle evaluations address that
algorithmic property. Report additional checked evidence only if actually reviewed.

Do not calculate quotation-intent precision, false-positive rates or natural-text
recall from these labels. Stronger claims would require appropriate independent
labels and sampling, outside this pilot. No deployment-wide precision/recall,
significance claims, universal error bounds or automatic setting recommendation.
The sample is small, corpus-derived positives are artificial, combined cases are
only three, natural sources are narrow, and existing fuzzy cases are reused
regression material rather than a new held-out test.

## Implementation and approval boundaries

Approved implementation stages:

1. Validate parent artifacts; freeze the 50-case selection, source-derived targets,
   hashes and selection rules before examining selected results.
2. Project saved evidence; capture only missing fuzzy/configuration combinations.
3. Simplify the notebook for input/source correspondence and a separate, small
   technical-review progress file. Test deduplication, slices, persistence and
   scoring denominators on fixtures; preserve all original artifacts and annotations.
4. Present the pilot for technical review. After review, report controlled recovery,
   configuration differences, descriptive natural alerts and reviewed issues with
   unresolved counts and limitations. No final human-reviewed findings before review.

Reference [Phase 3B](phase3b-validation.md), [Phase 4B](phase4b-validation.md),
[MARISA production](marisa-production.md) and [Phase 5B](phase5b-validation.md)
for completed correctness, performance and compatibility evidence; no reruns or
optimization work are part of this pilot.

The maintainer approved this composition (including reuse of 15 Phase 4 queries),
technical-only review, separate pilot progress and metric definitions. The review
handoff is the current stop point. Production code, normalization, resources,
dependencies, public APIs, commits, pushes, releases and Phase 7 remain outside scope.
