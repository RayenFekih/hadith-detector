# Hadith Detector

An offline Python library for finding Arabic Hadith quotations and returning
independently supporting source references.

**Status: provisional exact and fuzzy detector (Phase 4B).** Exact and partial ordered matching,
multiple passages, source lookup and typed results work with explicitly supplied
local resources. Character-error tolerance and internal source-word omissions work
together. No corpus is bundled and no release is published. Annotation and top-level
convenience functions remain planned.

## Installation and local resources

Python 3.11–3.14 are supported; development and resource construction use Python 3.14.
RapidFuzz (`>=3.14.6,<4`) is the required production character-distance dependency.
Install dependencies before offline use. Detection never needs network access.

Repository-only Phase 4A tools compare complete fuzzy retrieval strategies and
pure-Python versus RapidFuzz bounded word distance. Python distance implementations
remain repository-only correctness tools. See [fuzzy benchmark usage](docs/fuzzy-benchmark.md)
and [the measurements and Phase 4B recommendation](docs/phase4-fuzzy-benchmark.md).

```sh
uv sync --locked
```

Prepare the pinned corpus using the separate `data` dependency group and the
[data-preparation guide](docs/data-preparation.md), then build its index offline:

```sh
uv run python -m tools.build_index --corpus-dir data/prepared-corpus --output-dir data/runtime-index
```

Choose a new output directory for each build. Downloads and generated resources
stay outside Git. Research notebooks use separate exploratory environments.

## Working provisional API

```python
from hadith_detector import HadithDetector

detector = HadithDetector.from_directory("data/runtime-index")
text = "إنما الأعمال بالنيات"
matches = detector.detect(text, min_match_words=3)
# Optional budgets, independently applied to each supporting occurrence:
tolerant_matches = detector.detect(text, min_match_words=3, max_errors=1, max_missing_words=1)
for match in matches:
    assert text[match.start : match.end] == match.text
    for reference in match.references:
        record = detector.get_hadith(reference.record.hadith_key)
        for occurrence in reference.occurrences:
            assert record.text[occurrence.start : occurrence.end] == occurrence.text
    serializable = match.to_dict()
```

The default minimum is five normalized input words; any positive integer is allowed.
Exact means equality after shared Arabic normalization, with preserved word order.
Punctuation separates words; numbers, non-Arabic words and damaged characters block
matches. Written words remain intact. Offsets are Python string indices with exclusive
ends. All source identities and all supporting occurrences are returned.

Loading validates resources once; subsequent calls reuse them. Loading and detection
never download, rebuild or write resources. See the [API and resource guide](docs/runtime-index.md)
and [Phase 3B validation report](docs/phase3b-validation.md).

## Planned API — not implemented

```python
detect(text, min_match_words=5, max_errors=1, max_missing_words=1)
annotate(text, format="html")
get_hadith(hadith_key)
```

These top-level functions are planned for later milestones; the instance supports fuzzy budgets now.
The provisional class API can change before its finalization in Phase 5.

## Limitations and data rights

Textual support does not independently authenticate a narration. Common chains and
embedded Quranic passages can match corpus text. There is no semantic matching,
Matn/Isnad extraction, mode parameter or inferred expansion of abbreviated narrations.
The approved corpus contains 14,940 complete Bukhari and Muslim source records.
Existing evaluation material remains provisional; oracle agreement verifies algorithmic
behavior rather than real-world authentication or detection accuracy.

Code is [MIT licensed](LICENSE); dataset rights are separate. Pinned configuration
terms, upstream attribution and the maintainer's approval are recorded in
[data/README.md](data/README.md). Resources are local artifacts until the packaging milestone.

See [CONTRIBUTING.md](CONTRIBUTING.md), the [roadmap](docs/roadmap.md) and
[changelog](CHANGELOG.md). Each next phase requires review and approval.
