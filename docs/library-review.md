# Library reuse review before Phase 5

Reviewed on 2026-10-14 against the implemented foundation, preparation pipeline,
exact index and fuzzy runtime. This is a selection survey, not an adoption or performance
report. No packages were installed, requirements changed, artifacts rebuilt or detector
code modified. Phase 5 has not started. Current release metadata and official project
documentation were checked; actual installation/parity testing remains part of evaluating
the candidates the maintainer selects.

## Recommendation for selection

First evaluate RapidFuzz's collection search APIs, `msgspec` versus `orjson`, and standard
library cache reuse versus `cachetools`. These can target existing vocabulary scans,
JSON loading/conversion and cache plumbing without changing matching semantics or the
current resource format. Select one JSON implementation if justified, rather than adding
both by default.

For a separate storage/memory experiment, consider `marisa-trie`, `pyroaring`, and
NumPy versus standard-library memory mapping. Their potential benefits are credible,
but their integration is larger and may require a new artifact version. None has been
measured on this corpus. Existing Phase 3/4 benchmark winners remain the baseline.

Keep independent Python correctness oracles. Preserve the project's normalization and
alignment policies even if their underlying operations become library-backed. No reviewed
package supplies a drop-in implementation of all our semantics; this is a conclusion
from the documented APIs, not a claim that no such library can exist.

## What already uses maintained implementations

| Area | Existing reuse | Remaining project work |
| --- | --- | --- |
| Foundation | uv, setuptools, setuptools-scm, pytest, Ruff, mypy, build, twine | Project configuration, packaging contents and compatibility contracts |
| Acquisition | `huggingface_hub` | Source revision/lock, provenance and checksum policy |
| Parquet | PyArrow | Identity/type validation and complete original-field preservation |
| Unicode | Standard-library `unicodedata` | Selected letter mappings, original-span tracing, warnings and barriers |
| Binary resources | `array`, `memoryview`, `struct`, `hashlib` | Resource schema, validation, posting completeness and deterministic builds |
| Character distance | RapidFuzz | Retrieval guarantees, ordered alignment, separate budgets and canonical traces |
| Public results | Standard-library dataclasses/deepcopy | Snapshot semantics and result dictionary shape |

Thus, the remaining opportunities are largely replacing Python orchestration, containers
and validation rather than replacing implementations of Parquet, Unicode normalization
or character distance that were written from scratch.

## Most relevant candidates

| Candidate | Existing code it could replace | Potential benefit | Conditions and recommendation |
| --- | --- | --- | --- |
| RapidFuzz `process.extract_iter` / `extract` | `_fuzzy.FuzzyMatcher.approximate()` scalar vocabulary loop | Uses the existing dependency's collection-search implementation and avoids repeated Python distance dispatch | Highest-priority retrieval experiment. Use Levenshtein, unit weights, no preprocessing and all matches, never a default top-five cap. Preserve length buckets, complete IDs and deterministic ordering. |
| `msgspec` | JSON decoding in `_resources`/preparation; portions of record validation and result conversion | Native serialization/decoding and typed validation in one package | First JSON candidate. Start with dictionaries to preserve unknown fields and current public dataclasses. Typed schemas need explicit extra-field preservation; replacing public classes is a separate API decision. |
| `orjson` | JSON loads/dumps around resources and artifacts; possible direct dataclass encoding | Native JSON implementation with direct dataclass support | Benchmark alternative to msgspec. Lower schema scope: it does not replace domain validation, snapshot copying or result shaping. Prefer a decoder-only trial initially. |
| `functools.lru_cache` | Distance cache insertion/eviction in `_fuzzy.distance()` | Standard maintained cache implementation and less manual bookkeeping | Compare first. Use an instance-scoped wrapper, normalize cutoff before the cache key, and avoid a class-level method cache retaining all detector instances. Does not implement neighbor-cache weight limits. |
| `cachetools.LRUCache` | Manual distance and weighted-neighbor LRU handling | Reusable cache implementation with custom value-size accounting | Maintenance candidate, not an assumed speedup: it is Python code. A wrapper still needs both the 4,096-key and 100,000-word limits, oversized-entry bypass and immutable values. |
| `marisa-trie` | Vocabulary and trigram-key lookup dictionaries; potentially key-to-posting-block tables | Native compact static tries, persistence and memory mapping | Promising storage experiment. Keep all occurrence postings, unigram fallback and explicit key encoding. Its trie IDs cannot silently replace current deterministic vocabulary IDs. Likely changes runtime artifacts. |
| `pyroaring` | Candidate-start Python sets and potentially posting containers | Native compressed integer sets and bulk set operations | Promising common-phrase/memory experiment. Use record-aware encoded positions, or 64-bit bitmaps for current packed identities. Offset arithmetic must never carry a position into another record. |
| NumPy | Scalar binary-column validation, selected posting operations and arrays | Native array operations and read-only file mapping | Conditional, after profiling. Existing `array`/`memoryview` already provide compact native storage; NumPy helps only if substantial work becomes vectorized. Compare against stdlib `mmap` before adding a large numeric dependency. |

