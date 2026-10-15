# Implementation roadmap

## Workflow and current status

Phase 1 established the library foundation. Phase 2 implements pinned corpus
preparation and shared tokenization. Phase 3A benchmarked indexes; the maintainer
approved the three-word index with unigram fallback. Phase 3B implements compact
resources and a provisional exact detector with explicit local resources. See the
[runtime guide](runtime-index.md) and [validation report](phase3b-validation.md).
Each phase depends on acceptance of its predecessor:
present changes, checks, limitations, and proposed commits; stop for review and
approval before starting the next. Publishing is separately approval-gated.

Phase 4A added an independent fuzzy oracle, complete retrieval experiments and a
bounded-distance comparison with RapidFuzz, preserving the exact runtime at that milestone.
On 2026-10-14 the maintainer selected RapidFuzz as the sole required
production distance engine for Phase 4B, retaining the independent Python implementations
only in repository tests and benchmarks. No dual runtime backends or acceleration extra
are planned. Review [Phase 4A evidence and the revised proposal](phase4-fuzzy-benchmark.md)
for the design evidence. The maintainer subsequently authorized Phase 4B implementation:
the instance API now accepts both budgets, uses RapidFuzz, and returns typed alignment
traces with complete supporting occurrences. Resource and normalization versions remain 1.
See [runtime behavior](fuzzy-runtime.md) and [Phase 4B validation](phase4b-validation.md).
Phase 5 remains pending review and approval.

Before Phase 5, the maintainer requested a review of maintained libraries for the
existing phases. See [library reuse review](library-review.md) for candidates and
compatibility evidence. The requested focused evaluation is recorded in
[library benchmark results](library-benchmark-results.md), with commands in
[the protocol](library-benchmark.md). Production adoption remains pending review;
the experiments do not change runtime dependencies or resource formats.

The prebuilt MARISA v2 trial is implemented separately in repository tooling.
See [the historical acceptance report](marisa-trial.md): complete oracle agreement and a
78 MiB steady-memory reduction, with approximately 52% slower validated loading
and 19% slower first fuzzy calls. The maintainer accepted these one-time costs for
long-lived instances and approved production v2-only integration. Production now
requires MARISA 1.4.1 alongside RapidFuzz; integrity checks remain complete.
See [production validation](marisa-production.md). Phase 5 remains pending.

## Architectural commitments

- Search complete narrations with one engine. No Matn/Isnad extraction or mode parameter.
- Preserve every original source record, text, identity, and useful metadata.
- Normalize derived tokens identically for source and input. Use Quran-detector-style
  letter equivalences (`ة → ه`, `ى → ي`, alif variants), diacritic handling, tatweel
  removal, and presentation-form handling while preserving token boundaries and offsets.
- Preserve word order; exact matching means equality after normalization, not literal
  character identity. Normalization version 1 is implemented and tested in Phase 2.
- Default to five aligned input words; spelling and omission budgets default to zero.
- Count spelling errors as total character Levenshtein edits across aligned words.
  Omissions skip internal source words; skipped words do not count toward the minimum.
- Independently verify each reference against the entire selected input span. Never
  combine partial evidence from different narrations or infer text from «مثله» or «نحوه».
- Group references dynamically by selected passage, without assumed narration families.
- Rank overlaps by descending matched-word count, descending input-span length, fewer
  errors/omissions, then earlier start. Greedily retain non-overlapping spans; return
  them in input order with stable reference ordering.
- Offsets are Python string indices with exclusive ends. Input and source slices must
  reproduce reported original substrings, including relevant combining marks.
- Reuse immutable corpus/index resources across calls. Runtime stays fully offline,
  without rebuilding indexes, LLMs, embeddings, or external APIs.
- Offline operation is required; zero runtime dependencies is not. Well-maintained
  dependencies may be used in any phase when they improve performance, reliability
  or maintainability. Historical zero-dependency implementations describe milestone choices.
- Phase 4 ranks fuzzy cost ties by character edits, then source omissions. Return all
  budget-valid supporting occurrences, with one lowest-cost canonical word trace per
  source span. Internal symbol-expansion omissions are permitted; endpoints stay whole.

## Phases and approval gates

