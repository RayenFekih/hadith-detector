# Phase 4A fuzzy experiments

These repository tools compare complete fuzzy retrieval and bounded character
distance. The public package still implements exact detection only. Runtime
requirements and corpus/index formats remain unchanged.

## Environment and commands

Use Python 3.14 and the locked benchmark group, containing psutil and RapidFuzz 3.14.6:

```sh
uv sync --locked --group benchmark
uv run --frozen --group benchmark pytest tests/test_fuzzy_benchmark.py
uv run --frozen --group benchmark python -m tools.fuzzy_benchmark prepare --corpus-dir data/prepared-corpus --exact-dir data/phase3-benchmark --output-dir data/phase4-fuzzy
uv run --frozen --group benchmark python -m tools.fuzzy_benchmark run --corpus-dir data/prepared-corpus --output-dir data/phase4-fuzzy
```

Preparation refuses an existing directory. It writes deterministic queries, a
10,000-pair scalar workload, complete oracle results and expected hashes. The
`ready.json` marker appears only after all fuzzy and zero-budget oracle checks pass.
An interrupted preparation remains unaccepted; use another output directory.
Run consumes the accepted preparation and starts six sequential isolated workers.
Both operations use verified local corpus files, with no network access. Network
may be used only when initially installing development dependencies.

The exact directory supplies the saved Phase 3A query suite and independent result
hashes. Full-corpus downloads never run in ordinary CI. All generated resources,
queries, traces and detailed measurements remain ignored by Git.

For synthetic smoke checks, `--per-category 1 --micro-count 50` reduces preparation
size. Acceptance measurements use the defaults: 168 fuzzy cases, 168 exact
regressions and 10,000 microbenchmark pairs.

## Semantics

Character edits operate within normalized word pairs, with unit-cost insertion,
deletion and substitution. A transposition costs two edits. Source words can be
omitted strictly between aligned endpoints; input words cannot be skipped, joined,
split or reordered. Both budgets apply independently to each source occurrence.
Numbers, non-Arabic text and damaged characters remain barriers. Expansion endpoints
must be whole, while internal expanded words may be omitted.

Budgets accept any nonnegative integer, excluding bool. Internal bounds depend on
finite text lengths rather than user-budget-sized arrays. Minimum aligned input
words remain positive, defaulting to five. No similarity threshold or result cap is added.

Every candidate is independently verified inside one source segment. Passage selection
uses words, original input-span length, best supporting edit count, omission count,
then earlier start. Every budget-valid occurrence is retained, even alongside exact
support. Canonical paths minimize edits, omissions and aligned source-token indices.
The oracle and prototypes enumerate shorter legal endpoints as well as longer ones,
so non-overlapping tails remain available after greedy selection.

Zero budgets dispatch to the independent Phase 3 exact oracle or the existing exact
index verifier, respectively, then attach zero-cost word traces. This retains the
established exact selection/recovery semantics and avoids materializing every exact
subsequence of full narrations. Fuzzy verification itself is independently checked
against direct path enumeration and uses different state transitions in oracle and prototypes.

## Retrieval and kernels

First-word retrieval scans vocabulary length buckets for every budget-valid first
word. Guaranteed anchors use `errors + 1` distinct input positions when the minimum
exceeds the error budget: at most `errors` aligned words can differ, so at least one
selected position is exact. Earlier source omissions shift an anchor's inferred
start by zero through the feasible omission budget.

The hybrid uses all trigrams in a minimum window when
`minimum - errors > 2 * (errors + missing + 1)`. At least `minimum - errors` words
are exact, split into at most `errors + missing + 1` runs; that inequality guarantees
a run of three. Otherwise it falls back to anchors or approximate first words.
These are complete retrieval arguments, not heuristics assuming an intact seed.

The shared verifier precomputes source segment endpoints once and input segment
endpoints once per call. This avoids repeated scans without changing retrieval,
barrier constraints or accepted alignments; its memory is included in measurements.

Both backends use identical scalar calls, ordering, length checks and caches. RapidFuzz
uses `Levenshtein.distance` with unit weights, no processor/hint, and the remaining
character budget as cutoff. Over-cutoff values are rejection sentinels, not exact
distances. No token-similarity scorers, batch search or threading are involved.

Distance results use an LRU cache of 50,000 `(word pair, cutoff)` entries; approximate
word lists use 4,096 entries. Eviction affects work, never completeness. Both backends
share these limits, and reports include cache counts and eviction statistics.
The raw `kernel_calls` counter counts distance-cache misses, including the shared
identity/length short circuits; interpret it as cache misses, not native function calls.

## Results, measurements and limitations

Experimental JSON adds passage/occurrence `errors` and `missing_words`, an `alignment`
list with input/source token indices, original offsets and per-word costs, and
`omitted_source_tokens` with token indices, spans, text and normalized terms. Repeated
symbol spans remain distinguishable by token indices. Full source metadata stays in
the verified corpus, referenced by identity; the experiment does not copy it into
every result. No character edit scripts or public model exports are introduced.

Each worker records import memory/time, verified corpus loading, index construction,
first-call latency, first correctness-pass times and three warm repetitions. The
first correctness pass uses progressively populated caches; it is not a completely
cold process for every query. Scalar microbenchmarks bypass application caches.
Corpus loading retokenizes prepared records for verification and is not a production
startup prediction. Each prototype also reloads its serialized posting index and
checks every fuzzy case again, followed by the 168 exact regressions.

Peak memory includes corpus, index, result traces, caches, serialization and reload;
import-only deltas help isolate backend overhead. Pure-Python workers never import
RapidFuzz. Raw timings and environment metadata are separate from deterministic
queries, oracle outputs and prototype indexes. Checksums establish reproducibility,
not publisher authenticity.

The workload uses synthetic mutations and surroundings, including deliberately
unmatchable long-word filler in large inputs. It measures algorithmic agreement and
performance on these cases, not semantic accuracy on ordinary Arabic prose.
Common phrases and large budgets may produce many supporting occurrences.

See [the measured report and Phase 4B proposal](phase4-fuzzy-benchmark.md).
