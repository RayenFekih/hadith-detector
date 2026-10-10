# Hadith Detector

An open-source Python library being developed to detect Arabic Hadith quotations
in arbitrary text and return independently supported source references.

**Status: Phase 1 foundation.** The package installs and exposes `__version__`.
Detection, annotation, source retrieval, corpus preparation, and indexes are
**planned and not implemented**. No corpus is bundled and no release is published.

## Development installation

Python 3.11–3.14 are tested; local development uses Python 3.14. With
[uv](https://docs.astral.sh/uv/) installed, run from this checkout:

```sh
uv sync --locked
uv run python -c "import hadith_detector; print(hadith_detector.__version__)"
```

The foundation has no runtime dependencies. Research notebooks have separate,
unsupported exploratory environments; their dependencies are not installed here.
See [CONTRIBUTING.md](CONTRIBUTING.md) for checks and the review workflow.

## Planned capabilities

- Exact and partial ordered quotation matching, with a default minimum of five words.
- Arabic normalization, diacritic handling, multiple passages, and original character offsets.
- Optional spelling-error and omitted-word tolerance, both disabled by default.
- All independently verified references supporting each selected passage.
- Longest-supported-match selection for overlaps and deterministic output.
- Fully offline runtime, with packaged corpus and prebuilt index once redistribution is verified.

The initial target is QuranLab's `bukhari-ar` and `muslim-ar` configurations,
approximately 14,940 complete narrations. Original source text and identities will
remain intact. Matn, Isnad, and combined inputs use the same engine; there is no
detection mode or Matn/Isnad extraction.

## Planned API — not executable yet

```python
from hadith_detector import HadithDetector, annotate, detect, get_hadith

results = detect(text)
results = detect(text, min_match_words=5, max_errors=1, max_missing_words=1)
annotated = annotate(text, format="html")
record = get_hadith("bukhari:1")
detector = HadithDetector()
```

Planned typed results will expose original input substrings and offsets, complete
source narrations, identifiers, numbering, nullable URLs, matched source spans,
and per-reference matching details. Offsets use Python string indices and exclusive ends.

## Limitations and data rights

Textual detection does not independently authenticate a narration. Common chains
and Quranic passages embedded in narrations can match corpus text. No semantic
similarity, embeddings, LLMs, external runtime APIs, narration-family assumptions,
or expansion of abbreviated narrations will be used.

The code is [MIT licensed](LICENSE). Dataset and digitization rights are separate:
QuranLab's provenance and licensing summaries require configuration-specific
verification before public redistribution. See [data/README.md](data/README.md).
Existing evaluation examples are provisional, not definitive ground truth.

See the [implementation roadmap](docs/roadmap.md) and [changelog](CHANGELOG.md).
Each phase requires review and approval before the next begins.
