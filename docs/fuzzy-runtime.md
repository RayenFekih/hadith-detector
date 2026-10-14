# Fuzzy matching (Phase 4B)

```python
from hadith_detector import HadithDetector

detector = HadithDetector.from_directory("data/runtime-index")
results = detector.detect(text, min_match_words=5, max_errors=1, max_missing_words=1)
```

Both budgets default to zero and accept any nonnegative integer, excluding booleans.
The minimum accepts any positive integer. Invalid values raise `ValueError`, even for
empty inputs. Bounds are clamped to available words/characters internally; no user budget
caps silently change semantics. Large budgets can still require substantial work and
produce many references. There is no fuzzy search mode or hidden reference limit.

Each aligned normalized word pair consumes unit-cost Levenshtein insertions, deletions
and substitutions. A transposition costs two edits. Input words cannot be skipped,
reordered, split or joined. Only internal source words may be omitted; neither leading
nor trailing omissions are allowed. Both budgets apply independently to every source
occurrence. Omitted words do not count toward the minimum.

Normalization remains version 1; the compact MARISA index is version 2. Barriers cannot be crossed,
even using omissions. Input/source endpoints must consume complete symbol expansions.
Internal expanded source words may be omitted; token indices distinguish shared spans.
Character offsets always slice the original input and source strings, including marks.

Retrieval chooses `max_errors + 1` least-frequent distinct input positions when the
minimum exceeds the error budget: at least one must match exactly. Every feasible
omission count before an anchor is examined. Otherwise it compares the first input word
against the entire eligible vocabulary using length buckets and RapidFuzz, then retrieves
all matching unigram postings. Unknown input terms are retained. Every legal input start
is examined; the retrieval window need not end at a symbol boundary.

Discovery verifies ordered alignments and records only the best cost pair for each input
span. Selection ranks by matched words, original span length, fewer edits, fewer omissions,
then earlier start. Greedy non-overlap selection retains eligible shorter tails. A second
verification pass recovers every supporting identity and distinct source span under the
original budgets. An exact reference does not suppress another approximate reference.
Each occurrence uses the lowest edits, then lowest omissions, then lexicographically
earliest aligned source-token positions. References and occurrences retain source ordering.

`Detection.errors` and `missing_words` are the best pair from a single supporting
occurrence. Each `SourceOccurrence` has its own costs, `alignment: tuple[WordAlignment,
...]` and `omitted_source_tokens: tuple[OmittedSourceToken, ...]`. Input token indices
refer to the entire normalized input; source token indices refer to the entire narration.
These frozen models are exported. Dictionary serialization uses lists, with the new keys
also present on exact results. Existing occurrence/detection constructor calls retain
default zero costs and empty traces; detector-generated exact results include word traces.
Source metadata snapshots and lookup behavior are unchanged.

Install RapidFuzz (`>=3.14.6,<4`) before offline use. It is imported on first fuzzy use;
zero-budget calls use the existing exact matcher without initializing fuzzy helpers.
Missing/broken imports raise a clear `RuntimeError`. No project Python runtime fallback,
acceleration extra, download or index rebuild is provided. RapidFuzz supplies the
[bounded Levenshtein contract](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html).
Independent Python implementations remain outside the installed package for correctness
and upgrade tests.

Each instance lazily builds vocabulary length buckets and compact source-segment endpoints
once. A distance LRU holds at most 50,000 word-pair/cutoff entries; over-cutoff sentinels are
never treated as exact distances. Neighbor caching is limited to 4,096 keys and 100,000
total word IDs. Oversized entries are computed without caching; eviction causes
recomputation without losing candidates. Instances have independent caches. Concurrent
calls on one instance execute sequentially under the Phase 5A instance lock.

Run synthetic checks with `uv run --group benchmark pytest tests/test_fuzzy_detector.py`.
Reproduce full-corpus validation offline using the saved Phase 4A evidence:

```sh
uv run --group benchmark python -m tools.validate_fuzzy_runtime --index-dir data/runtime-index-v2-a --benchmark-dir data/phase4-final --output data/phase4b-validation/report-v2.json
```

Choose a new report filename each run. Keep generated data ignored. Textual support is
not independent authentication; common chains and embedded Quranic passages can match.
Annotation and corpus bundling remain later milestones; convenience functions are implemented.

Phase 5A adds frozen defaults and sequential shared-instance calls. Omitted/None
settings inherit configuration; explicit zero overrides it. See [public API](public-api.md).
