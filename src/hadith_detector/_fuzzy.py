"""Complete anchor retrieval and two-pass bounded alignment; no Python distance fallback."""

from __future__ import annotations

from array import array
from collections import OrderedDict, defaultdict
from collections.abc import Iterator

from ._resources import MAX_U32, Resources, Sequence, query_sequence
from ._text import Token
from .models import (
    Detection,
    HadithRecord,
    HadithReference,
    OmittedSourceToken,
    SourceOccurrence,
    WordAlignment,
)

DISTANCE_LIMIT = 50_000
NEIGHBOR_LIMIT = 4096
NEIGHBOR_WORD_LIMIT = 100_000


def segment_ends(sequence: Sequence) -> array[int]:
    ends: array[int] = array("I", [0]) * len(sequence)
    stop = len(sequence)
    for i in range(len(sequence) - 1, -1, -1):
        if i + 1 < len(sequence) and sequence.segments[i] != sequence.segments[i + 1]:
            stop = i + 1
        ends[i] = stop
    return ends


class FuzzyMatcher:
    def __init__(self, resources: Resources) -> None:
        try:
            from rapidfuzz.distance import Levenshtein
        except ImportError as exc:
            raise RuntimeError("Fuzzy matching requires a working RapidFuzz installation") from exc
        self.kernel = Levenshtein.distance
        self.data = resources
        self.words = dict(sorted((wid, term) for term, wid in resources.vocabulary.items()))
        self.buckets: dict[int, list[int]] = defaultdict(list)
        for wid, word in self.words.items():
            self.buckets[len(word)].append(wid)
        self.ends = [segment_ends(source) for source in resources.sequences]
        self.distances: OrderedDict[tuple[str, str, int], int] = OrderedDict()
        self.neighbors: OrderedDict[tuple[str, int], tuple[int, ...]] = OrderedDict()
        self.neighbor_words = 0

    def distance(self, a: str, b: str, cutoff: int) -> int:
        # Larger cutoffs cannot change an exact distance beyond this finite bound.
        cutoff = min(cutoff, max(len(a), len(b)))
        key = a, b, cutoff
        cached = self.distances.get(key)
        if cached is not None:
            self.distances.move_to_end(key)
            return cached
        if a == b:
            result = 0
        elif abs(len(a) - len(b)) > cutoff:
            result = cutoff + 1
        else:
            result = int(self.kernel(a, b, weights=(1, 1, 1), processor=None, score_cutoff=cutoff))
        self.distances[key] = result
        if len(self.distances) > DISTANCE_LIMIT:
            self.distances.popitem(last=False)
        return result

    def approximate(self, term: str, errors: int) -> tuple[int, ...]:
        # Canonicalize huge budgets to the maximum meaningful word distance.
        errors = min(errors, max(len(term), max(self.buckets, default=0)))
        key = term, errors
        if key in self.neighbors:
            self.neighbors.move_to_end(key)
            return self.neighbors[key]
        found = tuple(
            sorted(
                wid
                for length, words in self.buckets.items()
                if abs(length - len(term)) <= errors
                for wid in words
                if self.distance(term, self.words[wid], errors) <= errors
            )
        )
        if len(found) <= NEIGHBOR_WORD_LIMIT:
            self.neighbors[key] = found
            self.neighbor_words += len(found)
            while len(self.neighbors) > NEIGHBOR_LIMIT or self.neighbor_words > NEIGHBOR_WORD_LIMIT:
                _, removed = self.neighbors.popitem(last=False)
                self.neighbor_words -= len(removed)
        return found

    def starts(
        self,
        tokens: tuple[Token, ...],
        query: Sequence,
        qa: int,
        minimum: int,
        errors: int,
        missing: int,
    ) -> set[tuple[int, int]]:
        data = self.data
        if minimum <= errors:
            anchors = [(qa, wid) for wid in self.approximate(tokens[qa].term, errors)]
        else:
            choices = [
                (data.unigram_counts[wid] if wid >= 0 else 0, a, wid)
                for a in range(qa, qa + minimum)
                for wid in [int(query.terms[a])]
            ]
            anchors = [(a, wid) for _, a, wid in sorted(choices)[: errors + 1]]
        result = set()
        for anchor, wid in anchors:
            if wid < 0:
                continue
            offset, count = data.unigram_offsets[wid], data.unigram_counts[wid]
            for i in range(offset, offset + count):
                packed = data.unigram_postings[i]
                rid, position = packed >> 32, packed & MAX_U32
                base = position - (anchor - qa)
                for skipped in range(min(missing, base) + 1):
                    result.add((rid, base - skipped))
        return result

    def verify(
        self,
        tokens: tuple[Token, ...],
        query: Sequence,
        qa: int,
        rid: int,
        sa: int,
        minimum: int,
        errors: int,
        missing: int,
        qstop: int,
        trace: bool,
    ) -> Iterator[tuple[int, int, int, int, tuple[int, ...]]]:
        source = self.data.sequences[rid]
        if not source.window(sa, minimum) or not source.boundary(sa):
            return
        first = self.distance(tokens[qa].term, self.words[int(source.terms[sa])], errors)
        if first > errors:
            return
        qsize = qstop - qa
        ssize = min(self.ends[rid][sa] - sa, qsize + missing)
        # Only active layers retain paths, and the discovery pass keeps no paths.
        layers: dict[int, dict[tuple[int, int, bool], tuple[int, tuple[int, ...]]]] = {
            2: {(1, 1, True): (first, (sa,) if trace else ())}
        }

        def put(qi: int, si: int, last: bool, cost: int, path: tuple[int, ...]) -> None:
            layer = layers.setdefault(qi + si, {})
            key = qi, si, last
            value = cost, path
            if key not in layer or value < layer[key]:
                layer[key] = value

        for consumed in range(2, qsize + ssize + 1):
            if not layers:
                break
            for (qi, si, last), (cost, path) in layers.pop(consumed, {}).items():
                if last and qi >= minimum and query.boundary(qa + qi) and source.boundary(sa + si):
                    yield qa + qi, sa + si, cost, si - qi, path
                if qi >= qsize or si >= ssize:
                    continue
                if si - qi < missing:
                    put(qi, si + 1, False, cost, path)
                delta = self.distance(
                    tokens[qa + qi].term, self.words[int(source.terms[sa + si])], errors - cost
                )
                if delta <= errors - cost:
                    put(qi + 1, si + 1, True, cost + delta, path + (sa + si,) if trace else ())

    def occurrence(
        self,
        tokens: tuple[Token, ...],
        qa: int,
        rid: int,
        sa: int,
        sb: int,
        errors: int,
        missing: int,
        path: tuple[int, ...],
    ) -> SourceOccurrence:
        source = self.data.sequences[rid]
        original = self.data.records[rid]["text"]
        alignment = tuple(
            WordAlignment(
                qi,
                si,
                tokens[qi].start,
                tokens[qi].end,
                int(source.starts[si]),
                int(source.ends[si]),
                self.distance(tokens[qi].term, self.words[int(source.terms[si])], errors),
            )
            for qi, si in zip(range(qa, qa + len(path)), path, strict=True)
        )
        aligned = set(path)
        omitted = tuple(
            OmittedSourceToken(
                si,
                int(source.starts[si]),
                int(source.ends[si]),
                original[source.starts[si] : source.ends[si]],
                self.words[int(source.terms[si])],
            )
            for si in range(sa, sb)
            if si not in aligned
        )
        a, b = int(source.starts[sa]), int(source.ends[sb - 1])
        return SourceOccurrence(a, b, original[a:b], errors, missing, alignment, omitted)

    def detect(
        self,
        text: str,
        tokens: tuple[Token, ...],
        minimum: int,
        errors: int,
        missing: int,
    ) -> list[Detection]:
        query = query_sequence(tokens, self.data.vocabulary)
        ends = segment_ends(query)
        costs: dict[tuple[int, int], tuple[int, int]] = {}
        for qa in range(len(tokens) - minimum + 1):
            if not query.boundary(qa) or not query.window(qa, minimum):
                continue
            for rid, sa in self.starts(tokens, query, qa, minimum, errors, missing):
                for qb, _, cost, omissions, _ in self.verify(
                    tokens, query, qa, rid, sa, minimum, errors, missing, ends[qa], False
                ):
                    key = qa, qb
                    value = cost, omissions
                    if key not in costs or value < costs[key]:
                        costs[key] = value
        pending = sorted(
            costs,
            key=lambda p: (
                -(p[1] - p[0]),
                -(tokens[p[1] - 1].end - tokens[p[0]].start),
                *costs[p],
                tokens[p[0]].start,
                p,
            ),
        )
        selected: list[tuple[int, int]] = []
        for qa, qb in pending:
            if not any(qa < b and a < qb for a, b in selected):
                selected.append((qa, qb))
        output = []
        for qa, qb in sorted(selected):
            occurrences: dict[int, dict[tuple[int, int], SourceOccurrence]] = defaultdict(dict)
            for rid, sa in self.starts(tokens, query, qa, qb - qa, errors, missing):
                for end, sb, cost, omissions, path in self.verify(
                    tokens, query, qa, rid, sa, qb - qa, errors, missing, qb, True
                ):
                    if end != qb:
                        continue
                    item = self.occurrence(tokens, qa, rid, sa, sb, cost, omissions, path)
                    occurrences[rid][item.start, item.end] = item
            references = tuple(
                HadithReference(
                    HadithRecord._from_source(self.data.records[rid]),
                    tuple(item for _, item in sorted(occurrences[rid].items())),
                )
                for rid in sorted(occurrences)
            )
            a, b = tokens[qa].start, tokens[qb - 1].end
            output.append(Detection(a, b, text[a:b], qb - qa, references, *costs[qa, qb]))
        return output
