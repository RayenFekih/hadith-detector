# HTML annotation (Phase 5B)

Annotation returns an HTML fragment string containing escaped **plain input text**
and one `<mark>` per detector-selected passage. It supports exact matches,
character edits and internal source omissions with the same configuration and
matching behavior as `detect()`.

```python
from hadith_detector import DetectorConfig, HadithDetector, annotate

detector = HadithDetector("data/runtime-index-v2-a", config=DetectorConfig(max_errors=1))
text = "مثال: إنما الأعمال بالنياث وإنما لكل امرئ ما نوى"
html = detector.annotate(text)
strict_html = detector.annotate(text, max_errors=0)

# Reuse the single convenience cache; index_dir remains required until Phase 7.
assert annotate(text, index_dir=detector.index_dir, config=detector.config) == html
```

The instance signature is
`annotate(text, *, format="html", min_match_words=None, max_errors=None, max_missing_words=None)`.
The top-level function adds required keyword-only `index_dir` and optional
`config=None`, following [public configuration precedence](public-api.md).
Only the exact format string `"html"` is supported. Non-string text/format raises
`TypeError`; unsupported formats and invalid settings raise `ValueError`.
Settings are validated for empty/no-match inputs. The empty fragment is `""`;
no-match input is escaped normally.

## Original text, offsets and selection

Annotation calls the existing detector once and uses its original exclusive-end
Python string spans. It does not normalize for rendering, repeat retrieval,
rerank overlapping candidates or replace input with source narration text.
Existing overlap selection and eligible tails apply unchanged. Adjacent selected
passages remain separate marks. All unmatched text remains present.

Diacritics, tatweel, direction/joining controls, punctuation, whitespace, symbols
and supplementary characters remain in their original positions. Fuzzy matches
highlight the original spelling. Missing source words are not inserted into input.
HTML encoding changes serialized output positions; `data-start` and `data-end`
always refer to the original Python string. They are not UTF-8 byte offsets or
JavaScript UTF-16 offsets.

## Fixed markup

Each passage is rendered with these attributes, in this order:

```html
<mark class="hadith-match" data-match-index="0" data-start="12" data-end="47" data-errors="1" data-missing-words="0" data-reference-count="2">...</mark>
```

`data-match-index` starts at zero in input order. Costs are the passage's best
supporting pair; other supporting occurrences may have different costs.
`data-reference-count` counts source identities, not source occurrences. Exact
and fuzzy passages use the same markup. No source URLs, narration metadata,
embedded JSON, automatic links, tooltips, scripts or event attributes are added.
Use `detect()` separately when full references and canonical traces are needed;
annotation does not truncate or change detection results. No public interface
accepts externally supplied detections.

## Escaping and presentation

Every input slice is escaped using standard-library HTML escaping, including
quotes. Literal `<script>` tags and entity-like strings remain plain text. This
function is not a sanitizer for an existing HTML document: supplying HTML means
annotating its literal source text. Markup names are fixed and caller-defined
attributes/templates are not accepted.

Carriage returns are encoded as `&#13;` so HTML newline preprocessing does not
replace them. Decoded text reproduces the original string, including CR/LF and
tabs. NUL and lone surrogate characters raise `ValueError` for annotation because
HTML cannot represent them losslessly. `detect()` accepts the same strings as
before; this restriction changes neither detection nor normalization.

The fragment supplies no wrapper, direction override, stylesheet or document
shell. The consumer chooses direction and presentation. To display original
spacing and line breaks, apply `white-space: pre-wrap` to the containing element:

```css
.quotation-text { white-space: pre-wrap; }
.hadith-match { background: #fff2b3; }
```

Concurrent annotation/detection/lookup calls on one instance execute sequentially,
including rendering, under its reentrant lock. Convenience-cache locking is
released before annotation. Clearing the cache does not interrupt an in-flight
call. Resources remain immutable, offline and validated once per initialization.

Textual support is not independent Hadith authentication. Safe rendering does
not change corpus limitations, matching accuracy or evaluation claims.
