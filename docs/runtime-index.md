# Exact and fuzzy detector with compact resources

Phase 3B implements the approved three-word index with complete unigram fallback.
The repository builder consumes verified Phase 2 artifacts; the installed library
uses RapidFuzz for fuzzy character distances and an explicitly supplied resource directory.
Nothing is bundled, downloaded or rebuilt by the runtime.

## Build and use

Use the recorded Python 3.14 environment. This command is offline and refuses an
existing output directory:

```sh
uv run python -m tools.build_index --corpus-dir data/prepared-corpus --output-dir data/runtime-index
```

The builder verifies the prepared corpus, constructs resources in a temporary sibling
directory, validates the complete result, then renames it into place. Failed validation
leaves no accepted partial output. Keep these directories ignored, alongside raw data.
Names such as `runtime-index-a` and `runtime-index-b` are arbitrary directory names
for independent reproducibility checks, not format requirements.

```python
from hadith_detector import HadithDetector

detector = HadithDetector.from_directory("data/runtime-index")
results = detector.detect("إنما الأعمال بالنيات", min_match_words=3)
if results:
    first = results[0]
    record = detector.get_hadith(first.references[0].record.hadith_key)
    payload = first.to_dict()
```

`detect(text, *, min_match_words=5, max_errors=0, max_missing_words=0)` returns
`list[Detection]`. Empty input returns
an empty list. Minimum values must be positive integers, excluding booleans;
invalid values raise `ValueError`. Non-string text or source keys raise `TypeError`.
Unknown keys raise `KeyError`. Missing resource files raise `FileNotFoundError`;
incompatible versions, invalid checksums or structural corruption raise `ValueError`.
These contracts and models are provisional until Phase 5.

## Results and source preservation

| Model | Fields |
| --- | --- |
| `Detection` | `start`, `end`, `text`, `matched_words`, `references`, `errors`, `missing_words` |
| `HadithReference` | `record`, `occurrences` |
| `SourceOccurrence` | `start`, `end`, `text`, `errors`, `missing_words`, `alignment`, `omitted_source_tokens` |
| `WordAlignment` | `input_token`, `source_token`, `input_start`, `input_end`, `source_start`, `source_end`, `errors` |
| `OmittedSourceToken` | `source_token`, `start`, `end`, `text`, `term` |
| `HadithRecord` | Original identity, numbering, language, collection, text, grades and nullable URL fields; `additional_metadata` for unknown source fields |

All models provide `to_dict()` for JSON-compatible values. `HadithRecord.to_dict()`
reconstructs the complete original flat record, including additional fields and nested
metadata. Other serializers use nested dictionaries and lists. Model attributes are
frozen; nested metadata is an independent mutable snapshot. Mutating returned metadata
does not change another result, a later lookup, or the loaded corpus.

Offsets use exclusive Python string indices. Slicing the original input or narration
reproduces the reported substring. References sort by collection and source sequence;
occurrences sort by source start/end. Distinct identities sharing text remain distinct.

## Matching behavior

Source and input use normalization version 1, unchanged from Phase 2. Terms match in
contiguous order within one segment and one narration. Punctuation and whitespace
separate words; matching barriers cannot be crossed. Complete symbol expansions are
required at both ends, so a match cannot consume only part of `ﷺ`. Expanded words
count as normalized words and share the original symbol's span.

Every minimum-length window throughout the input is considered. At minimum lengths
of three or more, retrieval chooses the least frequent trigram in that window; below
three it uses unigram postings. Retrieved candidates are verified and extended by
ordered token equality. There are no posting, reference or occurrence caps.

Select overlapping passages by descending matched-word count, descending original
input-span length, then earlier start. Exact matching has no error or omission budget.
Valid non-overlapping tails of suppressed alignments remain eligible. Results return
in input order. Every reference supports the complete selected passage, including
references recovered from longer suppressed alignments; all source occurrences survive.

## Resource format version 1

The format is explicit little-endian binary tables plus canonical UTF-8 JSON, with
independent index, manifest, record, token and normalization versions, currently all 1.
Record IDs follow prepared collection/sequence order; vocabulary IDs follow first
occurrence order. No timestamp, absolute path or library development version enters
deterministic resources.

| File | Payload |
| --- | --- |
| `records.jsonl` | Unchanged complete Phase 2 records |
| `vocabulary.json` | Ordered normalized terms |
| `tokens.bin` | Four uint32 values per token: term ID, start, end, segment |
| `record-offsets.bin` | uint64 global token boundaries, including terminal boundary |
| `unigram-offsets.bin` | Vocabulary-aligned `(uint64 offset, uint32 count)` blocks |
| `unigram-postings.bin` | uint64 postings |
| `trigram-keys.bin` | Lexicographically sorted triples of uint32 term IDs |
| `trigram-offsets.bin` | Key-aligned `(uint64 offset, uint32 count)` blocks |
| `trigram-postings.bin` | uint64 postings |
| `manifest.json` | Provenance, versions, counts, code/environment fingerprint and SHA-256 checksums |

Every binary file starts with the 32-byte header `<8sIIIIQ`: magic `HDIDX001`,
index version, file-kind ID, row width, flags (1 = little endian), and row count.
Postings encode `(record_id << 32) | local_token_position`. Counts and IDs are bounded
by uint32; headers and block offsets are uint64. The loader checks exact sizes before
allocation, source identities and spans, key order, posting bounds and ordering,
segment validity and complete unigram/trigram coverage. Checksums detect accidental
changes; they do not authenticate an untrusted publisher.

Loading uses compact arrays and token memoryviews plus a trigram lookup dictionary;
it reads resources eagerly and performs structural verification without retokenizing
all narrations. Each detector loads once and reuses its resources across calls.
Different detector instances load independent resources. Missing or incompatible
resources never trigger automatic conversion.

## Reproduce full-corpus validation

Build twice into different directories, then compare every artifact and the saved
Phase 3A oracle results in separate worker processes:

```sh
uv run --group benchmark python -m tools.validate_runtime_index run --index-dir data/runtime-index-a --index-dir data/runtime-index-b --benchmark-dir data/phase3-benchmark --output-dir data/runtime-validation
```

Ordinary CI uses synthetic resources and never downloads the corpus. Full-corpus
evidence and measured limitations are recorded in [the validation report](phase3b-validation.md).
Phase 4B adds fuzzy matching and omitted source words; see [fuzzy behavior](fuzzy-runtime.md)
and [its validation report](phase4b-validation.md). HTML annotation and packaged resources
remain later milestones.
