# Phase 6 notebook validation

## Simplified interface revision

The reviewer-facing screen now prioritizes the Arabic paragraph, a plain-language
proposed label with a short explanation, and a direct classification question.
Four decision controls precede Save & Next; sources and technical evidence are
inside a collapsed Advanced Details section. Paragraph and highlighted-passage
reviews have distinct instructions. Three help examples explain acceptance,
correction of a meaningful false alarm to Not intended, and rejection versus
uncertainty. CSV values and evaluation logic are unchanged.

Focused UI/preparation tests: **24 passed**, including layout order, plain labels,
no preselected decision, collapsed details, correction semantics, uncertainty notes,
save/resume, atomic persistence, manual additions and existing CSV validation.
The revised notebook executed successfully in a fresh local kernel against all
453 original rows, using a scratch progress path. The existing `check-review`
accepted its saved CSV, and checksums confirmed the original export and any
existing human progress file were unchanged. No decisions were added to real
annotations. The notebook is delivered with cleared outputs. Live browser visual
inspection is not claimed.

This is a usability addition to the existing draft review, not a new evaluation
or approval of annotations. Production code, resources and runtime requirements
are unchanged.

## Evidence

- Focused notebook and preparation tests: **22 passed** on local Python 3.14.
  Tests cover decisions, corrections including offset zero, resume, immutable
  fields, all original rows, manual additions, filters, navigation, progress,
  complete repeated source occurrences, bounded evidence caching, interruption
  before replacement, external edits, Arabic/emoji/combining-mark slicing,
  safe HTML escaping and widget callbacks.
- The real export loaded **453 rows, all pending**, from 136 cases. Its checksum
  remained `3c0b2361c4efdcd4730286765397cfe3e0c8789d1b7fe12886afcaedbaf10471`.
- A separate scratch file exercised accept, correct, reject and uncertain plus a
  manually added span. Reopening restored every row and correction. The existing
  CLI accepted **454 rows**: accept 1, reject 1, uncertain 1, correct 2, pending
  449, with `status=draft_only` and `gold_approved=False`.
- The notebook executed successfully in a local ipykernel, using the real frozen
  inputs and a scratch progress path. Widget construction and saved widget state
  completed; notebook schema validation passed. The delivered notebook retains
  two code cells, with outputs and execution counts cleared.
- Ruff lint/format and strict package mypy passed. Notebook dependencies are
  isolated in `review`; runtime requirements remain RapidFuzz and marisa-trie.
- Wheel/sdist builds passed. Wheel metadata retains exactly the existing two
  runtime requirements; notebook tools, frozen data, review outputs and caches
  are excluded from the wheel. The sdist excludes notebooks and generated data.
  The updated lock passes its offline consistency check.

Scratch decisions were not written to `data/phase6-reviewed.csv`. They are test
data only and must not be used as annotations or quality evidence.

## Limits

An authenticated local JupyterLab server returned HTTP 200 for its frontend and
was shut down after testing. Browser automation
approval timed out. Kernel execution and widget callbacks were tested; a live
browser visual inspection and browser button round trip were **not verified**.
The RTL rendering and exact highlighted slices are covered by HTML tests.
VS Code was not separately exercised.

Use one active notebook review session. The file-change check detects stale
sessions, but is not a concurrent-editor merge or locking protocol. Resuming
selects the first pending row; skip history and filter choices are session-only.
Saved uncertain decisions remain unresolved. Manual additions follow the
existing correction-only CSV convention.

Historical detector benchmarks and compatibility matrices were not rerun for
this UI-only change. Final gold labels, precision, recall and confirmed false
positives remain pending human review and explicit approval.
