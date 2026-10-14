"""Independent exhaustive source scan and unbounded Wagner–Fischer word costs."""

from functools import lru_cache

from .common import Evidence, exact_evidence, materialize, parameters, query_tokens


@lru_cache(maxsize=200_000)
def distance(a, b):
    if a == b:
        return 0
    matrix = [list(range(len(b) + 1))]
    for i, character in enumerate(a, 1):
        row = [i]
        for j, other in enumerate(b, 1):
            row.append(
                min(row[-1] + 1, matrix[-1][j] + 1, matrix[-1][j - 1] + (character != other))
            )
        matrix.append(row)
    return matrix[-1][-1]


def paths(corpus, tokens, query, qa, rid, sa, errors, missing, minimum, reverse):
    """Layered jump alignment; no prototype verifier or source postings."""
    source = corpus.sequences[rid]
    stopq = qa
    while stopq < len(query) and query.segments[stopq] == query.segments[qa]:
        stopq += 1
    stops = sa
    while stops < len(source) and source.segments[stops] == source.segments[sa]:
        stops += 1
    found = []
    # Endpoint states retain the cheapest canonical path; missing count is fixed
    # by consumed input/source lengths, so no error-budget-sized table is needed.
    frontier = {(qa, sa): (0, ())}
    for qi in range(qa, stopq):
        next_states = {}
        for (_, previous), (cost, path) in frontier.items():
            begin = previous if not path else previous + 1
            final = min(
                stops, begin + missing - (0 if not path else path[-1] - sa + 1 - len(path)) + 1
            )
            if not path:
                final = min(stops, sa + 1)
            for si in range(begin, final):
                omitted = si - sa - (qi - qa)
                if omitted > missing:
                    break
                word = reverse[int(source.terms[si])]
                if abs(len(tokens[qi].term) - len(word)) > errors - cost:
                    continue
                total = cost + distance(tokens[qi].term, word)
                if total > errors:
                    continue
                trace = path + (si,)
                key = qi + 1, si
                choice = total, trace
                if key not in next_states or choice < next_states[key]:
                    next_states[key] = choice
        frontier = next_states
        for (_, si), (cost, path) in frontier.items():
            if qi + 1 - qa >= minimum and query.boundary(qi + 1) and source.boundary(si + 1):
                found.append(Evidence(qa, qi + 1, rid, sa, si + 1, cost, path))
        if not frontier:
            break
    return found


def select(evidence, query):
    # Independent free-interval selection, rather than prototype filtering.
    available = [(0, len(query))]
    selected = []
    while True:
        costs = {}
        for item in evidence:
            if any(a <= item.qa and item.qb <= b for a, b in available):
                key = item.qa, item.qb
                costs[key] = min(
                    costs.get(key, (float("inf"), float("inf"))), (item.errors, item.missing)
                )
        if not costs:
            break
        qa, qb = min(
            costs,
            key=lambda p: (
                -(p[1] - p[0]),
                -(query.ends[p[1] - 1] - query.starts[p[0]]),
                *costs[p],
                query.starts[p[0]],
                p,
            ),
        )
        selected.append((qa, qb))
        new = []
        for a, b in available:
            if qb <= a or qa >= b:
                new.append((a, b))
            else:
                if a < qa:
                    new.append((a, qa))
                if qb < b:
                    new.append((qb, b))
        available = new
    return selected


def detect(corpus, text, minimum=5, errors=0, missing=0):
    parameters(text, minimum, errors, missing)
    tokens, query = query_tokens(corpus, text)
    if not errors and not missing:
        from tools.exact_benchmark.oracle import detect as exact_detect

        result, stats = exact_detect(corpus, text, minimum)
        evidence, chosen = exact_evidence(corpus, query, result)
        return materialize(corpus, text, tokens, query, chosen, evidence, distance), stats
    # Query-side evidence lookup only. Every source position is still scanned;
    # no persistent or temporary source posting index is constructed.
    firsts = {}
    for qa in range(len(tokens) - minimum + 1):
        if query.boundary(qa) and query.window(qa, minimum):
            firsts.setdefault(tokens[qa].term, []).append(qa)
    matches = {}
    for word, wid in corpus.vocabulary.items():
        positions = []
        for term, starts in firsts.items():
            if abs(len(term) - len(word)) <= errors and distance(term, word) <= errors:
                positions.extend(starts)
        if positions:
            matches[wid] = positions
    evidence = []
    checked = 0
    reverse = {v: k for k, v in corpus.vocabulary.items()}
    for rid, source in enumerate(corpus.sequences):
        for sa, wid in enumerate(source.terms):
            if source.boundary(sa):
                for qa in matches.get(int(wid), ()):
                    checked += 1
                    evidence.extend(
                        paths(corpus, tokens, query, qa, rid, sa, errors, missing, minimum, reverse)
                    )
    chosen = select(evidence, query)
    result = materialize(corpus, text, tokens, query, chosen, evidence, distance)
    return result, {
        "retrieved_starts": checked,
        "verification_calls": checked,
        "verified_occurrences": sum(len(r["occurrences"]) for p in result for r in p["references"]),
    }
