"""Concrete prebuilt native lookups with complete ID and mapping validation."""

from __future__ import annotations

from array import array
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import marisa_trie  # type: ignore[import-not-found]

OPTIONS = {
    "num_tries": marisa_trie.DEFAULT_NUM_TRIES,
    "cache_size": marisa_trie.DEFAULT_CACHE,
    "order": marisa_trie.WEIGHT_ORDER,
    "binary": False,
}


def encode_trigram(key: tuple[int, ...]) -> str:
    return "".join(f"{wid:08x}" for wid in key)


class WordLookup:
    def __init__(self, trie: Any) -> None:
        self.trie = trie

    def __len__(self) -> int:
        return int(len(self.trie))

    def get(self, term: str, default: int = -1) -> int:
        values = self.trie.get(term)
        return int(values[0][0]) if values else default

    def items(self) -> Iterator[tuple[str, int]]:
        for word, value in self.trie.iteritems():
            yield word, int(value[0])


class TrigramLookup:
    def __init__(self, trie: Any) -> None:
        self.trie = trie

    def __len__(self) -> int:
        return int(len(self.trie))

    def get(self, key: tuple[int, ...]) -> int | None:
        if any(wid < 0 for wid in key):
            return None
        values = self.trie.get(encode_trigram(key))
        return int(values[0][0]) if values else None


def load_tries(
    root: Path, counts: Mapping[str, int]
) -> tuple[WordLookup, TrigramLookup, array[int]]:
    try:
        words = marisa_trie.RecordTrie("<I").load(str(root / "vocabulary.marisa"))
        grams = marisa_trie.RecordTrie("<I").load(str(root / "trigrams.marisa"))
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("Invalid native MARISA resource") from exc
    if len(words) != counts["vocabulary"] or len(grams) != counts["trigram_keys"]:
        raise ValueError("Native key counts disagree with manifest")
    seen = bytearray(len(words))
    for word, value in words.iteritems():
        wid = value[0]
        if not word or not 0 <= wid < len(seen) or seen[wid]:
            raise ValueError("Invalid/duplicate vocabulary IDs")
        seen[wid] = 1
    if not all(seen):
        raise ValueError("Incomplete vocabulary ID coverage")
    seen = bytearray(len(grams))
    keys = array("I", [0]) * (3 * len(grams))
    previous = None
    for encoded, value in grams.iteritems():
        if len(encoded) != 24 or any(c not in "0123456789abcdef" for c in encoded):
            raise ValueError("Invalid trigram encoding")
        key = tuple(int(encoded[i : i + 8], 16) for i in (0, 8, 16))
        block = value[0]
        if (
            not 0 <= block < len(seen)
            or seen[block]
            or any(wid >= len(words) for wid in key)
            or encoded == previous
        ):
            raise ValueError("Invalid/duplicate trigram IDs or keys")
        seen[block] = 1
        keys[block * 3 : block * 3 + 3] = array("I", key)
        previous = encoded
    if not all(seen) or any(
        tuple(keys[i : i + 3]) >= tuple(keys[i + 3 : i + 6]) for i in range(0, len(keys) - 3, 3)
    ):
        raise ValueError("Incomplete or unordered trigram block IDs")
    # RecordTrie permits multiple values per key. Adjacent iteration is not
    # guaranteed by WEIGHT_ORDER, so verify uniqueness through native lookup.
    for word in words.iterkeys():
        if len(words[word]) != 1:
            raise ValueError("Duplicate vocabulary key")
    for key in grams.iterkeys():
        if len(grams[key]) != 1:
            raise ValueError("Duplicate trigram key")
    return WordLookup(words), TrigramLookup(grams), keys
