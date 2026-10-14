"""Experimental evidence models and original-offset serialization."""

from array import array
from collections import defaultdict
from dataclasses import dataclass

from hadith_detector._text import tokenize
from tools.exact_benchmark.corpus import sequence, validate_minimum


def parameters(text, minimum, errors, missing):
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    validate_minimum(minimum)
    for value in (errors, missing):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("budgets must be nonnegative integers, excluding bool")


@dataclass(frozen=True)
class Evidence:
    qa: int
    qb: int
    rid: int
    sa: int
    sb: int
    errors: int
    path: tuple[int, ...]

    @property
    def missing(self):
        return self.sb - self.sa - (self.qb - self.qa)


def query_tokens(corpus, text):
    tokens = tokenize(text).tokens
    return tokens, sequence(tokens, corpus.vocabulary, False)


def segment_ends(source):
    ends = array("I", [0]) * len(source)
    stop = len(source)
    for i in range(len(source) - 1, -1, -1):
        if i + 1 < len(source) and source.segments[i] != source.segments[i + 1]:
            stop = i + 1
        ends[i] = stop
    return ends


def materialize(corpus, text, tokens, query, selected, evidence, distance):
    """Shared presentation only: both matchers select passages independently."""
    output = []
    for qa, qb in sorted(selected):
        supporting = defaultdict(dict)
        for item in evidence:
            if (item.qa, item.qb) != (qa, qb):
                continue
            source = corpus.sequences[item.rid]
            span = (int(source.starts[item.sa]), int(source.ends[item.sb - 1]))
            previous = supporting[item.rid].get(span)
            if previous is None or (item.errors, item.missing, item.path) < (
                previous.errors,
                previous.missing,
                previous.path,
            ):
                supporting[item.rid][span] = item
        refs = []
        best = None
        reverse = {v: k for k, v in corpus.vocabulary.items()}
        for rid, spans in sorted(supporting.items()):
            source = corpus.sequences[rid]
            record = corpus.records[rid]
            occurrences = []
            for (a, b), item in sorted(spans.items()):
                pair = (item.errors, item.missing)
                best = pair if best is None else min(best, pair)
                alignment = []
                for qi, si in zip(range(qa, qb), item.path, strict=True):
                    alignment.append(
                        {
                            "input_token": qi,
                            "source_token": si,
                            "input_start": tokens[qi].start,
                            "input_end": tokens[qi].end,
                            "source_start": int(source.starts[si]),
                            "source_end": int(source.ends[si]),
                            "errors": distance(tokens[qi].term, reverse[int(source.terms[si])]),
                        }
                    )
                aligned = set(item.path)
                omissions = [
                    {
                        "source_token": si,
                        "start": int(source.starts[si]),
                        "end": int(source.ends[si]),
                        "text": record["text"][source.starts[si] : source.ends[si]],
                        "term": reverse[int(source.terms[si])],
                    }
                    for si in range(item.sa, item.sb)
                    if si not in aligned
                ]
                occurrences.append(
                    {
                        "start": a,
                        "end": b,
                        "text": record["text"][a:b],
                        "errors": item.errors,
                        "missing_words": item.missing,
                        "alignment": alignment,
                        "omitted_source_tokens": omissions,
                    }
                )
            refs.append({"hadith_key": record["hadith_key"], "occurrences": occurrences})
        a, b = int(query.starts[qa]), int(query.ends[qb - 1])
        output.append(
            {
                "start": a,
                "end": b,
                "text": text[a:b],
                "matched_words": qb - qa,
                "errors": best[0],
                "missing_words": best[1],
                "references": refs,
            }
        )
    return output


def exact_evidence(corpus, query, results):
    """Attach word traces to an independently selected exact result."""
    identities = {r["hadith_key"]: i for i, r in enumerate(corpus.records)}
    evidence, selected = [], []
    for result in results:
        qa = next(
            i
            for i, start in enumerate(query.starts)
            if start == result["start"] and query.boundary(i)
        )
        qb = qa + result["matched_words"]
        selected.append((qa, qb))
        for reference in result["references"]:
            rid = identities[reference["hadith_key"]]
            source = corpus.sequences[rid]
            for occurrence in reference["occurrences"]:
                sa = next(
                    i
                    for i, start in enumerate(source.starts)
                    if start == occurrence["start"] and source.boundary(i)
                )
                sb = sa + qb - qa
                evidence.append(Evidence(qa, qb, rid, sa, sb, 0, tuple(range(sa, sb))))
    return evidence, selected


def exact_projection(results):
    return [
        {
            "start": r["start"],
            "end": r["end"],
            "text": r["text"],
            "matched_words": r["matched_words"],
            "references": [
                {
                    "hadith_key": ref["hadith_key"],
                    "occurrences": [
                        {k: o[k] for k in ("start", "end", "text")} for o in ref["occurrences"]
                    ],
                }
                for ref in r["references"]
            ],
        }
        for r in results
    ]