RapidFuzz documents distance scorers and complete cutoff-filtered iteration in its
[process API](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html). A collection search
may change cache behavior; preserve bounded semantics and measure whole detection, not
just vocabulary kernel speed. This was intentionally excluded from Phase 4A's scalar
comparison and is a new experiment, not a correction to that report.

`msgspec` supports dataclasses and typed decoding, but unknown fields are ignored in
typed dataclass/Struct decoding. Its JSON encoder also maps nonfinite floats to null.
Both need explicit handling under our preservation/rejection policy.
[Supported types](https://msgspec.dev/supported-types).

`orjson` supports dataclass encoding and current supported CPython versions. Its encoder
also converts NaN/infinity to null, and its normal integer range is bounded to 64 bits.
We currently reject non-JSON floats and preserve arbitrary original JSON integers.
Do not replace canonical artifact writing blindly: numeric behavior, escaping, key order,
UTF-8 and exact bytes affect checksums. It may be suitable for runtime decoding even if
canonical preprocessing stays with the standard library.
[Project documentation](https://github.com/ijl/orjson).

`cachetools` supports `getsizeof`, but weights are evaluated on insertion and its caches
are not inherently thread-safe. Adopting it does not by itself establish concurrent
detector-call support. Empty neighbor lists must still count toward the key limit.
[Cache documentation](https://cachetools.readthedocs.io/en/stable/).
The standard-library alternative is documented in
[functools](https://docs.python.org/3.14/library/functools.html#functools.lru_cache).

MARISA persistence/mapping could reduce key-container memory, but mapped random accesses
can slow queries. [MARISA tutorial](https://marisa-trie.readthedocs.io/en/latest/tutorial.html).
PyRoaring supports both 32- and 64-bit integer sets and serialization;
it replaces a container, not ordered match verification.
[PyRoaring API](https://pyroaringbitmap.readthedocs.io/en/latest/).
NumPy supports memory-mapped arrays;
[memmap](https://numpy.org/doc/stable/reference/generated/numpy.memmap.html).

## Further candidates and reasons to defer

| Candidate | Useful capability | Fit for this project |
| --- | --- | --- |
| [pyahocorasick](https://pyahocorasick.readthedocs.io/en/latest/) | Native multi-pattern exact scanning | Could scan encoded trigram seeds, followed by our verifier. Whole-narration patterns do not cover arbitrary partial quotations. Preserve word/segment boundaries, short-query fallback and every overlapping seed. Larger alternative-index experiment, not a direct full matcher replacement. |
| [symspellpy](https://symspellpy.readthedocs.io/en/latest/api/symspellpy.html) | Delete-index vocabulary suggestions | Relevant to approximate first-word retrieval at small budgets. Requires ALL suggestions and ordinary Levenshtein, not a transposition discount. Its built dictionary has a maximum edit budget, so unrestricted public budgets need complete fallback or another explicitly approved design. More resources/maintenance than using RapidFuzz process first. |
| [Pydantic v2](https://docs.pydantic.dev/latest/concepts/strict_mode/) | Strict schemas, useful validation errors, JSON models | Credible alternative if richer validation becomes an API requirement. It adds several dependencies and still needs project checks for uniqueness, checksums and occurrence integrity. Preserve extras and disable coercion. Compare to msgspec for the actual schema before choosing. |
| [cattrs](https://catt.rs/en/stable/) | Conversion of existing dataclasses to/from builtins | Relevant to Phase 5 JSON round trips without replacing public dataclasses. Hooks still need original-record flattening, list serialization and independent snapshots. No demonstrated need to add it alongside another adequate codec. |
| [regex](https://pypi.org/project/regex/) | Unicode properties and grapheme-cluster matching | Could help classification/clustering, but is not a mapped Arabic normalizer. Switching Unicode definitions can alter tokens and artifact fingerprints. Current code already delegates NFKC to `unicodedata`. Defer unless profiling shows a benefit under identical normalization tests. |
| [PyArabic](https://pypi.org/project/PyArabic/) | Arabic stripping/normalization and token locations | Reviewed, but not a drop-in replacement for our expansion mappings/barriers and preserved letter distinctions. PyPI reports GPL and last release in 2022; would need a separate license/maintenance decision. Small helper reuse offers little demonstrated advantage. |
| [edlib](https://github.com/Martinsos/edlib), [parasail](https://github.com/jeffdaily/parasail), [fuzzysearch](https://github.com/taleinat/fuzzysearch) | Native/edit-based or sequence substring alignment | Their documented models do not directly encode separate per-word character errors and source-only internal omission budgets, full symbol endpoints, all occurrences and our canonical trace policy. Adapters could approach the complexity of the current verifier. Defer as matcher replacements. |
| [Numba](https://numba.readthedocs.io/en/stable/user/installing.html) / [Cython](https://pypi.org/project/Cython/) | Compile numeric loops or project algorithms | Acceleration tools, not replacements for algorithm ownership. Numba adds LLVM/NumPy and startup compilation; existing Python objects and RapidFuzz calls need restructuring. Cython adds extension builds/wheel work. Consider only after profiling alignment state work. |
| [SQLite](https://docs.python.org/3.14/library/sqlite3.html) / [Tantivy](https://github.com/quickwit-oss/tantivy-py/blob/master/docs/reference.md) | Existing storage/search indexing engines | SQLite is a stdlib storage alternative worth considering for a future artifact redesign. Tantivy is a native search engine, but document-ranking APIs are not sufficient evidence of all token occurrences and matching-budget completeness. Neither is a drop-in verifier. |

## Compatibility and maintenance evidence

Release information below is from PyPI metadata on the review date. "Wheels" means
listed Windows x86-64 and Linux manylinux wheels for each of CPython 3.11–3.14, not
verified installation or operation. Universal wheels still need operation tests.
Recent releases are evidence of activity, not a guarantee of future maintenance.
License expressions are reported metadata, not a legal interpretation.

| Package | Reviewed latest version | Latest file date | Python/install evidence | Reported license |
| --- | --- | --- | --- | --- |
| [orjson](https://pypi.org/project/orjson/) | 3.13.0 | 2026-10-07 | Python >=3.10; wheels; no mandatory dependencies | MPL-2.0 AND (Apache-2.0 OR MIT) |
| [msgspec](https://pypi.org/project/msgspec/) | 0.22.0 | 2026-09-29 | Python >=3.10; wheels; no mandatory dependencies | BSD-3-Clause |
| [cachetools](https://pypi.org/project/cachetools/) | 7.2.1 | 2026-10-05 | Python >=3.10; universal wheel; no mandatory dependencies | MIT |
| [marisa-trie](https://pypi.org/project/marisa-trie/) | 1.4.1 | 2026-04-08 | Python >=3.9; wheels; no mandatory dependencies | MIT AND (BSD-2-Clause OR LGPL-2.1-or-later) |
| [pyroaring](https://pypi.org/project/pyroaring/) | 1.2.0 | 2026-10-03 | Wheels; no mandatory dependencies | MIT |
| [pyahocorasick](https://pypi.org/project/pyahocorasick/) | 2.3.1 | 2026-04-27 | Python >=3.10; wheels; no mandatory dependencies | BSD-3-Clause and Public-Domain |
| [NumPy](https://pypi.org/project/numpy/) | 2.5.4 | 2026-10-10 | Latest requires >=3.12; cannot use a single unconstrained latest version for our matrix | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| [symspellpy](https://pypi.org/project/symspellpy/) | 6.10.0 | 2026-07-11 | Python >=3.10; universal wheel | MIT |
| [Pydantic](https://pypi.org/project/pydantic/) | 2.14.1 | 2026-10-11 | Python >=3.10; native pydantic-core and several other dependencies | MIT |
| [Numba](https://pypi.org/project/numba/) | 0.68.0 | 2026-09-30 | Python >=3.10; wheels; requires llvmlite and NumPy | BSD |

NumPy [2.3.5](https://pypi.org/project/numpy/2.3.5/) declares Python >=3.11 and 3.14
support. A selected NumPy experiment must choose a tested supported range or version
markers and establish an upgrade policy for 3.11. Default latest-version installation
must not silently exclude a supported Python.

All shortlisted operations can run offline after installation and with local artifacts.
Native packages add wheel/source-build requirements; retain the project's Windows/Linux
matrix and test network-disabled operation. Download size is not installed footprint or
RSS: those measurements have not been made for these candidates.

## Proposed evaluation scope after selection

1. Compare scalar vocabulary enumeration with RapidFuzz complete collection search on
   real Arabic terms, including unknown terms, large budgets and common short inputs.
2. Compare stdlib JSON, msgspec and orjson on source records, vocabulary, manifests and
   large typed results. Start without altering schemas, dataclasses or artifact bytes.
   Validate nested extras, nullable fields, boolean/integer distinctions, nonfinite values,
   large integers, JSON shape and metadata snapshot independence.
3. Compare instance-scoped stdlib LRU, current OrderedDict and cachetools under identical
   limits/hit rates, including empty/oversized neighbors and forced eviction.
4. If selected, isolate storage experiments: MARISA key lookup, Roaring candidate sets,
   NumPy vectorized checks and stdlib mmap/read-only views. Keep current resources as
   baseline; quantify build/reload latency, memory, size and compatibility/migration costs.

Every selected experiment must retain oracle agreement, complete references/occurrences,
no silent caps and offline operation. Measure whole-detector median/p95, startup, peak
RSS, footprint and maintenance costs. Then choose the replacements with evidence;
reusable-library status alone does not establish an improvement.

The maintainer selects candidates and authorizes evaluation/adoption before any runtime
dependency or artifact-format change. Existing implementations remain unchanged meanwhile.
