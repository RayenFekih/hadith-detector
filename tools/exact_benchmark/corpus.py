"""Verified Phase 2 input, stored compactly for comparable prototype experiments."""

import hashlib
import json
from array import array
from dataclasses import dataclass
from pathlib import Path

from hadith_detector._text import NORMALIZATION_VERSION, Token, tokenize


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Sequence:
    terms: array
    starts: array
    ends: array
    segments: array

    def __len__(self) -> int:
        return len(self.terms)

    def boundary(self, position: int) -> bool:
        return position in (0, len(self)) or (
            self.starts[position - 1],
            self.ends[position - 1],
        ) != (self.starts[position], self.ends[position])

    def window(self, start: int, size: int) -> bool:
        end = start + size
        return 0 <= start < end <= len(self) and self.segments[start] == self.segments[end - 1]


@dataclass
class Corpus:
    records: list[dict]
    sequences: list[Sequence]
    vocabulary: dict[str, int]
    fingerprint: str

    @classmethod
    def synthetic(cls, texts: list[str]) -> "Corpus":
        vocabulary: dict[str, int] = {}
        records = [
            {
                "hadith_key": f"fixture:{i + 1}",
                "collection": "fixture",
                "seq": i + 1,
                "text": text,
                "sunnah_url": None,
            }
            for i, text in enumerate(texts)
        ]
        sequences = [sequence(tokenize(text).tokens, vocabulary, True) for text in texts]
        return cls(records, sequences, vocabulary, hashlib.sha256(canonical(texts)).hexdigest())

    def query(self, text: str) -> Sequence:
        return sequence(tokenize(text).tokens, self.vocabulary, False)


def sequence(tokens: tuple[Token, ...], vocabulary: dict[str, int], add: bool) -> Sequence:
    ids = []
    for token in tokens:
        if add and token.term not in vocabulary:
            vocabulary[token.term] = len(vocabulary)
        ids.append(vocabulary.get(token.term, -1))
    return Sequence(
        array("i", ids),
        array("I", (t.start for t in tokens)),
        array("I", (t.end for t in tokens)),
        array("I", (t.segment for t in tokens)),
    )


def load_corpus(path: Path) -> Corpus:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("versions") != {
        "manifest": 1,
        "normalization": NORMALIZATION_VERSION,
        "records": 1,
        "tokens": 1,
    }:
        raise ValueError("Unsupported prepared-corpus formats")
    expected = {"records.jsonl", "tokens.jsonl", "validation.json"}
    if set(manifest.get("artifacts", {})) != expected:
        raise ValueError("Invalid prepared-corpus inventory")
    for name, checksum in manifest["artifacts"].items():
        if digest(path / name) != checksum:
            raise ValueError(f"Prepared-corpus checksum mismatch: {name}")
    records = [json.loads(line) for line in (path / "records.jsonl").open(encoding="utf-8")]
    if records != sorted(records, key=lambda r: (r["collection"], r["seq"])):
        raise ValueError("Records are not in deterministic collection/sequence order")
    vocabulary: dict[str, int] = {}
    sequences = []
    with (path / "tokens.jsonl").open(encoding="utf-8") as stream:
        for rid, line in enumerate(stream):
            row = json.loads(line)
            if rid >= len(records) or row["hadith_key"] != records[rid]["hadith_key"]:
                raise ValueError("Record/token identity mismatch")
            tokens = tuple(Token(**t) for t in row["tokens"])
            if tokens != tokenize(records[rid]["text"]).tokens:
                raise ValueError("Prepared token/span validation failed")
            sequences.append(sequence(tokens, vocabulary, True))
    if len(sequences) != len(records) or len({r["hadith_key"] for r in records}) != len(records):
        raise ValueError("Incomplete corpus or duplicate identities")
    fingerprint = hashlib.sha256(canonical(manifest["artifacts"])).hexdigest()
    return Corpus(records, sequences, vocabulary, fingerprint)


def validate_minimum(minimum: int) -> None:
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        raise ValueError("min_match_words must be a positive integer")
