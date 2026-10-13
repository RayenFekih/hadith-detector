"""Versioned compact resources: checksummed, little-endian, dependency-free."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ._text import NORMALIZATION_VERSION, Token

INDEX_VERSION = 1
MAGIC = b"HDIDX001"
HEADER = struct.Struct("<8sIIIIQ")
BLOCK = struct.Struct("<QI")
MAX_U32 = 2**32 - 1
# kind, bytes per row: directories use uint64 offsets and uint32 counts.
LAYOUTS = {
    "tokens.bin": (1, 16),
    "record-offsets.bin": (2, 8),
    "unigram-offsets.bin": (3, 12),
    "unigram-postings.bin": (4, 8),
    "trigram-keys.bin": (5, 12),
    "trigram-offsets.bin": (6, 12),
    "trigram-postings.bin": (7, 8),
}
RESOURCE_FILES = frozenset((*LAYOUTS, "records.jsonl", "vocabulary.json"))
CONFIG_FIELDS = (
    "source_fingerprint",
    "prepared_manifest_sha256",
    "source_artifacts",
    "source_dataset",
    "builder",
    "algorithm",
    "byte_order",
    "versions",
    "counts",
)


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _reject_number(value: str) -> None:
    raise ValueError(f"Invalid JSON number: {value}")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_number)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError(f"Invalid resource JSON: {path.name}") from exc


def integer(value: object, *, maximum: int | None = None) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        and (maximum is None or value <= maximum)
    )


def read_binary(path: Path) -> tuple[bytes, int]:
    with path.open("rb") as stream:
        raw = stream.read(HEADER.size)
        if len(raw) != HEADER.size:
            raise ValueError(f"Truncated binary header: {path.name}")
        magic, version, kind, width, flags, count = HEADER.unpack(raw)
        if (
            magic != MAGIC
            or version != INDEX_VERSION
            or flags != 1
            or (kind, width) != LAYOUTS[path.name]
        ):
            raise ValueError(f"Incompatible binary header: {path.name}")
        if path.stat().st_size != HEADER.size + count * width:
            raise ValueError(f"Binary length/count mismatch: {path.name}")
        return stream.read(), count


def native_array(code: str, data: bytes) -> array[int]:
    result: array[int] = array(code)
    if result.itemsize != (4 if code == "I" else 8):
        raise ValueError("Unsupported platform integer widths")
    result.frombytes(data)
    if sys.byteorder != "little":
        result.byteswap()
    return result


def directory(data: bytes) -> tuple[array[int], array[int]]:
    offsets: array[int] = array("Q")
    counts: array[int] = array("I")
    for offset, count in BLOCK.iter_unpack(data):
        offsets.append(offset)
        counts.append(count)
    return offsets, counts


@dataclass(frozen=True)
class Sequence:
    terms: memoryview
    starts: memoryview
    ends: memoryview
    segments: memoryview

    def __len__(self) -> int:
        return len(self.terms)

    def boundary(self, position: int) -> bool:
        return position in (0, len(self)) or bool(
            (self.starts[position - 1], self.ends[position - 1])
            != (self.starts[position], self.ends[position])
        )

    def window(self, start: int, size: int) -> bool:
        end = start + size
        return bool(
            0 <= start < end <= len(self) and self.segments[start] == self.segments[end - 1]
        )


def query_sequence(tokens: tuple[Token, ...], vocabulary: dict[str, int]) -> Sequence:
    return Sequence(
        memoryview(array("q", (vocabulary.get(t.term, -1) for t in tokens))),
        memoryview(array("I", (t.start for t in tokens))),
        memoryview(array("I", (t.end for t in tokens))),
        memoryview(array("I", (t.segment for t in tokens))),
    )


def validate_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("Source record must be an object")
    for field in ("hadith_key", "collection", "language", "hadith_number"):
        if not isinstance(record.get(field), str) or not record[field]:
            raise ValueError(f"Invalid source identity field: {field}")
    if record["hadith_key"] != f"{record['collection']}:{record['hadith_number']}":
        raise ValueError("Source identity/number mismatch")
    for field in ("urn", "seq", "number_sort", "book_number", "in_book_number", "n_grades"):
        if not integer(record.get(field)):
            raise ValueError(f"Invalid source integer field: {field}")
    if not record["urn"] or not record["seq"] or record["language"] != "ar":
        raise ValueError("Invalid source sequence/URN/language")
    for field in ("sunnah_url", "grade_summary"):
        if field not in record or (
            record[field] is not None and not isinstance(record[field], str)
        ):
            raise ValueError(f"Invalid source nullable field: {field}")
    if not isinstance(record.get("text"), str) or not isinstance(record.get("is_muallaq"), bool):
        raise ValueError("Invalid source text/flag")
    if not isinstance(record.get("grades"), list) or len(record["grades"]) != record["n_grades"]:
        raise ValueError("Invalid source grades")
    for grade in record["grades"]:
        if not isinstance(grade, dict) or any(
            not isinstance(grade.get(k), str) for k in ("grade", "grader")
        ):
            raise ValueError("Invalid source nested grade")
    return cast(dict[str, Any], record)


@dataclass(frozen=True)
class Resources:
    records: list[dict[str, Any]]
    sequences: list[Sequence]
    vocabulary: dict[str, int]
    keys: dict[str, int]
    unigram_offsets: array[int]
    unigram_counts: array[int]
    unigram_postings: array[int]
    trigrams: dict[tuple[int, int, int], int]
    trigram_offsets: array[int]
    trigram_counts: array[int]
    trigram_postings: array[int]

    @classmethod
    def load(cls, root: Path) -> Resources:
        manifest = read_json(root / "manifest.json")
        if not isinstance(manifest, dict) or manifest.get("format") != "hadith-detector-index":
            raise ValueError("Invalid index manifest")
        versions = {
            "index": INDEX_VERSION,
            "manifest": 1,
            "records": 1,
            "tokens": 1,
            "normalization": NORMALIZATION_VERSION,
        }
        if (
            manifest.get("versions") != versions
            or manifest.get("algorithm") != "trigram+unigram"
            or manifest.get("byte_order") != "little"
        ):
            raise ValueError("Incompatible index format/normalization/algorithm")
        if not all(name in manifest for name in CONFIG_FIELDS):
            raise ValueError("Incomplete runtime build provenance")
        fingerprint = hashlib.sha256(
            canonical({name: manifest[name] for name in CONFIG_FIELDS})
        ).hexdigest()
        if manifest.get("build_fingerprint") != fingerprint:
            raise ValueError("Invalid runtime build fingerprint")
        counts = manifest.get("counts")
        count_names = {"records", "tokens", "vocabulary", "trigram_keys", "trigram_postings"}
        if (
            not isinstance(counts, dict)
            or set(counts) != count_names
            or not all(integer(c, maximum=MAX_U32) for c in counts.values())
            or not counts["records"]
        ):
            raise ValueError("Invalid index counts or unsupported bounds")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or set(artifacts) != RESOURCE_FILES:
            raise ValueError("Invalid runtime resource inventory")
        for name, expected in artifacts.items():
            if not isinstance(expected, str) or checksum(root / name) != expected:
                raise ValueError(f"Resource checksum mismatch: {name}")
        records = []
        with (root / "records.jsonl").open(encoding="utf-8") as stream:
            try:
                for line in stream:
                    records.append(validate_record(json.loads(line, parse_constant=_reject_number)))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("Invalid records JSONL") from exc
        if (
            len(records) != counts["records"]
            or len({r["hadith_key"] for r in records}) != len(records)
            or len({r["urn"] for r in records}) != len(records)
            or len({(r["collection"], r["seq"]) for r in records}) != len(records)
            or records != sorted(records, key=lambda r: (r["collection"], r["seq"]))
        ):
            raise ValueError("Invalid record count, order or duplicate identities")
        words = read_json(root / "vocabulary.json")
        if (
            not isinstance(words, list)
            or len(words) != counts["vocabulary"]
            or not all(isinstance(w, str) and w for w in words)
            or len(set(words)) != len(words)
        ):
            raise ValueError("Invalid vocabulary")
        vocabulary = {word: i for i, word in enumerate(words)}
        payload, size = read_binary(root / "tokens.bin")
        if size != counts["tokens"]:
            raise ValueError("Token count mismatch")
        token_data = native_array("I", payload)
        del payload
        view = memoryview(token_data)
        payload, size = read_binary(root / "record-offsets.bin")
        boundaries = native_array("Q", payload)
        if (
            size != len(records) + 1
            or boundaries[0] != 0
            or boundaries[-1] != counts["tokens"]
            or any(a > b for a, b in zip(boundaries, boundaries[1:], strict=False))
        ):
            raise ValueError("Invalid record token boundaries")
        sequences = []
        expected_trigrams = 0
        for rid, record in enumerate(records):
            a, b = boundaries[rid] * 4, boundaries[rid + 1] * 4
            source = Sequence(*(view[a + c : b : 4] for c in range(4)))
            previous = None
            for position in range(len(source)):
                word, start, end, segment = (
                    int(column[position])
                    for column in (source.terms, source.starts, source.ends, source.segments)
                )
                if word >= len(words) or not 0 <= start < end <= len(record["text"]):
                    raise ValueError("Invalid token ID or original character span")
                if previous is not None:
                    ps, pe, pg = previous
                    if (
                        start < ps
                        or end < pe
                        or segment < pg
                        or (start < pe and (start, end, segment) != previous)
                    ):
                        raise ValueError("Invalid token span/segment order")
                previous = start, end, segment
                if position >= 2 and source.segments[position - 2] == segment:
                    expected_trigrams += 1
            sequences.append(source)
        if expected_trigrams != counts["trigram_postings"]:
            raise ValueError("Invalid trigram occurrence count")
        payload, size = read_binary(root / "unigram-offsets.bin")
        u_offsets, u_counts = directory(payload)
        if size != len(words):
            raise ValueError("Invalid unigram directory count")
        payload, size = read_binary(root / "unigram-postings.bin")
        u_postings = native_array("Q", payload)
        if size != counts["tokens"]:
            raise ValueError("Incomplete unigram occurrence inventory")
        payload, size = read_binary(root / "trigram-keys.bin")
        t_keys = native_array("I", payload)
        if size != counts["trigram_keys"]:
            raise ValueError("Invalid trigram key count")
        trigrams: dict[tuple[int, int, int], int] = {}
        previous_key = None
        for i in range(size):
            key = (t_keys[i * 3], t_keys[i * 3 + 1], t_keys[i * 3 + 2])
            if any(k >= len(words) for k in key) or (
                previous_key is not None and key <= previous_key
            ):
                raise ValueError("Invalid trigram key order/bounds")
            trigrams[key] = i
            previous_key = key
        payload, size = read_binary(root / "trigram-offsets.bin")
        t_offsets, t_counts = directory(payload)
        if size != len(trigrams):
            raise ValueError("Invalid trigram directory count")
        payload, size = read_binary(root / "trigram-postings.bin")
        t_postings = native_array("Q", payload)
        if size != expected_trigrams:
            raise ValueError("Incomplete trigram occurrence inventory")
        instance = cls(
            records,
            sequences,
            vocabulary,
            {r["hadith_key"]: i for i, r in enumerate(records)},
            u_offsets,
            u_counts,
            u_postings,
            trigrams,
            t_offsets,
            t_counts,
            t_postings,
        )
        instance._validate_postings()
        return instance

    def _validate_postings(self) -> None:
        tables = (
            (
                [(i,) for i in range(len(self.vocabulary))],
                self.unigram_offsets,
                self.unigram_counts,
                self.unigram_postings,
            ),
            (list(self.trigrams), self.trigram_offsets, self.trigram_counts, self.trigram_postings),
        )
        for keys, offsets, counts, postings in tables:
            consumed = 0
            for index, key in enumerate(keys):
                offset, count = offsets[index], counts[index]
                if offset != consumed or not count or offset + count > len(postings):
                    raise ValueError("Invalid posting block bounds/coverage")
                previous = -1
                for packed in postings[offset : offset + count]:
                    rid, pos = packed >> 32, packed & MAX_U32
                    if packed <= previous or rid >= len(self.records):
                        raise ValueError("Invalid posting order/record")
                    source = self.sequences[rid]
                    if (
                        not source.window(pos, len(key))
                        or tuple(source.terms[pos : pos + len(key)]) != key
                    ):
                        raise ValueError("Invalid posting token position/key/segment")
                    previous = packed
                consumed += count
            if consumed != len(postings):
                raise ValueError("Incomplete posting block coverage")
