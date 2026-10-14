"""Complete positional retrieval with a shared bounded ordered verifier."""

from collections import OrderedDict, defaultdict

from tools.exact_benchmark.indexes import Index

from .common import Evidence, exact_evidence, materialize, parameters, query_tokens, segment_ends
from .distance import Backend

STRATEGIES = ("first", "anchors", "hybrid")
MAX_NEIGHBOR_CACHE = 4096


class Matcher:
    def __init__(self, corpus, strategy="hybrid", backend="python"):
        if strategy not in STRATEGIES:
            raise ValueError("Unknown retrieval strategy")
        self.corpus, self.strategy = corpus, strategy
        self.backend = Backend(backend)
        self.index = Index(corpus, "ngram3")
        self.words = {v: k for k, v in corpus.vocabulary.items()}
        self.buckets = defaultdict(list)
        for wid, word in self.words.items():
            self.buckets[len(word)].append(wid)
        self.neighbors = OrderedDict()
        self.stats = {}
        self.source_ends = [segment_ends(s) for s in corpus.sequences]

    def approximate(self, term, errors):
        key = term, errors
        if key not in self.neighbors:
            found = []
            for length, words in sorted(self.buckets.items()):
                if abs(length - len(term)) <= errors:
                    for wid in words:
                        self.stats["vocabulary_comparisons"] += 1
                        if self.backend.distance(term, self.words[wid], errors) <= errors:
                            found.append(wid)
            self.neighbors[key] = tuple(sorted(found))
            if len(self.neighbors) > MAX_NEIGHBOR_CACHE:
                self.neighbors.popitem(last=False)
        self.neighbors.move_to_end(key)
        return self.neighbors[key]

    def starts(self, tokens, query, qa, minimum, errors, missing):
        result = set()
        if self.strategy == "first" or minimum <= errors:
            for wid in self.approximate(tokens[qa].term, errors):
                for packed in self.index.unigrams[(wid,)]:
                    result.add((packed >> 32, packed & 0xFFFFFFFF))
            return result
        # Integer arithmetic avoids overflow/rounding for enormous budgets.
        guarantee = minimum - errors > 2 * (errors + missing + 1)
        if self.strategy == "hybrid" and guarantee:
            anchors = [
                (a, self.index.ngrams.get(tuple(query.terms[a : a + 3]), ()))
                for a in range(qa, qa + minimum - 2)
            ]
        else:
            available = [
                (len(self.index.unigrams.get((int(query.terms[a]),), ())), a)
                for a in range(qa, qa + minimum)
            ]
            anchors = [
                (a, self.index.unigrams.get((int(query.terms[a]),), ()))
                for _, a in sorted(available)[: errors + 1]
            ]
        for anchor, postings in anchors:
            for packed in postings:
                rid, position = packed >> 32, packed & 0xFFFFFFFF
                base = position - (anchor - qa)
                # Gaps before the anchor are bounded by the actual source prefix.
                for skipped in range(min(missing, base) + 1):
                    result.add((rid, base - skipped))
        return result

    def verify(self, tokens, query, qa, rid, sa, minimum, errors, missing, query_ends):
        source = self.corpus.sequences[rid]
        if not 0 <= sa < len(source) or not source.boundary(sa):
            return []
        if not source.window(sa, minimum):
            return []
        first = self.backend.distance(tokens[qa].term, self.words[int(source.terms[sa])], errors)
        if first > errors:
            return []
        # States consume prefixes. Align and skip are separate transitions;
        # endpoints are accepted only immediately after an alignment transition.
        states = {(1, 1, True): (first, (sa,))}
        found = []
        qsize = query_ends[qa] - qa
        ssize = self.source_ends[rid][sa] - sa
        ssize = min(ssize, qsize + missing)
        for consumed in range(2, qsize + ssize + 1):
            if not states:
                break
            layer = sorted(k for k in states if k[0] + k[1] == consumed)
            for qi, si, aligned_last in layer:
                cost, path = states.pop((qi, si, aligned_last))
                self.stats["alignment_states"] += 1
                if (
                    aligned_last
                    and qi >= minimum
                    and query.boundary(qa + qi)
                    and source.boundary(sa + si)
                ):
                    found.append(Evidence(qa, qa + qi, rid, sa, sa + si, cost, path))
                if qi >= qsize:
                    continue
                if si < ssize:
                    if si - qi < missing:
                        self._put(states, (qi, si + 1, False), (cost, path))
                    delta = self.backend.distance(
                        tokens[qa + qi].term, self.words[int(source.terms[sa + si])], errors - cost
                    )
                    if delta <= errors - cost:
                        self._put(states, (qi + 1, si + 1, True), (cost + delta, path + (sa + si,)))
        return found

    @staticmethod
    def _put(states, key, value):
        if key not in states or value < states[key]:
            states[key] = value

    def detect(self, text, minimum=5, errors=0, missing=0):
        parameters(text, minimum, errors, missing)
        tokens, query = query_tokens(self.corpus, text)
        if not errors and not missing:
            result, stats = self.index.detect(text, minimum)
            evidence, chosen = exact_evidence(self.corpus, query, result)
            return materialize(
                self.corpus,
                text,
                tokens,
                query,
                chosen,
                evidence,
                lambda a, b: self.backend.distance(a, b, 0),
            ), stats
        self.stats = {
            "vocabulary_comparisons": 0,
            "retrieved_starts": 0,
            "verification_calls": 0,
            "alignment_states": 0,
        }
        before = self.backend.calls, self.backend.hits, self.backend.kernel_calls
        query_ends = segment_ends(query)
        evidence = []
        for qa in range(len(tokens) - minimum + 1):
            if not query.boundary(qa) or not query.window(qa, minimum):
                continue
            starts = self.starts(tokens, query, qa, minimum, errors, missing)
            self.stats["retrieved_starts"] += len(starts)
            for rid, sa in sorted(starts):
                self.stats["verification_calls"] += 1
                evidence.extend(
                    self.verify(tokens, query, qa, rid, sa, minimum, errors, missing, query_ends)
                )
        costs = {}
        for item in evidence:
            key = item.qa, item.qb
            costs[key] = min(
                costs.get(key, (float("inf"), float("inf"))), (item.errors, item.missing)
            )
        pending = sorted(
            costs,
            key=lambda p: (
                -(p[1] - p[0]),
                -(query.ends[p[1] - 1] - query.starts[p[0]]),
                *costs[p],
                query.starts[p[0]],
                p,
            ),
        )
        selected = []
        for qa, qb in pending:
            if not any(qa < b and a < qb for a, b in selected):
                selected.append((qa, qb))
        result = materialize(
            self.corpus,
            text,
            tokens,
            query,
            selected,
            evidence,
            lambda a, b: self.backend.distance(a, b, errors),
        )
        self.stats.update(
            {
                "distance_calls": self.backend.calls - before[0],
                "cache_hits": self.backend.hits - before[1],
                "kernel_calls": self.backend.kernel_calls - before[2],
                "distance_cache_entries": len(self.backend.cache),
                "neighbor_cache_entries": len(self.neighbors),
                "distance_cache_evictions": self.backend.evictions,
                "verified_occurrences": sum(
                    len(r["occurrences"]) for p in result for r in p["references"]
                ),
            }
        )
        return result, self.stats.copy()
