# Focused library evaluation

Repository-only benchmarks compare adapters with the unchanged Phase 4B detector.
Production source, runtime requirements, `uv.lock`, normalization, index format and
Python 3.11–3.14 support remain unchanged. No Phase 5 work is included.

## Reproduction

Create an isolated environment using Python 3.14; dependencies are pinned independently
in `tools/library_benchmark/requirements.txt`. NumPy 2.3.5 supports the retained matrix.
Do not install these research dependencies into the supported contributor/runtime groups.

```sh
uv venv --python 3.14 .cache/library-env
uv pip install --python .cache/library-env/Scripts/python.exe -r tools/library_benchmark/requirements.txt
uv build --wheel --no-sources --out-dir .cache/library-current-wheel
uv pip install --python .cache/library-env/Scripts/python.exe .cache/library-current-wheel/<wheel-name>.whl
.cache/library-env/Scripts/python.exe -m tools.library_benchmark prepare --index-dir data/runtime-index-a --evidence-dir data/phase4-measured --output-dir data/library-evaluation-final
.cache/library-env/Scripts/python.exe -m tools.library_benchmark run --index-dir data/runtime-index-a --output-dir data/library-evaluation-final
```

Use `bin/python` on Linux. Obtain/install the wheels before offline testing. Preparation
and performance workers use verified local resources and saved oracle evidence only;
workers forbid network sockets. Choose a new output directory for preparation. Large
query/report/prototype artifacts remain ignored. Production distributions are not changed
to carry experimental dependencies or trie files.

Run synthetic checks with the isolated environment's Python:

```sh
.cache/library-env/Scripts/python.exe -m pytest tests/test_library_benchmark.py
```

These tests skip when the experiment libraries are absent. Normal project quality,
preprocessing and packaging checks still use the existing supported environments.

## Scope and controls

The deterministic suite has 39 queries: 20 representative Phase 4 cases, three real
long quotations, and 16 Phase 3 exact cases. It includes short/no-anchor fuzzy searches,
common chains, combined budgets, destroyed seeds, barriers/negatives, normalization,
multiple passages, and approximately 1,024-/4,096-token paragraph inputs. Real long
quotations use 99, 249 and 499 words, with a character insertion and an internal omission.

Saved Phase 3/4 independent oracle evidence establishes complete expectations for the
representative cases. Preparation additionally scans the full corpus with the independent
Python oracle for the three long passages, using their entire known-supported input length
as the oracle minimum. The runtime still uses minimum 5; full-input support dominates
all shorter spans, allowing a full independent reference/occurrence comparison.

Every worker runs in a fresh subprocess, sequentially to avoid another candidate's CPU
or retained index allocations. Each query gets one application-cache-cold call, followed
by three warm repetitions. The first fuzzy call also includes lazy helper setup. OS
filesystem caches are not flushed: resource loading is process-cold, not a claimed
uncached-disk measurement. Warm repetitions are within each query, not a production
traffic model. Results must agree on spans, costs, identities, all occurrences and traces
on every repetition. Serialization round trips and repeated bytes are also checked.

Detection timing includes normalization, retrieval, verification, typed results and full
metadata snapshots. Serialization timing separately includes existing `.to_dict()` shape
conversion and encoding. The combined API-to-JSON pipeline is their sum. Correctness
hashing and decoder round-trip checks are outside these timed intervals.

Process RSS is recorded before imports, after resource/adaptor initialization, and after
the detection suite and garbage collection. The process peak captured at the end of that
suite includes initialization, result conversion and correctness-harness allocations;
it is not pure verifier memory. A separate final/peak measurement after microbenchmarks
includes their temporary full-corpus JSON allocations. Do not conflate those scopes.

Record dependency import time/RSS and installed-file size, using distribution metadata;
installed-file size excludes unrecorded bytecode. All candidates coexist in the isolated
environment, but workers import only the selected candidate. A dependency present on disk
is not evidence that its memory is loaded in a baseline process.

## Compared adapters

- `baseline`: unchanged detector, standard JSON and Python candidate sets.
- `rf-iter` / `rf-extract`: complete RapidFuzz collection lookup with unit-cost
  Levenshtein, no preprocessing, and no result cap. Length buckets and bounded neighbor
  cache remain. Word-pair cache is bypassed inside native collection calls, a measured
  trade-off rather than a claim of identical kernel-call counts.
- `numpy`: packed candidate positions, vectorized valid omission offsets and `unique`.
  Original postings are viewed without a copy; available source positions bound large
  budgets. Verification remains the existing implementation.
- `roaring`: `BitMap64` candidate positions instead of tuple sets. Record bits remain
  separate from within-record displacement; no shift crosses a narration.
- `numpy-roaring`: vectorized position production followed by Roaring deduplication.
- `msgspec` / `orjson`: resource JSON decoding and API dictionary encoding. Existing
  validators, dataclasses and complete metadata remain. Nonfinite values are explicitly
  rejected. orjson conservatively falls back to stdlib for long digit runs and integers
  outside its encoder range, preserving the existing arbitrary-integer policy. Adapter
  costs are included. This is not a public-model or typed-schema redesign.
- `marisa` / `marisa-mmap`: static native record tries for vocabulary IDs and trigram
  block IDs, with unchanged posting arrays and verifier. Existing resources are validated
  first, then lookup containers replaced within the worker. Thus total startup includes
  the compatibility bridge and experimental trie construction. Native reload/mmap time
  is separately measured and must not be called complete detector startup.

MARISA trial files preserve IDs through explicit values and encode trigram IDs as fixed
width hexadecimal keys. Repeated native builds must produce identical bytes. Native
prototype files are separate ignored artifacts, not a replacement production format.

Microbenchmarks measure uncached vocabulary lookup, candidate generation/deduplication
including deterministic output materialization, and decoding/encoding the full source
records, vocabulary and manifest. Candidate-position serialization is a separate container
comparison; it does not imply a new persistent index. Current JSON artifacts must retain
identical bytes on this pinned corpus. General numeric/metadata behavior is checked with
synthetic cases too; corpus parity alone does not establish all possible codec equivalence.

`tools.library_benchmark.kernels` separately measures raw JSON kernels on validated inputs,
without claiming those kernels satisfy the full numeric policy. `order_control` runs
the same suite with sorted Python candidate verification, isolating part of the effect
that sorted NumPy/Roaring containers introduce. A repeated baseline checks timing drift.

See [the reuse survey](library-review.md) for sources and
[measured recommendations](library-benchmark-results.md) for the review decision.
