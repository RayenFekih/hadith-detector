# Phase 3A exact-index experiments

These tools compare exact lexical matching on the verified Phase 2 corpus. They
are repository-only; no `detect`, `get_hadith`, or `HadithDetector` public API is
introduced. Fuzzy matching, omission tolerance and annotation are outside this milestone.

## Run locally

```sh
uv sync --locked --group benchmark
uv run --frozen --group benchmark python -m tools.exact_benchmark run --corpus-dir data/prepared-corpus --output-dir data/phase3-benchmark
```

Use a new output directory for every run. After dependencies are installed, add
`--offline` to uv: experiments read only local files and do not access services.
The prepared input is checksum-verified and its tokens are regenerated to check
normalization and offsets before any measurement. This loading/validation cost
is separate from index construction and is not a production startup estimate.

Default generation creates 168 queries: 20 in each of bare excerpts, embedded
paragraphs, multiple quotations, full narrations, common phrases/chains, short
queries, verified negatives, and normalization/perturbation variants; plus eight
larger inputs around 1,024/4,096 tokens. Source sampling balances collections when
applicable; full narrations span length quantiles. Seed 42 is fixed. `--per-category`
can reduce ordinary categories for a smoke run; larger-input cases remain eight.
Excerpt sampling and full-narration quantiles use records with at least 30 tokens;
the separate short-query category covers minimum lengths one through four.

## Algorithms and correctness

The exhaustive oracle scans every contiguous source window on each query. It uses
only a query-seed map, not a corpus search index. The indexed prototypes retrieve
positional word, word-pair, word-triple or five-word postings, using the rarest
available seed inside each minimum-length query window. All n-gram prototypes
also store unigrams to support any positive minimum, including one-word queries.

Verification preserves token order and segments, extends each matching alignment
inside one source record, and trims incomplete symbol expansions. No stopwords,
semantic filters, source deduplication, reference limits or candidate caps are used.
Normalized equality and Python original-text offsets use the existing Phase 2 tokenizer.

Selection ranks all supported contiguous substrings by word count, character-span
length, and earlier start. After selecting a passage, independently supported
non-overlapping fragments outside it remain eligible if they meet the minimum.
No source texts are stitched together. Recovery includes every source alignment
supporting a selected span, even when that source's longer alignment was suppressed.
Each original identity appears once per passage with all source occurrences in order.

The oracle has its own discovery/selection/recovery implementation. Indexed
prototypes share a separate verifier. Manual expected cases and a tiny exhaustive
substring enumerator independently check both paths, including ligatures,
repetition, barriers, overlap fragments and complete references.

## Outputs and measurement

The output directory contains deterministic `queries.json`, result fingerprints
from the oracle, prototype JSONL indexes, worker logs, per-candidate metrics,
`summary.json`, and a Markdown report. These large experimental artifacts remain
ignored by Git; only the compact reviewed report belongs in docs.

Each candidate runs in a fresh subprocess, first checks every query against the
oracle, then writes/reloads its index and runs three warm repetitions per query.
Complete result hashes and counters must agree before/after reload and across all
repetitions. A second independent index build must produce identical bytes.
Only one index instance is retained at a time; no other candidate index is resident.

Report construction, serialization, reload, first-call and warm latency separately.
The first call is an embedded-paragraph query after corpus validation and index
construction; it is not a cold operating-system/disk startup measurement.
Warm timing includes query normalization and complete result creation, excluding
result hashing. Category median/p95 pools three measurements per query. Candidate
counts describe retrieved seed postings before exact verification; verification
calls and final source-occurrence counts are recorded separately. The oracle
counts matching minimum-window hits rather than retrieved postings, so its
candidate count is not the same kind of filtering workload as an index's.

psutil samples worker RSS every 10 ms; Windows native peak-working-set information
also contributes where available. Peak covers the whole worker lifecycle, including
corpus validation, serialization/reload, result materialization and rebuild checks.
It is a process high-water mark, not an isolated persistent-index allocation size.

Prototype serialization is canonical uncompressed JSONL: a version/corpus/candidate
header followed by sorted keys and sorted `[record_id, token_position]` pairs for
unigram and n-gram tables. Posting memory uses unsigned integer arrays internally.
Record IDs follow collection/sequence order; word IDs follow first occurrence in
that corpus order. The JSONL experiment format is not the production runtime format.

No semantic accuracy claims are made. Negatives are exhaustively confirmed absent;
perturbed cases are evaluated for remaining exact fragments, not fuzzy recall.
Numbers depend on this machine and these queries. Review startup, memory, storage
and default paragraph speed together before approving the Phase 3B index design.
