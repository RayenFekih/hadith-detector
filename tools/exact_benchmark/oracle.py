"""Independent exhaustive source scan, including independent result recovery."""

from collections import defaultdict

from .corpus import Corpus, validate_minimum


def detect(corpus: Corpus, text: str, minimum: int = 5) -> tuple[list[dict], dict]:
    validate_minimum(minimum)
    query = corpus.query(text)
    seeds: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for i in range(len(query) - minimum + 1):
        if query.window(i, minimum):
            key = tuple(query.terms[i : i + minimum])
            if -1 not in key:
                seeds[key].append(i)
    runs = set()
    covered = {}
    candidates = checked = 0
    if seeds:
        # No corpus index: examine every contiguous source window afresh.
        for rid, source in enumerate(corpus.sequences):
            for j in range(len(source) - minimum + 1):
                if not source.window(j, minimum):
                    continue
                for i in seeds.get(tuple(source.terms[j : j + minimum]), ()):
                    candidates += 1
                    diagonal = (rid, i - j)
                    if i < covered.get(diagonal, -1):
                        continue
                    checked += 1
                    left = 0
                    while i - left > 0 and j - left > 0:
                        qi, si = i - left - 1, j - left - 1
                        if (
                            query.segments[qi] != query.segments[i]
                            or source.segments[si] != source.segments[j]
                            or query.terms[qi] != source.terms[si]
                        ):
                            break
                        left += 1
                    right = minimum
                    while i + right < len(query) and j + right < len(source):
                        qi, si = i + right, j + right
                        if (
                            query.segments[qi] != query.segments[i]
                            or source.segments[si] != source.segments[j]
                            or query.terms[qi] != source.terms[si]
                        ):
                            break
                        right += 1
                    covered[diagonal] = i + right
                    qa, qb, sa, sb = i - left, i + right, j - left, j + right
                    while qa < qb and (not query.boundary(qa) or not source.boundary(sa)):
                        qa += 1
                        sa += 1
                    while qb > qa and (not query.boundary(qb) or not source.boundary(sb)):
                        qb -= 1
                        sb -= 1
                    if qb - qa >= minimum:
                        runs.add((qa, qb, rid, sa, sb))
    selected = []
    free = [(0, len(query))]
    while free:
        passages = set()
        for ra, rb, rid, sa, _ in runs:
            source = corpus.sequences[rid]
            for fa, fb in free:
                qa, qb = max(ra, fa), min(rb, fb)
                start, finish = sa + qa - ra, sa + qb - ra
                while qa < qb and (not query.boundary(qa) or not source.boundary(start)):
                    qa += 1
                    start += 1
                while qb > qa and (not query.boundary(qb) or not source.boundary(finish)):
                    qb -= 1
                    finish -= 1
                if qb - qa >= minimum:
                    passages.add((qa, qb))
        if not passages:
            break
        qa, qb = min(
            passages,
            key=lambda p: (
                -(p[1] - p[0]),
                -(query.ends[p[1] - 1] - query.starts[p[0]]),
                query.starts[p[0]],
                p,
            ),
        )
        selected.append((qa, qb))
        remaining = []
        for fa, fb in free:
            if qb <= fa or qa >= fb:
                remaining.append((fa, fb))
            else:
                if fa < qa:
                    remaining.append((fa, qa))
                if qb < fb:
                    remaining.append((qb, fb))
        free = remaining
    output = []
    occurrences = 0
    for qa, qb in sorted(selected):
        supporting: dict[int, set[tuple[int, int]]] = defaultdict(set)
        for ra, rb, rid, sa, _ in runs:
            if ra <= qa and qb <= rb:
                source = corpus.sequences[rid]
                start, finish = sa + qa - ra, sa + qb - ra
                if source.boundary(start) and source.boundary(finish):
                    supporting[rid].add((source.starts[start], source.ends[finish - 1]))
        references = []
        for rid in sorted(supporting):
            record = corpus.records[rid]
            spans = sorted(supporting[rid])
            occurrences += len(spans)
            references.append(
                {
                    "hadith_key": record["hadith_key"],
                    "occurrences": [
                        {"start": a, "end": b, "text": record["text"][a:b]} for a, b in spans
                    ],
                }
            )
        begin, end = query.starts[qa], query.ends[qb - 1]
        output.append(
            {
                "start": begin,
                "end": end,
                "text": text[begin:end],
                "matched_words": qb - qa,
                "references": references,
            }
        )
    return output, {
        "candidates": candidates,
        "verification_calls": checked,
        "verified_occurrences": occurrences,
    }
