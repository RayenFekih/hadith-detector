"""Reusable offline exact/fuzzy detection using explicitly supplied compact resources."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from threading import RLock

from ._fuzzy import FuzzyMatcher
from ._resources import MAX_U32, Resources, Sequence, query_sequence
from ._text import tokenize
from .config import DetectorConfig
from .models import Detection, HadithRecord, HadithReference, SourceOccurrence, WordAlignment

Run = tuple[int, int, int, int, int]


class HadithDetector:
    """Offline exact/fuzzy API; calls on one instance execute sequentially."""

    __slots__ = ("_resources", "_fuzzy", "_config", "_index_dir", "_lock")

    def __init__(self, index_dir: str | Path, config: DetectorConfig | None = None) -> None:
        if config is not None and not isinstance(config, DetectorConfig):
            raise TypeError("config must be a DetectorConfig or None")
        self._config = config if config is not None else DetectorConfig()
        self._index_dir = Path(index_dir).resolve()
        self._lock = RLock()
        self._resources = Resources.load(self._index_dir)
        self._fuzzy: FuzzyMatcher | None = None

    @property
    def config(self) -> DetectorConfig:
        """Immutable instance defaults."""
        return self._config

    @property
    def index_dir(self) -> Path:
        """Resolved resource directory; resources must remain unchanged."""
        return self._index_dir

    @classmethod
    def from_directory(
        cls, index_dir: str | Path, config: DetectorConfig | None = None
    ) -> HadithDetector:
        """Validate/load local resources without downloading or rebuilding."""
        return cls(index_dir, config)

    def get_hadith(self, hadith_key: str) -> HadithRecord:
        """Return an independent snapshot; unknown identities raise KeyError."""
        with self._lock:
            if not isinstance(hadith_key, str):
                raise TypeError("hadith_key must be a string")
            rid = self._resources.keys[hadith_key]
            return HadithRecord._from_source(self._resources.records[rid])

    def detect(
        self,
        text: str,
        *,
        min_match_words: int | None = None,
        max_errors: int | None = None,
        max_missing_words: int | None = None,
    ) -> list[Detection]:
        """Detect passages sequentially on this instance; None inherits defaults."""
        with self._lock:
            config = self.config._override(min_match_words, max_errors, max_missing_words)
            return self._detect(
                text,
                min_match_words=config.min_match_words,
                max_errors=config.max_errors,
                max_missing_words=config.max_missing_words,
            )

    def _seeds(self, query: Sequence, minimum: int) -> Iterator[tuple[int, int, int]]:
        data = self._resources
        width = 3 if minimum >= 3 else 1
        for start in range(len(query) - minimum + 1):
            if not query.window(start, minimum):
                continue
            best: tuple[int, int, int] | None = None
            for anchor in range(start, start + minimum - width + 1):
                if width == 1:
                    key = int(query.terms[anchor])
                    count = data.unigram_counts[key] if key >= 0 else 0
                    offset = data.unigram_offsets[key] if key >= 0 else 0
                else:
                    gram = (
                        int(query.terms[anchor]),
                        int(query.terms[anchor + 1]),
                        int(query.terms[anchor + 2]),
                    )
                    block = data.trigrams.get(gram)
                    count = data.trigram_counts[block] if block is not None else 0
                    offset = data.trigram_offsets[block] if block is not None else 0
                if not count:
                    best = None
                    break
                choice = count, anchor, offset
                if best is None or choice < best:
                    best = choice
            if best is not None:
                count, anchor, offset = best
                postings = data.trigram_postings if width == 3 else data.unigram_postings
                for position in range(offset, offset + count):
                    packed = postings[position]
                    yield start, packed >> 32, (packed & MAX_U32) - (anchor - start)

    def _detect(
        self,
        text: str,
        *,
        min_match_words: int = 5,
        max_errors: int = 0,
        max_missing_words: int = 0,
    ) -> list[Detection]:
        """Detect ordered normalized substrings and every supporting source occurrence.

        Results use exclusive Python character offsets. There are no reference
        caps or semantic filters. Edits are unit-cost character Levenshtein;
        omissions skip only internal source words. Booleans are not budgets.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        minimum = min_match_words
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
            raise ValueError("min_match_words must be a positive integer")
        for name, budget in (("max_errors", max_errors), ("max_missing_words", max_missing_words)):
            if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        tokens = tokenize(text).tokens
        if len(tokens) < minimum:
            return []
        if max_errors or max_missing_words:
            if self._fuzzy is None:
                self._fuzzy = FuzzyMatcher(self._resources)
            return self._fuzzy.detect(text, tokens, minimum, max_errors, max_missing_words)
        query = query_sequence(tokens, self._resources.vocabulary)
        runs: set[Run] = set()
        covered: dict[tuple[int, int], int] = {}
        for qi, rid, si in self._seeds(query, minimum):
            source = self._resources.sequences[rid]
            if not source.window(si, minimum):
                continue
            diagonal = rid, qi - si
            if qi < covered.get(diagonal, -1):
                continue
            if query.terms[qi : qi + minimum] != source.terms[si : si + minimum]:
                continue
            qa, qb, sa, sb = qi, qi + minimum, si, si + minimum
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
            run = _trim(query, source, qa, qb, rid, sa, sb)
            if run[1] - run[0] >= minimum:
                runs.add(run)
        return self._results(text, query, runs, minimum)

    def _results(self, text: str, query: Sequence, runs: set[Run], minimum: int) -> list[Detection]:
        pending = runs.copy()
        selected = []
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
                source = self._resources.sequences[rid]
                for left, right in ((qa, min(qb, start)), (max(qa, end), qb)):
                    run = _trim(query, source, left, right, rid, sa + left - qa, sa + right - qa)
                    if run[1] - run[0] >= minimum:
                        remaining.add(run)
            pending = remaining
        output = []
        for start, end in sorted(selected):
            matches: dict[int, set[tuple[int, int, int]]] = defaultdict(set)
            for qa, qb, rid, sa, _ in runs:
                if qa <= start and end <= qb:
                    source = self._resources.sequences[rid]
                    left, right = sa + start - qa, sa + end - qa
                    if source.boundary(left) and source.boundary(right):
                        matches[rid].add(
                            (int(source.starts[left]), int(source.ends[right - 1]), left)
                        )
            references = []
            for rid in sorted(matches):
                source_record = self._resources.records[rid]
                source = self._resources.sequences[rid]
                occurrences = tuple(
                    SourceOccurrence(
                        a,
                        b,
                        source_record["text"][a:b],
                        alignment=tuple(
                            WordAlignment(
                                qi,
                                si,
                                int(query.starts[qi]),
                                int(query.ends[qi]),
                                int(source.starts[si]),
                                int(source.ends[si]),
                                0,
                            )
                            for qi, si in zip(
                                range(start, end), range(left, left + end - start), strict=True
                            )
                        ),
                    )
                    for a, b, left in sorted(matches[rid])
                )
                references.append(
                    HadithReference(HadithRecord._from_source(source_record), occurrences)
                )
            a, b = int(query.starts[start]), int(query.ends[end - 1])
            output.append(Detection(a, b, text[a:b], end - start, tuple(references)))
        return output


def _trim(query: Sequence, source: Sequence, qa: int, qb: int, rid: int, sa: int, sb: int) -> Run:
    while qa < qb and not (query.boundary(qa) and source.boundary(sa)):
        qa += 1
        sa += 1
    while qb > qa and not (query.boundary(qb) and source.boundary(sb)):
        qb -= 1
        sb -= 1
    return qa, qb, rid, sa, sb
