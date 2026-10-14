# Public API (Phase 5A)

The target is one combined Sahih Bukhari/Sahih Muslim corpus. Until Phase 7,
every constructor and convenience call requires an explicit local `index_dir`.
Nothing is downloaded, rebuilt or bundled by this milestone. HTML annotation
is reserved for Phase 5B and is not exported.

## Construction and configuration

```python
from hadith_detector import DetectorConfig, HadithDetector

detector = HadithDetector(
    "data/runtime-index-v2-a",
    config=DetectorConfig(min_match_words=5, max_errors=1, max_missing_words=1),
)
assert detector.index_dir.is_absolute()  # read-only resolved pathlib.Path
matches = detector.detect("إنما الأعمال بالنيات وإنما لكل امرئ ما نوى")
strict = detector.detect(
    "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى",
    max_errors=0,
    max_missing_words=0,
)
```

`HadithDetector.from_directory(index_dir, config=None)` remains supported.
Construction eagerly validates and loads MARISA v2 resources once. `config`
is a read-only frozen `DetectorConfig`. Defaults are five words and zero edits
and omissions. Overrides are keyword-only and never change instance defaults:
omitted values and explicit `None` inherit; explicit `0` disables the configured
error or omission tolerance. The word minimum must be a positive integer;
budgets must be nonnegative integers. Booleans are rejected. Settings are
validated even for empty text, which otherwise returns an empty list.

Compatibility changes: the formerly internal `HadithDetector(Resources)`
constructor now takes a directory; callers using `from_directory()` need no
change. Explicit `None`, formerly invalid for detection settings, now inherits.
Python 3.11–3.14, index format 2, normalization version 1, matching rules and
runtime dependency requirements are unchanged.

## Convenience calls and lifetime

```python
from hadith_detector import clear_cache, detect, get_hadith

matches = detect(
    "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى",
    index_dir="data/runtime-index-v2-a",
    config=DetectorConfig(max_errors=1),
    max_errors=0,
)
record = get_hadith("bukhari:1", index_dir="data/runtime-index-v2-a")
clear_cache()
```

One synchronized entry caches a detector by resolved directory. Repeated calls
reuse it; a different directory replaces it. Supplied configuration applies
only to that call; omitted configuration uses library defaults, never the
preceding call's defaults. Importing the package loads no corpus. Failed
initialization does not replace a valid entry.

Resource directories must remain immutable while in use. There is no file
watching, automatic reload or per-call checksum verification. `clear_cache()`
forgets the reference; it does not interrupt active calls or invalidate an
explicit instance. Creating the next cached instance validates resources again.
There is no global dataset configuration or configurable cache capacity.

## Thread safety and costs

A reentrant per-instance lock protects detection, lazy fuzzy state and source
lookup. Concurrent calls on the same instance execute sequentially. Independent
instances have independent fuzzy caches; this API provides no parallel or async
execution facility. The convenience-cache lock protects creation only and is
released before running detection. Clearing the cache can complete while an
existing detection is still running.

The earlier MARISA measurements found about 78 MiB less steady memory with
about 1.34 seconds additional one-time validated initialization. These are
historical measurements, not new Phase 5A performance claims. Long-lived
instances amortize loading. Integrity checks remain complete; locking does not
weaken validation or alter matching.

## Results and serialization

The existing [result field table](runtime-index.md#results-and-source-preservation)
and dictionary shapes are unchanged. Each exported result dataclass provides
`to_dict()` and `from_dict(payload)`:

```python
import json
from hadith_detector import Detection

if matches:
    payload = json.loads(json.dumps(matches[0].to_dict(), ensure_ascii=False))
    restored = Detection.from_dict(payload)
    assert restored == matches[0]
```

References, occurrences and traces restore as tuples. Records serialize their
original fields flat, including additional metadata and nullable URLs. Frozen
attributes may contain mutable metadata snapshots; serialization and restoration
copy them independently of the input payload and detector resources.

Deserialization validates required/unknown structural fields, types, finite JSON
metadata, nonnegative counts, nonempty exclusive-end spans and available text
lengths/slices. It checks ordered token traces, internal omissions, costs, word
counts and supporting occurrence relationships. Shared symbol spans are valid.
Zero-cost empty traces remain valid for manually constructed older models;
nonzero costs require a trace. Missing optional cost/trace fields use existing
zero/empty defaults. Unknown narration metadata is preserved; unknown structural
fields on other models are rejected.

These checks do not tokenize, consult resources, reproduce matching or authenticate
a narration. Standalone models can check only information present in that model;
parent models add available substring and count checks. Direct dataclass constructors
remain unchanged; `from_dict()` is the validated restoration path.

## Exceptions and limitations

Non-string text/source keys and invalid configuration objects raise `TypeError`.
Invalid word/budget settings raise `ValueError`. Unknown source keys raise
`KeyError`. Missing resources raise filesystem errors; incompatible versions,
checksums and structural corruption raise `ValueError`. Deserialization rejects
invalid types with `TypeError` and invalid relationships/shapes with `ValueError`.

Offsets slice the original Python strings, with exclusive ends. Complete source
identities, occurrences and canonical alignments are preserved. Textual support
does not independently authenticate Hadith; common chains and embedded Quranic
passages can match source text. Annotation, independent real-world evaluation and
bundled-resource installation remain later work.
