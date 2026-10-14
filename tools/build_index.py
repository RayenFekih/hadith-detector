"""Build deterministic compact runtime resources from verified Phase 2 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import platform
import shutil
import sys
import tempfile
import time
import unicodedata
from array import array
from importlib.metadata import version
from pathlib import Path

import marisa_trie

from hadith_detector._marisa import OPTIONS, encode_trigram
from hadith_detector._resources import (
    BLOCK,
    HEADER,
    INDEX_VERSION,
    LAYOUTS,
    MAGIC,
    MAX_U32,
    RESOURCE_FILES,
    Resources,
    canonical,
    checksum,
    read_json,
)
from hadith_detector._text import NORMALIZATION_VERSION
from tools.exact_benchmark.corpus import load_corpus
from tools.exact_benchmark.indexes import Index

ROOT = Path(__file__).resolve().parents[1]


def write_array(path: Path, values: array, rows: int) -> None:
    kind, width = LAYOUTS[path.name]
    if values.itemsize not in (4, 8) or len(values) * values.itemsize != rows * width:
        raise ValueError("Unsupported binary array layout")
    if sys.byteorder != "little":
        values = array(values.typecode, values)
        values.byteswap()
    with path.open("wb") as stream:
        stream.write(HEADER.pack(MAGIC, INDEX_VERSION, kind, width, 1, rows))
        values.tofile(stream)


def write_table(root: Path, name: str, keys: list[tuple[int, ...]], table: dict) -> None:
    offsets = root / f"{name}-offsets.bin"
    postings = root / f"{name}-postings.bin"
    kind, width = LAYOUTS[offsets.name]
    total = sum(len(table[key]) for key in keys)
    with offsets.open("wb") as directory, postings.open("wb") as payload:
        directory.write(HEADER.pack(MAGIC, INDEX_VERSION, kind, width, 1, len(keys)))
        pkind, pwidth = LAYOUTS[postings.name]
        payload.write(HEADER.pack(MAGIC, INDEX_VERSION, pkind, pwidth, 1, total))
        consumed = 0
        for key in keys:
            values = table[key]
            if len(values) > MAX_U32:
                raise ValueError("Posting block exceeds uint32 count bounds")
            directory.write(BLOCK.pack(consumed, len(values)))
            if sys.byteorder == "little":
                values.tofile(payload)
            else:
                copy = array("Q", values)
                copy.byteswap()
                copy.tofile(payload)
            consumed += len(values)


def build(corpus_dir: Path, output_dir: Path) -> dict:
    if sys.version_info[:2] != (3, 14):
        raise ValueError("Runtime index builds require the pinned Python 3.14 environment")
    if version("marisa-trie") != "1.4.1":
        raise ValueError("Index builds require marisa-trie 1.4.1")
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ValueError("Output directory already exists; choose a new directory")
    corpus = load_corpus(corpus_dir)
    index = Index(corpus, "ngram3")
    total = sum(len(s) for s in corpus.sequences)
    if max(len(corpus.records), len(corpus.vocabulary), total, len(index.ngrams)) > MAX_U32:
        raise ValueError("Corpus exceeds supported uint32 bounds")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".index-build-", dir=output_dir.parent))
    try:
        shutil.copyfile(corpus_dir / "records.jsonl", staging / "records.jsonl")
        words = sorted(corpus.vocabulary, key=corpus.vocabulary.__getitem__)
        marisa_trie.RecordTrie(
            "<I", ((word, (wid,)) for wid, word in enumerate(words)), **OPTIONS
        ).save(str(staging / "vocabulary.marisa"))
        fields = array("I")
        boundaries = array("Q", [0])
        for source in corpus.sequences:
            if len(source) > MAX_U32:
                raise ValueError("Record exceeds uint32 token-position bounds")
            for i in range(len(source)):
                fields.extend(
                    (source.terms[i], source.starts[i], source.ends[i], source.segments[i])
                )
            boundaries.append(boundaries[-1] + len(source))
        write_array(staging / "tokens.bin", fields, total)
        write_array(staging / "record-offsets.bin", boundaries, len(boundaries))
        write_table(staging, "unigram", [(i,) for i in range(len(words))], index.unigrams)
        keys = sorted(index.ngrams)
        marisa_trie.RecordTrie(
            "<I", ((encode_trigram(key), (block,)) for block, key in enumerate(keys)), **OPTIONS
        ).save(str(staging / "trigrams.marisa"))
        write_table(staging, "trigram", keys, index.ngrams)
        count_grams = sum(len(v) for v in index.ngrams.values())
        if count_grams > MAX_U32:
            raise ValueError("Corpus exceeds supported trigram-count bounds")
        code_files = (
            "tools/build_index.py",
            "src/hadith_detector/_marisa.py",
            "tools/exact_benchmark/corpus.py",
            "tools/exact_benchmark/indexes.py",
            "src/hadith_detector/_resources.py",
            "src/hadith_detector/_text.py",
        )
        prepared = read_json(corpus_dir / "manifest.json")
        source_lock = prepared.get("source_lock")
        config = {
            "source_fingerprint": corpus.fingerprint,
            "prepared_manifest_sha256": checksum(corpus_dir / "manifest.json"),
            "source_artifacts": prepared["artifacts"],
            "source_dataset": {
                "repository": source_lock["repository"],
                "revision": source_lock["revision"],
                "configurations": [c["name"] for c in source_lock["configs"]],
            }
            if source_lock is not None
            else None,
            "builder": {
                "python": platform.python_version(),
                "marisa_trie": version("marisa-trie"),
                "native_settings": OPTIONS,
                "dependency_lock_sha256": checksum(ROOT / "uv.lock"),
                "unicode": unicodedata.unidata_version,
                "sources": {
                    name: hashlib.sha256(
                        (ROOT / name).read_text(encoding="utf-8").encode("utf-8")
                    ).hexdigest()
                    for name in code_files
                },
            },
            "algorithm": "trigram+unigram",
            "byte_order": "little",
            "versions": {
                "index": INDEX_VERSION,
                "manifest": 1,
                "records": 1,
                "tokens": 1,
                "normalization": NORMALIZATION_VERSION,
            },
            "counts": {
                "records": len(corpus.records),
                "tokens": total,
                "vocabulary": len(words),
                "trigram_keys": len(keys),
                "trigram_postings": count_grams,
            },
        }
        manifest = {
            "format": "hadith-detector-index",
            **config,
            "build_fingerprint": hashlib.sha256(canonical(config)).hexdigest(),
            "artifacts": {name: checksum(staging / name) for name in sorted(RESOURCE_FILES)},
        }
        (staging / "manifest.json").write_bytes(canonical(manifest))
        Resources.load(staging)
        if output_dir.exists():
            raise ValueError("Output appeared during build; refusing overwrite")
        staging.rename(output_dir)
        return manifest
    finally:
        if staging.exists():
            if staging.resolve().parent != output_dir.parent or not staging.name.startswith(
                ".index-build-"
            ):
                raise ValueError("Refusing cleanup outside the staging parent")
            shutil.rmtree(staging)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        manifest = build(args.corpus_dir.resolve(), args.output_dir)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"index build: passed ({time.perf_counter() - started:.2f}s); {manifest['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
