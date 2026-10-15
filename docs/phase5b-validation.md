# Phase 5B review report

The [approved plan](phase5b-plan.md) is implemented. Instance and convenience
`annotate()` return escaped HTML fragments with deterministic fixed `<mark>`
elements. See the [HTML guide](html-annotation.md) for signatures and markup.
No commit, push, release or Phase 6 work is part of this milestone.

## Behavior and compatibility

Annotation calls the existing detector once. It highlights original input slices
without normalization, spelling repair, source substitution, repeated matching
or another overlap policy. Exact/fuzzy selection, eligible tails, references,
every source occurrence and canonical traces remain detection's responsibility.
Offset/cost/reference-count attributes are numeric; text and quotes are escaped.
There are no links, tooltips, embedded metadata, arbitrary attributes, scripts,
stylesheets or direction wrappers.

Decoded fragment text reproduces original Arabic, marks, symbols, controls and
whitespace. CR is encoded as `&#13;`. Annotation rejects NUL/lone surrogates
because HTML cannot represent them losslessly; detection accepts the same
strings as before. Offsets remain exclusive-end Python string indices, not HTML
positions or JavaScript UTF-16 indices. Consumers control presentation and can
apply `white-space: pre-wrap` to display original spacing and line breaks.

Configuration inheritance, explicit-zero overrides, directory requirements,
single-entry caching and resource integrity remain unchanged. The instance lock
covers annotation through rendering; same-instance operations are sequential.
The cache lock is released before annotation and cache clearing does not interrupt
in-flight work. Defensive renderer checks reject invalid/overlapping spans.

All pre-existing detector method bodies are AST-identical to the preceding
implementation. Fuzzy matching, resource validation/loading, MARISA v2, RapidFuzz,
normalization v1, result models, configuration, dependencies and source data are
unchanged. Annotation uses only Python's standard library.

## Verification

The final complete local regression suite passed **212 tests**, including
retained fuzzy tails and multiple occurrences within one reference.
All **12** optional library-survey regression tests passed in their isolated
environment. Updated examples ran successfully against the complete corpus.

Offline saved-oracle validation passed **168 exact**, **168 fuzzy** and **39
representative** cases. The public annotation method was also called on all
**375** cases; independently parsed fragments reproduced original text, match
slices, input offsets, best costs and complete reference counts. All **14,940**
source records retained their original fields through lookup and restoration.
This is algorithmic evidence, not independent Hadith authentication.

The supported-version matrix runs API, annotation, normalization, exact/fuzzy
and corruption tests, plus clean offline wheel probes outside the checkout.
Each run includes at least **147** runtime tests; the two final review fixtures
are additionally checked on every supported Python/platform combination.

| Python | Windows 11 | Linux/WSL Ubuntu 22.04 |
| --- | --- | --- |
| 3.11.15 | Passed | Passed |
| 3.12.13 | Passed | Passed |
| 3.13.14 | Passed | Passed |
| 3.14.6 | Passed | Passed |

Wheel/sdist build and metadata checks passed, including rebuilding a wheel from
the sdist without Git and clean offline installation of both wheels. Installed
library probes verify annotation/detection without network access, only read
prebuilt native tries, reject v1 and create no files in their working directory.
Runtime dependencies remain RapidFuzz and MARISA only; corpus/index/preparation
dependencies remain excluded from distributions. Ruff, formatting, strict mypy
and Twine checks passed.

Generated evidence remains ignored in `data/phase5b-oracles.json`,
`data/phase5b-installed-*.json` and `.cache/phase5b-*.log`.
The preserved index manifest SHA-256 is
`a34ebdd099389594b039a4ac55e667081110c2c192f43eee08095fe1f7d5dcbd`.

## Review boundary

Annotation handles plain text, not existing HTML document sanitization. It emits
no reference UI; use `detect()` for full metadata. Shared-instance operations are
sequential. No new performance claims or bundled resources are introduced.
Phase 5B is complete for review. Phase 6 has not begun.
