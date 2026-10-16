# Phase 6 technical pilot: current approved composition

The maintainer approved expanding realistic religious content to exactly **55
existing frozen inputs**. Implementation is ready for technical review; see the
[handoff](phase6-pilot-55.md). The [original approved 50-input plan](phase6-pilot-plan-50.md)
is retained as historical evidence.

## Frozen selection

- 10 exact source excerpts: unchanged input-only eligibility and hash ranking,
  with stratum quotas 3/3/2/2 in the existing stratum order.
- 10 existing Phase 4 mutations: 4 character-edit, 4 omission and 2 combined,
  using the same hash ranking and eligible pools.
- The same 15 general Arabic paragraphs, retaining source quotas 4/4/4/3.
- All 20 original frozen religious commentary paragraphs, regardless of matching
  outcomes or provisional quotation labels.

No new examples, output-based substitutions or corpus modifications. Selection is
frozen reproducibly before projecting saved outputs. Existing detection evidence
is reused wherever input and source fingerprints agree; this build required zero
new detector calls. All identities, occurrences, metadata and offsets are retained.

## Review and reporting

One screen per input, with complete Arabic text, highlighted detections and original
corpus passages. Deduplicate identical input spans across settings. Retain differing
boundaries and all evidence; the four input groups are clearly identified. Ask only
Yes/No/Uncertain for textual correspondence and Yes/Correct/Uncertain for boundaries.
Retain automatic saving, valid correction previews and pending-input resume.

Report controlled recovery for exact (10) and modified (10; split 4/4/2) inputs.
Report general-prose (15) and religious-commentary (20) alerts descriptively and
separately, without inferring precision, false positives or natural-text recall.
Compare configurations with unchanged defaults using explicit eligible denominators.
Keep inspected textual/boundary issues separate by group, uncertainty and completion.
Final human-reviewed scores await maintainer review; deployment-wide claims remain
outside scope. Reuse prior oracle, performance, memory and compatibility evidence.

## Annotation preservation and activation

Keep the original 50-input artifacts and progress intact and make a full backup.
Copy judgments only when the frozen input, displayed passage/occurrence and complete
linked evidence are identical. Preserve and report any excluded or changed judgments;
require explicit approval before activating a revision that cannot migrate them.
Do not overwrite an existing destination progress file or reinterpret intent labels.

The maintainer explicitly approved activating the separate 55-input progress while
retaining S0002's two excluded judgments in backup and the migration report. Three
unchanged reviewed pairs migrated verbatim. All research and original pilot artifacts
remain available. No production changes, dependency changes, commits, pushes,
releases or Phase 7 work are authorized.
