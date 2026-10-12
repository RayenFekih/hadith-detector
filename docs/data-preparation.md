# Data preparation (Phase 2)

The pipeline preserves the complete `bukhari-ar` and `muslim-ar` records from
QuranLab revision `cc6972dae1f46f5f5e2b65e877d24c4539bc4391`. It does not extract
Matn/Isnad, repair text, deduplicate narrations, create indexes, or detect quotations.
The public package still exports only its version; `_text` is private shared infrastructure.

## Commands

From an installed development checkout, use Python 3.14:

```sh
uv sync --locked --group data
uv run --frozen --group data python -m tools.prepare_data fetch --source-dir data/source-quranlab
uv run --frozen --group data python -m tools.prepare_data build --source-dir data/source-quranlab --output-dir data/build-a
uv run --frozen --group data python -m tools.prepare_data verify --source-dir data/source-quranlab --output-dir data/build-a
uv run --frozen --group data python -m tools.prepare_data build --source-dir data/source-quranlab --output-dir data/build-b
```

`fetch` downloads only source-lock filenames at the full pinned revision and verifies
SHA-256 hashes before accepting the snapshot. Existing source directories are reused
only if every pinned file matches. Incomplete/corrupted directories are rejected;
choose a new directory to retry without overwriting or altering old research.
No account or token is required for these public files.

`build` and `verify` do not call the Hub or use network services. With dependencies
already installed, add `--offline` to uv to prevent environment synchronization
from using the network. Both commands require explicit local source and output
directories. The optional `--lock` argument allows synthetic test locks or an
explicitly reviewed future source lock.

Builds refuse existing output directories. Acquisition and builds use sibling
temporary directories and rename them after successful validation; failed staging
directories are cleaned. Diagnostics go to stderr, failures return a nonzero exit
code, and elapsed time is printed only to the console.

## Validation and source preservation

The pinned counts are 7,580 Bukhari and 7,360 Muslim records. Validate unique keys
and URNs, positive unique sequence numbers, collection/language, numbering, required
field types, nullable URLs, nested grades, and JSON-compatible additional fields.
Unknown source fields are retained without renaming or coercion.

The actual pinned sequences have gaps (9 Bukhari, 203 Muslim), despite the general
dataset card's contiguous-sequence description. Preserve and report these gaps;
do not renumber, infer records, or reject otherwise valid source identities.
Duplicate text remains separate under every original identity.

Source text is never modified. Empty strings are retained with zero tokens and a
warning. Damaged text is retained, flagged by identifier and offsets, and tokenized
on either side of a matching barrier. URL nulls stay null. Required text must be a
string; null text is a schema error, not silently converted to an empty string.

## Artifact schemas

All artifacts use UTF-8, LF endings, sorted object keys, compact JSON separators,
and no NaN/infinite values. JSONL contains one record per line, ordered by collection
then original sequence. Dictionary key order changes; original field values do not.

- `records.jsonl`: original source objects, preserving every field and value.
- `tokens.jsonl`: `{hadith_key, tokens: [{term, start, end, segment}, ...]}`.
  Array index is token position; segment equality is required for matching.
- `validation.json`: version, integrity result, collection/null counts, sequence gaps,
  exact duplicate-text groups, token counts, warnings and affected identifiers.
  Duplicate groups use SHA-256 of the unchanged text and retain all source keys.
- `manifest.json`: source lock, independent format versions, environment and code
  fingerprints, build configuration, build fingerprint, and other artifact checksums.
  The manifest is not self-hashed; external comparison hashes all four output files.

Records, tokens, manifest, validation report, and normalization versions start at 1.
No index-format version exists yet. Verification checks versions and fingerprints,
checksums, and regenerated canonical records, tokens and report against the local
source. It catches altered spans even if artifact hashes were updated manually.

## Normalization and spans

Version 1 uses standard-library Unicode NFKC normalization on original Arabic
base/combining-mark clusters. It removes Arabic marks and tatweel, maps alif variants
to `ا`, `ة → ه`, and `ى/ی → ي`, and preserves `ؤ` and `ئ`. Canonically decomposed
hamza letters are composed before diacritics are removed. No stemming, clitic
segmentation, stopword removal, or joining standalone `و` is performed.

Whitespace and Unicode punctuation split words without splitting segments.
Direction marks, bidi controls and joining controls are ignored; unsupported
controls (including zero-width space), numbers, foreign letters, symbols/emoji and
replacement characters split segments. One-letter Arabic words remain tokens.
Orphan Arabic marks are reported and ignored; non-Arabic combining marks are barriers.

Arabic presentation forms and ligatures expand. `ﷲ` becomes `الله`; `ﷺ` becomes
the four normalized words `صلي الله عليه وسلم`. These four tokens share the original
symbol span and never merge into adjacent words. The future detector must consume
whole expansions: never begin/end between tokens sharing an identical span.
One-word ligatures remain one written-word token.

Offsets are Python codepoint indices with exclusive ends, not bytes or UTF-16 units.
Spans include attached marks and ignored controls within/trailing a word. They map
directly to original slices; expanded token terms can differ from those slices.
The complete original narration remains in `records.jsonl` for reference retrieval.

## Reproducibility and dependency boundaries

The manifest records the exact Python patch version and implementation, Unicode
version, Hub/PyArrow versions, uv.lock hash, normalization/pipeline source hashes,
source lock, and configuration. Source-code hashes normalize checkout line endings.
Timestamps, paths, host names and timings do not enter artifacts.

For identical source bytes, code, configuration, lockfile and recorded environment,
two builds must be byte-identical. Cross-Python build identity is not promised;
builds require Python 3.14. Normalization tests run on Python 3.11–3.14. All future
runtime normalization will reuse this module.

`huggingface-hub` and `pyarrow` belong to the `data` development group, not runtime
requirements. The wheel contains only library code and the typing marker; the sdist
also contains tools, tests, the source lock and documentation. Neither bundles raw
Parquet or generated artifacts. Large files stay ignored under data; no LFS/DVC or
release upload is introduced. Code is MIT; approved data provenance and credits
are recorded separately in [data/README.md](../data/README.md).

Run all Phase 2 checks with `uv run --frozen --group data pytest`, Ruff and strict
package mypy. CI uses synthetic Parquet inputs only. Full-corpus acceptance requires
two independently built directories, byte comparison of all four outputs, and
offline verification of both. See [acceptance evidence](phase2-validation.md).
