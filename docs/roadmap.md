# Implementation roadmap

## Workflow and current status

Phase 1 established the library foundation. Phase 2 implements pinned corpus
preparation and shared tokenization; detection and indexing remain unimplemented.
Each phase depends on acceptance of its predecessor:
present changes, checks, limitations, and proposed commits; stop for review and
approval before starting the next. Publishing is separately approval-gated.

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

Typed dataclasses will provide serialization, original input substrings/offsets,
match information, and all independently supported references. Each reference
exposes identifiers, collection/numbering, complete original narration, nullable
URL, matched source substring/offsets, and fuzzy details.

## Decisions for later milestone plans

Phase 2 uses canonical JSONL, mapped compatibility normalization, and matching barriers;
see [data preparation](data-preparation.md). Before implementing the relevant phase,
settle index choice and occurrence representation
(Phase 3), fuzzy limits and completeness policy (Phase 4), and final model fields,
configuration and exception contracts (Phase 5). Benchmark budgets belong in Phase 6.
Revisit this roadmap openly when implementation evidence requires a change.

Code remains MIT; approved corpus terms and attribution are documented separately. Git stores code,
small fixtures and reports; large downloads/derived artifacts remain outside Git.
Approved runtime resources later ship in Python distributions, with reproducible
large artifacts in release assets. No LFS or DVC without a separate decision.
See [data policy](../data/README.md) and [version/release policy](../CONTRIBUTING.md).
