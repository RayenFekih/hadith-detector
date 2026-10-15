# Phase 5B proposal: safe HTML annotation

Status: approved by the maintainer, including all three proposed decisions.
Implementation is authorized for Phase 5B only. Phase 5A is accepted. No commit,
push, release, corpus bundling or later phase is authorized.

## Scope and interfaces

Add instance and convenience annotation with the same detection settings:

```python
detector.annotate(
    text, *, format="html", min_match_words=None,
    max_errors=None, max_missing_words=None,
)
annotate(
    text, *, index_dir, format="html", config=None,
    min_match_words=None, max_errors=None, max_missing_words=None,
)
```

Recommended return value: an HTML fragment string. Only `format="html"` is
supported; no placeholder formats, result-model changes or rendering dependency.
Explicit local resources remain required. Configuration precedence, explicit-zero
overrides, single-entry convenience caching and sequential instance calls follow
Phase 5A. The convenience function releases the cache lock before annotation.

Annotation calls the existing detector once. A private renderer consumes its
selected detections without normalizing, retrieving, aligning or ranking again.
The instance reentrant lock covers the operation; HTML construction can safely
call detection while holding that lock. No asynchronous or parallel API is added.

## Original text and deterministic spans

Treat input as plain text, including any apparent HTML. Slice the original input
using the existing exclusive-end Python offsets. Escape each unmatched gap and
matched slice, wrapping each selected passage once. Do not substitute source
text, remove diacritics, repair spelling, insert omitted source words, normalize
whitespace or reorder text. Fuzzy matches highlight the original input passage.

Overlaps are resolved only by existing detection: matched words, span length,
costs and start position, retaining eligible tails. Annotation does not introduce
another overlap policy. Adjacent matches remain separate, without added text.
Rendering validates span bounds, original slices, ascending order and non-overlap;
invalid internal results raise `ValueError` rather than producing malformed output.
There is no public API accepting externally supplied detections in this milestone.

Decoded fragment text must reproduce the original input. HTML-output character
positions differ from input offsets because of tags and entities; exposed offsets
always refer to the original Python string. Symbol expansions remain whole at
endpoints, with their existing shared spans and traces unchanged.

## Proposed markup and escaping

Use fixed `<mark>` elements with fixed class names and numeric attributes:

```html
<mark class="hadith-match" data-match-index="0" data-start="12" data-end="47"
      data-errors="1" data-missing-words="0" data-reference-count="2">...</mark>
```

Attribute order and numbering follow input order and are deterministic. Costs
are the passage's best supporting pair, not claims that every reference has
those costs. Exact and fuzzy passages use the same markup structure. No
per-character edit rendering or inferred source text is introduced.

Use standard-library HTML escaping, including quotes, for every input slice.
Keep markup names fixed; expose no arbitrary attributes, templates or HTML
callbacks. Literal tags, scripts and existing entity-like text remain escaped
plain text. Embed no executable JavaScript, inline event handlers, raw JSON,
source URLs or source metadata. Full references remain available through
`detect()`; annotation does not cap or alter them.

Recommended output is a fragment without a document shell, stylesheet, direction
override or automatic reference links. Consumers can style `.hadith-match` and
use `white-space: pre-wrap` on their containing element to display original
spacing/newlines. Document that annotation escapes plain text rather than
sanitizing an existing HTML document, and that input offsets are Python string
indices rather than JavaScript UTF-16 indices.

Encode carriage returns as numeric character references after escaping so HTML
parsing does not silently normalize them. Proposed annotation-only restriction:
reject NUL and lone surrogate code points with `ValueError`, since HTML cannot
represent them losslessly. Detection continues to accept the same strings as
before; this does not change normalization or matching behavior.

## Verification and deliverables

- Exact, fuzzy and combined-budget annotation agrees with unchanged detection,
  including complete references, canonical traces and all source occurrences.
- Original Arabic, combining marks, tatweel, controls, symbols, supplementary
  characters, punctuation, barriers, CR/LF, tabs and whitespace survive decoded
  text round trips. Escaped tags, ampersands, quotes and entity-like strings
  cannot produce injected elements or attributes.
- Empty/no-match input, multiple/adjacent passages, overlap ranking and retained
  tails behave deterministically. Parsed marks correspond one-to-one with
  detection offsets and exact original substrings.
- Settings inherit/override as before; invalid inputs/formats/settings fail
  clearly. Convenience/instance results agree, cache reuse works, and concurrent
  detect/annotate/lookup calls serialize without deadlock or stale configuration.
- The renderer's defensive checks reject invalid bounds, slices and overlaps.
  No public external-result rendering API is added merely to exercise these tests.
- Run full regression and saved exact/fuzzy/representative corpus comparisons;
  add annotation text/span checks without reinterpreting oracle results.
- Retain Python 3.11-3.14 Linux and Windows compatibility, offline clean-wheel
  detection/annotation, wheel/sdist metadata/content checks, Ruff and strict mypy.
  No production dependencies, MARISA resources or artifact versions change.

Update the API guide, README, roadmap, changelog and runnable examples with
working annotation examples, CSS guidance, escaping limits and verification
evidence. Stop for review after Phase 5B; Phase 6 requires separate authorization.

Proposed commits, only if requested:

1. `feat: add safe deterministic HTML annotation`
2. `test: verify annotation escaping and detection parity`
3. `docs: document HTML annotation and validation`

## Decisions requested

1. Approve a fragment string return value, fixed `<mark>` markup and numeric
   span/cost/reference-count attributes, with full reference metadata obtained
   separately through `detect()`.
2. Approve consumer-controlled presentation: no automatic links, tooltips,
   stylesheet or RTL wrapper in this milestone.
3. Approve the lossless-text policy: numeric CR escaping and annotation-only
   rejection of NUL/lone surrogates, leaving detection unchanged.

The maintainer approved all three choices and subsequently instructed implementation.
They are the implementation requirements; completed work stops for review.
