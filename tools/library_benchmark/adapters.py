"""Experimental adapters imported only by isolated benchmark workers."""

import json
import math
import re
from collections.abc import Mapping
from dataclasses import replace
from types import SimpleNamespace

from hadith_detector import _resources
from hadith_detector._fuzzy import NEIGHBOR_LIMIT, NEIGHBOR_WORD_LIMIT, FuzzyMatcher

VARIANTS = (
    "baseline",
    "rf-iter",
    "rf-extract",
    "numpy",
    "roaring",
    "numpy-roaring",
    "msgspec",
    "orjson",
    "marisa",
    "marisa-mmap",
)


def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON number")
    if isinstance(value, dict):
        for item in value.values():
            finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            finite(item)


class Codec:
    def __init__(self, name):
        self.name = name
        self.library = __import__(name) if name != "baseline" else json

    def loads(self, raw, **kwargs):
        if self.name == "baseline":
            return json.loads(raw, **kwargs)
        try:
            # Conservatively preserve arbitrary original integers with orjson.
            # Digit runs inside strings can cause harmless stdlib fallback too.
            if self.name == "orjson" and re.search(
                rb"\d{19,}", raw.encode() if isinstance(raw, str) else raw
            ):
                result = json.loads(raw, **kwargs)
            elif self.name == "orjson":
                result = self.library.loads(raw)
            else:
                result = self.library.json.decode(raw)
            finite(result)
            return result
        except ValueError as exc:
            raise json.JSONDecodeError(str(exc), "", 0) from exc

    def encode(self, value):
        if self.name == "baseline":
            return _resources.canonical(value)
        finite(value)
        if self.name == "msgspec":
            return self.library.json.encode(value, order="sorted") + b"\n"
        try:
            return self.library.dumps(value, option=self.library.OPT_SORT_KEYS) + b"\n"
        except TypeError:
            # orjson rejects integers outside its native range.
            return _resources.canonical(value)

    def install_loader(self):
        # Replace this module's JSON facade only, never json.loads process-wide.
        _resources.json = SimpleNamespace(
            loads=self.loads, JSONDecodeError=json.JSONDecodeError, dumps=json.dumps
        )


class CollectionMatcher(FuzzyMatcher):
    mode = "iter"

    def __init__(self, data):
        super().__init__(data)
        self.collections = {
            length: {wid: self.words[wid] for wid in words}
            for length, words in self.buckets.items()
        }

    def approximate(self, term, errors):
        errors = min(errors, max(len(term), max(self.buckets, default=0)))
        key = term, errors
        if key in self.neighbors:
            self.neighbors.move_to_end(key)
            return self.neighbors[key]
        from rapidfuzz import process

        found = []
        for length in self.buckets:
            if abs(length - len(term)) > errors:
                continue
            choices = self.collections[length]
            options = dict(
                scorer=self.kernel,
                processor=None,
                score_cutoff=errors,
                scorer_kwargs={"weights": (1, 1, 1)},
            )
            matches = (
                process.extract_iter(term, choices, **options)
                if self.mode == "iter"
                else process.extract(term, choices, limit=None, **options)
            )
            found.extend(wid for _, _, wid in matches)
        found = tuple(sorted(found))
        if len(found) <= NEIGHBOR_WORD_LIMIT:
            self.neighbors[key] = found
            self.neighbor_words += len(found)
            while len(self.neighbors) > NEIGHBOR_LIMIT or self.neighbor_words > NEIGHBOR_WORD_LIMIT:
                _, removed = self.neighbors.popitem(last=False)
                self.neighbor_words -= len(removed)
        return found


def anchors(matcher, tokens, query, qa, minimum, errors):
    if minimum <= errors:
        return [(qa, wid) for wid in matcher.approximate(tokens[qa].term, errors)]
    data = matcher.data
    choices = [
        (data.unigram_counts[wid] if wid >= 0 else 0, a, wid)
        for a in range(qa, qa + minimum)
        for wid in [int(query.terms[a])]
    ]
    return [(a, wid) for _, a, wid in sorted(choices)[: errors + 1]]


