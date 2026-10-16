# Hadith Detector

**Detect Arabic Hadith text and find its sources. Offline, in Python.**

[![Python 3.11–3.14](https://img.shields.io/badge/Python-3.11%E2%80%933.14-3776AB?logo=python&logoColor=white)](https://github.com/RayenFekih/hadith-detector/blob/main/pyproject.toml)
[![CI](https://github.com/RayenFekih/hadith-detector/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/RayenFekih/hadith-detector/actions/workflows/ci.yml)
[![Code license: MIT](https://img.shields.io/badge/Code_license-MIT-blue.svg)](https://github.com/RayenFekih/hadith-detector/blob/main/LICENSE)

`hadith-detector` is a Python library that finds Arabic passages matching Hadith texts and returns their supporting sources. It works with short quotations or longer documents, supports exact and configurable fuzzy matching, and runs locally without an API key or an internet connection after installation.

The current bundled corpus covers **Sahih al-Bukhari and Sahih Muslim**. Support for additional Hadith collections is planned.

## Installation

```bash
pip install hadith-detector
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add hadith-detector
```

Requires **Python 3.11–3.14**. The package includes the Hadith texts and a prebuilt search index, so there is no separate corpus download or index-building step. Detection works offline after installation.

## Quick start

Detect a Hadith quotation and highlight it in the original Arabic text:

```python
from hadith_detector import detect, annotate

text = "قال رسول الله ﷺ: إنما الأعمال بالنيات وإنما لكل امرئ ما نوى."

matches = detect(text)
print(matches[0].text)
print(matches[0].references[0].record.hadith_key)

html = annotate(text)
print(html)  # Escaped HTML fragment with <mark> around detected passages
```

`detect()` returns matched passages, their original character offsets, and supporting Hadith references. A passage may have multiple supporting references. `annotate()` returns an HTML fragment that highlights matches without changing the original Arabic wording.

## Features

- **Exact Arabic text matching**, with normalization of supported Arabic letter forms and diacritics.
- **Optional fuzzy matching** for limited spelling differences and omitted words from the source.
- **Source references** with complete original records, occurrences, offsets, and alignment details.
- **Multiple detections** within the same paragraph or document.
- **HTML highlighting** of detected passages using `annotate()`.
- **Offline and deterministic** operation with a bundled index; no LLM or external service required.

## Configuration

The default settings are intentionally strict:

| Parameter | Default | What it controls |
| --- | ---: | --- |
| `min_match_words` | `5` | Minimum number of matched input words. Lower values also detect more short, common expressions; higher values can miss short quotations. |
| `max_errors` | `0` | Total number of character edits allowed across the matched words. |
| `max_missing_words` | `0` | Number of internal words in the source passage that may be absent from the input. |

```python
from hadith_detector import DetectorConfig, HadithDetector

detector = HadithDetector(
    config=DetectorConfig(
        min_match_words=5,
        max_errors=1,
        max_missing_words=1,
    )
)

matches = detector.detect("إنما الأعمال بالنياث وإنما لكل امرئ ما نوى")

# Override the settings for one call without changing the configuration.
exact_matches = detector.detect(
    "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى", max_errors=0, max_missing_words=0
)
```

For long Arabic documents, consider a higher `min_match_words` if short incidental matches create too much noise. Enable fuzzy budgets only when your input may contain spelling variations or source-word omissions. Broader settings can increase both detections and processing time. There is no universally best configuration; test the trade-offs on your own texts.

## More usage examples

**Retrieve a complete source record**

```python
from hadith_detector import get_hadith

record = get_hadith("bukhari:1")
print(record.text)
```

**Highlight matches in plain text**

```python
from hadith_detector import annotate

html = annotate("ورد في النص: إنما الأعمال بالنيات وإنما لكل امرئ ما نوى")
```

`annotate()` produces an escaped HTML fragment with matched passages wrapped in `<mark>` elements. It is designed for plain-text input, not for editing an existing HTML document.

## Important notes

- **Generic phrases can trigger incidental matches.** For example, a phrase such as `هو عبد الله` may also appear in Hadith records even when it occurs in an unrelated article. Likewise, narration formulas such as `عن النبي صلى الله عليه وسلم قال` may match without being meaningful standalone quotations. Shorter `min_match_words` values increase this risk, and permissive fuzzy budgets can introduce additional matches. **Tune `min_match_words`, `max_errors`, and `max_missing_words` for your text and use case**, especially for long documents; increasing the minimum can reduce short incidental matches but may miss genuine short quotations.
- **A match means textual support, not quotation intent.** Common expressions, honorifics, Quranic wording embedded in narrations, and narrator-chain fragments can also match. Do not automatically treat every detection as a deliberate Hadith quotation.
- **Review citations and source context.** Before publishing religious content or relying on the returned citation, inspect the original narration, relevant supporting occurrences, and data provenance. The library does not independently authenticate Hadith or interpret their meaning.
- **No match does not mean no Hadith exists.** Coverage is currently limited to the bundled Sahihayn collection, and configured matching thresholds may exclude short or modified quotations.
- **The dataset is preserved as supplied.** Source data can include duplicate narration texts, missing URLs, or damaged characters. Check that it meets your application’s accuracy and provenance requirements.

## Data

The package currently includes **14,940 Arabic Hadith records**:

| Collection | Records |
| --- | ---: |
| Sahih al-Bukhari | 7,580 |
| Sahih Muslim | 7,360 |

The data comes from the [QuranLab Hadith dataset on Hugging Face](https://huggingface.co/datasets/quranlab/hadith), using its `bukhari-ar` and `muslim-ar` configurations. Original Arabic records, source identities, and accompanying metadata are retained. **Additional Hadith books are planned for future versions.**

The library's **code is MIT-licensed**; the underlying Hadith data has separate source terms and notices. Consult the [dataset provenance and redistribution notes](https://github.com/RayenFekih/hadith-detector/blob/main/tools/bundle-notices/PROVENANCE.md) before reusing or redistributing the data independently.

## Use cases

- **Arabic documents and articles:** Locate matching Hadith passages inside longer text.
- **Research and reference lookup:** Find supporting collections and inspect the original narration.
- **Educational and editorial tools:** Help reviewers locate quotations and check source wording.
- **Web applications:** Highlight text matches and show citations or source context.
- **AI and LLM applications:** Check generated Hadith wording, retrieve source passages, and provide grounding evidence for citation workflows. Human review remains important.

## Documentation and community

- [Public API and result structure](https://github.com/RayenFekih/hadith-detector/blob/main/docs/public-api.md)
- [Matching and fuzzy behavior](https://github.com/RayenFekih/hadith-detector/blob/main/docs/fuzzy-runtime.md)
- [HTML annotation](https://github.com/RayenFekih/hadith-detector/blob/main/docs/html-annotation.md)
- [Evaluation and limitations](https://github.com/RayenFekih/hadith-detector/blob/main/docs/phase6-evaluation.md)
- [Contributing](https://github.com/RayenFekih/hadith-detector/blob/main/CONTRIBUTING.md)
- [Changelog](https://github.com/RayenFekih/hadith-detector/blob/main/CHANGELOG.md)
- [Report a bug or request a feature](https://github.com/RayenFekih/hadith-detector/issues)

Contributions, issue reports, reproducible examples, and suggestions for additional Hadith sources are welcome.