| Phase | Scope and deliverables | Validation | Documentation and commits |
| --- | --- | --- | --- |
| 1. Foundation | Package layout, uv/setuptools/setuptools-scm, no runtime dependencies, tests, CI and accurate project status. | Python 3.11–3.14; outside-checkout imports; no import side effects; wheel/sdist metadata and clean installations; rebuild without Git. | README, contribution guide, changelog, roadmap, data policy. `chore: establish installable library foundation`; `test: validate package builds and add CI`; `docs: document project status and phased roadmap`. |
| 2. Data preparation | Resolve redistribution rights; pin both QuranLab configurations; preserve records; normalize/tokenize with original offsets; produce versioned manifests, checksums, statistics and reports. No index selection yet. | Schema, keys, nullability, unchanged text, duplicate retention, Unicode offsets and reproducible rebuilds. | Provenance and rebuild documentation. `data: document provenance and redistribution terms`; `feat: add reproducible corpus preparation`. |
| 3. Exact baseline | Benchmark indexes, select from measurements, build artifacts; exact/partial matching, multiple passages, reference completeness and overlap selection. | Compare to exhaustive matching on fixtures and full-corpus sampled queries; prevent fabricated cross-record extensions. | Index decision report and exact-match behavior. `perf: benchmark candidate indexes`; `feat: implement exact quotation detection`. |
| 4. Fuzzy matching | Bounded ordered alignment for character edits and internal source omissions, both simultaneously; retrieval robust to corrupted seeds. | Budget boundaries, combined errors/omissions, repeated words, order violations, retrieval completeness and adversarial common phrases. | Error accounting and measured limits. `feat: add spelling-error tolerance`; `feat: add omitted-word alignment`. |
| 5. Public API | Typed results, reusable configuration, serialization, lookup, errors and safe HTML annotation. Minimal internal APIs may appear earlier. | API contracts, independent instances, repeated calls, JSON round trips, offset slicing, HTML escaping and determinism. | Working examples and API docs. `feat: finalize public detection API`; `feat: add safe HTML annotation`. |
| 6. Evaluation | Curate provisional cases, verify expected references against full corpus, optimize measured bottlenecks. | Separate candidate recall, passage accuracy, reference completeness, false positives, startup, latency, memory and artifact size. | Evaluation provenance and benchmark report. `test: establish verified evaluation suite`; justified optimization commits. |
| 7. Release | Bundle approved resources; clean installation and offline validation; prepare initial release process. | Wheel/sdist rebuilds, supported Python versions, network-disabled detection, no runtime rebuild or download, resource integrity and format compatibility. | Installation, attribution, release notes and checklist. `build: bundle validated runtime artifacts`; `docs: prepare initial release`. |

## Index benchmark (Phase 3)

Phase 3A runs the comparison and stops for review of the
[measurements and Phase 3B proposal](phase3-index-benchmark.md).
See [benchmark usage](index-benchmark.md). The approved trigram/unigram design is
implemented in Phase 3B. Phase 4A experiments informed the approved Phase 4B design.

Compare a straightforward exhaustive baseline, a positional inverted index, and
2-, 3-, and 5-word n-gram indexes using identical normalization and queries.
Include short quotations, full narrations, multiple quotations, common chains,
negatives, and future corrupted-query cases. Measure build time, artifact size,
cold initialization, peak memory, warm latency distributions, candidate counts,
and reference recall on ordinary laptops.

Correctness is mandatory. Choose the simplest index with a measured repeated-call
advantage; do not implement an expensive suffix trie purely from intuition.
Fixed n-grams must not prevent smaller configured minimum matches. Performance
budgets follow measurements rather than unsupported numerical promises.

## Planned public surface — not implemented in Phase 1

```python
detect(text, *, min_match_words=5, max_errors=0, max_missing_words=0)
annotate(text, *, format="html", ...)
get_hadith(hadith_key)
HadithDetector(...)
```

Phase 3B implements provisional typed dataclasses with serialization, original input
substrings/offsets and all supporting exact references. Phase 4B adds fuzzy costs,
word alignments and omitted-token traces. Phase 5A finalizes these models and configuration; Phase 5B will add annotation. Each reference
exposes identifiers, collection/numbering, complete original narration, nullable
URL, matched source substring/offsets, and fuzzy details.

## Decisions for later milestone plans

Phase 2 uses canonical JSONL, mapped compatibility normalization, and matching barriers;
see [data preparation](data-preparation.md). Before implementing the relevant phase,
use the approved index and complete occurrence representation described in
[the runtime guide](runtime-index.md) and [fuzzy behavior](fuzzy-runtime.md). Settle final model fields,
configuration and exception contracts (Phase 5). Benchmark budgets belong in Phase 6.
Revisit this roadmap openly when implementation evidence requires a change.

Code remains MIT; approved corpus terms and attribution are documented separately. Git stores code,
small fixtures and reports; large downloads/derived artifacts remain outside Git.
Approved runtime resources later ship in Python distributions, with reproducible
large artifacts in release assets. No LFS or DVC without a separate decision.
See [data policy](../data/README.md) and [version/release policy](../CONTRIBUTING.md).

## Phase 5 review boundaries

Phase 5A finalizes the [public API](public-api.md): frozen defaults, explicit local
resources, a single-entry convenience cache, per-instance sequential locking,
read-only resolved directory visibility and structural dictionary restoration.
The future bundled resource is one combined Bukhari/Muslim corpus. No global
corpus configuration, asynchronous API or parallel processing is introduced.

Matching, MARISA v2, RapidFuzz, normalization v1 and source data remain unchanged.
Phase 5A is accepted following regression, full-corpus oracle, packaging and
Python 3.11-3.14 compatibility checks. The [Phase 5A review report](phase5a-validation.md)
records verification. The [Phase 5B proposal](phase5b-plan.md) covers safe HTML
annotation; the maintainer approved the plan and authorized Phase 5B implementation.
Phase 7 will make resource arguments optional with bundled defaults.

Proposed Phase 5A commits, only when requested:

1. `feat: finalize detector configuration and convenience API`
2. `feat: add validated result deserialization`
3. `test: verify public API caching and concurrency contracts`
4. `docs: document finalized public API`

Phase 5B adds escaped fragments through the existing detector, fixed mark attributes,
original text/offset preservation and annotation-only NUL/surrogate rejection.
See the [HTML guide](html-annotation.md) and [review report](phase5b-validation.md).
Phase 5B stops for verification review;
Phase 6 has not begun. Algorithms, dependencies and resources remain unchanged.