class PositionMatcher(FuzzyMatcher):
    mode = "numpy"

    def starts(self, tokens, query, qa, minimum, errors, missing):
        data = self.data
        choices = anchors(self, tokens, query, qa, minimum, errors)
        if self.mode == "roaring":
            from pyroaring import BitMap64

            result = BitMap64()
            for anchor, wid in choices:
                if wid < 0:
                    continue
                offset, count = data.unigram_offsets[wid], data.unigram_counts[wid]
                for i in range(offset, offset + count):
                    packed = data.unigram_postings[i]
                    base = (packed & 0xFFFFFFFF) - (anchor - qa)
                    for d in range(min(missing, base) + 1):
                        result.add((packed & 0xFFFFFFFF00000000) | (base - d))
            return ((int(p) >> 32, int(p) & 0xFFFFFFFF) for p in result)
        import numpy as np

        pieces = []
        postings = np.frombuffer(data.unigram_postings, dtype=np.uint64)
        for anchor, wid in choices:
            if wid < 0:
                continue
            offset, count = data.unigram_offsets[wid], data.unigram_counts[wid]
            packed = postings[offset : offset + count]
            base = (packed & 0xFFFFFFFF).astype(np.int64) - (anchor - qa)
            stop = min(missing, max(0, int(base.max(initial=-1))))
            for d in range(stop + 1):
                valid = base >= d
                pieces.append(
                    (packed[valid] & np.uint64(0xFFFFFFFF00000000))
                    | (base[valid] - d).astype(np.uint64)
                )
        if not pieces:
            return iter(())
        if self.mode == "numpy-roaring":
            from pyroaring import BitMap64

            result = BitMap64()
            for piece in pieces:
                result.update(piece.tolist())
        else:
            result = np.unique(np.concatenate(pieces))
        return ((int(p) >> 32, int(p) & 0xFFFFFFFF) for p in result)


class TrieMapping(Mapping):
    def __init__(self, trie, triple=False):
        self.trie, self.triple = trie, triple

    def encoded(self, key):
        return "".join(f"{wid:08x}" for wid in key) if self.triple else key

    def __getitem__(self, key):
        return self.trie[self.encoded(key)][0][0]

    def __len__(self):
        return len(self.trie)

    def __iter__(self):
        for key in self.trie.keys():
            yield tuple(int(key[i : i + 8], 16) for i in (0, 8, 16)) if self.triple else key


def trie_resources(data, directory):
    import marisa_trie

    vocabulary = marisa_trie.RecordTrie(
        "<I", [(term, (wid,)) for term, wid in data.vocabulary.items()]
    )
    if hasattr(data.trigrams, "trie"):
        keys = list(data.trigrams.trie.iteritems())
    else:
        keys = [
            ("".join(f"{wid:08x}" for wid in key), (value,)) for key, value in data.trigrams.items()
        ]
    trigrams = marisa_trie.RecordTrie("<I", keys)
    if (
        vocabulary.tobytes()
        != marisa_trie.RecordTrie(
            "<I", [(term, (wid,)) for term, wid in data.vocabulary.items()]
        ).tobytes()
    ):
        raise AssertionError("Nondeterministic vocabulary trie")
    if trigrams.tobytes() != marisa_trie.RecordTrie("<I", keys).tobytes():
        raise AssertionError("Nondeterministic trigram trie")
    directory.mkdir()
    vocabulary.save(str(directory / "vocabulary.marisa"))
    trigrams.save(str(directory / "trigrams.marisa"))
    return replace(data, vocabulary=TrieMapping(vocabulary), trigrams=TrieMapping(trigrams, True))


def install_matcher(variant):
    import hadith_detector.detector as runtime

    if variant.startswith("rf-"):
        runtime.FuzzyMatcher = type("Experiment", (CollectionMatcher,), {"mode": variant[3:]})
    elif variant in ("numpy", "roaring", "numpy-roaring"):
        runtime.FuzzyMatcher = type("Experiment", (PositionMatcher,), {"mode": variant})
