"""Experimental positional and n-gram retrieval, sharing exact verification."""

import json
from array import array
from collections import defaultdict
from pathlib import Path

from .corpus import Corpus, Sequence, canonical, validate_minimum

CANDIDATES = {"positional": 1, "ngram2": 2, "ngram3": 3, "ngram5": 5}


class Index:
    def __init__(self, corpus: Corpus, candidate: str, *, populate: bool = True):
        self.corpus = corpus
        self.candidate = candidate
        self.size = CANDIDATES[candidate]
        self.unigrams: dict[tuple[int, ...], array] = {}
        self.ngrams: dict[tuple[int, ...], array] = {}
        if populate:
            for rid, source in enumerate(corpus.sequences):
                for pos, word in enumerate(source.terms):
                    packed = (rid << 32) | pos
                    self.unigrams.setdefault((word,), array("Q")).append(packed)
                    if self.size > 1 and source.window(pos, self.size):
                        key = tuple(source.terms[pos : pos + self.size])
                        self.ngrams.setdefault(key, array("Q")).append(packed)

    def save(self, path: Path) -> None:
        with path.open("wb") as stream:
            stream.write(
                canonical(
                    {
                        "prototype_version": 1,
                        "candidate": self.candidate,
                        "corpus_fingerprint": self.corpus.fingerprint,
                    }
                )
            )
            for name, table in (("unigrams", self.unigrams), ("ngrams", self.ngrams)):
                for key in sorted(table):
                    stream.write(
                        canonical(
                            {
                                "table": name,
                                "key": list(key),
                                "positions": [[p >> 32, p & 0xFFFFFFFF] for p in table[key]],
                            }
                        )
                    )

    @classmethod
    def load(cls, corpus: Corpus, path: Path) -> "Index":
        with path.open(encoding="utf-8") as stream:
            header = json.loads(next(stream))
            if (
                header.get("prototype_version") != 1
                or header.get("corpus_fingerprint") != corpus.fingerprint
            ):
                raise ValueError("Incompatible prototype index")
            instance = cls(corpus, header["candidate"], populate=False)
            for line in stream:
                row = json.loads(line)
                table = instance.unigrams if row["table"] == "unigrams" else instance.ngrams
                key = tuple(row["key"])
                if key in table:
                    raise ValueError("Duplicate prototype key")
                positions = array("Q")
                for rid, pos in row["positions"]:
                    if not 0 <= rid < len(corpus.sequences):
                        raise ValueError("Invalid posting record")
                    source = corpus.sequences[rid]
                    if (
                        not source.window(pos, len(key))
                        or tuple(source.terms[pos : pos + len(key)]) != key
                    ):
                        raise ValueError("Invalid posting position/key")
                    positions.append((rid << 32) | pos)
                if list(positions) != sorted(set(positions)):
                    raise ValueError("Prototype postings are not sorted/unique")
                table[key] = positions
        return instance

    def seeds(self, query: Sequence, minimum: int):
        width = self.size if self.size <= minimum else 1
        table = self.unigrams if width == 1 else self.ngrams
        for qi in range(len(query) - minimum + 1):
            if not query.window(qi, minimum):
                continue
            # Every match contains every seed within its minimum-length window.
            # Choose the least frequent seed, retaining completeness without caps.
            choices = [
                (
                    len(table.get(tuple(query.terms[a : a + width]), ())),
                    a,
                    tuple(query.terms[a : a + width]),
                )
                for a in range(qi, qi + minimum - width + 1)
            ]
            count, anchor, key = min(choices)
            if not count:
                continue
            for packed in table[key]:
                rid, pos = packed >> 32, (packed & 0xFFFFFFFF) - (anchor - qi)
                yield qi, rid, pos

    def detect(self, text: str, minimum: int = 5) -> tuple[list[dict], dict]:
        validate_minimum(minimum)
        query = self.corpus.query(text)
        runs = set()
        covered = {}
        candidates = checked = 0
        for qi, rid, si in self.seeds(query, minimum):
            candidates += 1
            source = self.corpus.sequences[rid]
            if not source.window(si, minimum):
                continue
            diagonal = rid, qi - si
            if qi < covered.get(diagonal, -1):
                continue
            checked += 1
            if query.terms[qi : qi + minimum] != source.terms[si : si + minimum]:
                continue
            qa, sa, qb, sb = qi, si, qi + minimum, si + minimum
            while (
                qa
                and sa
                and query.window(qa - 1, qb - qa + 1)
                and source.window(sa - 1, sb - sa + 1)
            ):
                if query.terms[qa - 1] != source.terms[sa - 1]:
                    break
                qa -= 1
                sa -= 1
            while qb < len(query) and sb < len(source):
                if (
                    query.segments[qb] != query.segments[qa]
                    or source.segments[sb] != source.segments[sa]
                    or query.terms[qb] != source.terms[sb]
                ):
                    break
                qb += 1
                sb += 1
            covered[diagonal] = qb
            while qa < qb and not (query.boundary(qa) and source.boundary(sa)):
                qa += 1
                sa += 1
            while qb > qa and not (query.boundary(qb) and source.boundary(sb)):
                qb -= 1
                sb -= 1
            if qb - qa >= minimum:
                runs.add((qa, qb, rid, sa, sb))
        results, occurrences = select_results(self.corpus, query, text, runs, minimum)
        return results, {
            "candidates": candidates,
            "verification_calls": checked,
            "verified_occurrences": occurrences,
        }


def select_results(
    corpus: Corpus, query: Sequence, text: str, runs: set, minimum: int
) -> tuple[list[dict], int]:
    selected = []
    pending = runs.copy()
    while pending:
        start, end = min(
            {(r[0], r[1]) for r in pending},
            key=lambda p: (
                -(p[1] - p[0]),
                -(query.ends[p[1] - 1] - query.starts[p[0]]),
                query.starts[p[0]],
                p,
            ),
        )
        selected.append((start, end))
        remaining = set()
        for qa, qb, rid, sa, sb in pending:
            if qb <= start or qa >= end:
                remaining.add((qa, qb, rid, sa, sb))
                continue
            source = corpus.sequences[rid]
            for left, right in ((qa, min(qb, start)), (max(qa, end), qb)):
                a, b = sa + left - qa, sa + right - qa
                while left < right and not (query.boundary(left) and source.boundary(a)):
                    left += 1
                    a += 1
                while right > left and not (query.boundary(right) and source.boundary(b)):
                    right -= 1
                    b -= 1
                if right - left >= minimum:
                    remaining.add((left, right, rid, a, b))
        pending = remaining
    output = []
    occurrence_count = 0
    for start, end in sorted(selected):
        matches: dict[int, set[tuple[int, int]]] = defaultdict(set)
        for qa, qb, rid, sa, _ in runs:
            if qa <= start and end <= qb:
                source = corpus.sequences[rid]
                left, right = sa + start - qa, sa + end - qa
                if source.boundary(left) and source.boundary(right):
                    matches[rid].add((source.starts[left], source.ends[right - 1]))
        references = []
        for rid in sorted(matches):
            record = corpus.records[rid]
            occurrences = [
                {"start": a, "end": b, "text": record["text"][a:b]} for a, b in sorted(matches[rid])
            ]
            occurrence_count += len(occurrences)
            references.append({"hadith_key": record["hadith_key"], "occurrences": occurrences})
        a, b = query.starts[start], query.ends[end - 1]
        output.append(
            {
                "start": a,
                "end": b,
                "text": text[a:b],
                "matched_words": end - start,
                "references": references,
            }
        )
    return output, occurrence_count
