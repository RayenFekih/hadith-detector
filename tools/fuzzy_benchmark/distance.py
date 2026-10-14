"""Identically wrapped bounded kernels; RapidFuzz imports only on explicit selection."""

from collections import OrderedDict

MAX_DISTANCE_CACHE = 50_000


def python_distance(a, b, cutoff):
    if abs(len(a) - len(b)) > cutoff:
        return cutoff + 1
    if a == b:
        return 0
    if not a or not b:
        return min(max(len(a), len(b)), cutoff + 1)
    cutoff = min(cutoff, max(len(a), len(b)))
    sentinel = cutoff + 1
    previous = [min(i, sentinel) for i in range(len(b) + 1)]
    for i, character in enumerate(a, 1):
        row = [sentinel] * (len(b) + 1)
        row[0] = min(i, sentinel)
        left, right = max(1, i - cutoff), min(len(b), i + cutoff)
        for j in range(left, right + 1):
            row[j] = min(
                row[j - 1] + 1, previous[j] + 1, previous[j - 1] + (character != b[j - 1]), sentinel
            )
        if min(row) > cutoff:
            return sentinel
        previous = row
    return min(previous[-1], sentinel)


class Backend:
    def __init__(self, name):
        self.name = name
        self.cache = OrderedDict()
        self.evictions = 0
        self.calls = self.hits = self.kernel_calls = 0
        if name == "python":
            self.function = python_distance
            self.implementation = "repository.banded_python"
        elif name == "rapidfuzz":
            from rapidfuzz.distance import Levenshtein

            self.implementation = Levenshtein.distance.__module__

            def kernel(a, b, cutoff):
                return Levenshtein.distance(
                    a, b, weights=(1, 1, 1), processor=None, score_cutoff=cutoff, score_hint=None
                )

            self.function = kernel
        else:
            raise ValueError("Unknown distance backend")

    def uncached(self, a, b, cutoff):
        # Identical short circuits and finite kernel bounds on both backends.
        if a == b:
            return 0
        if abs(len(a) - len(b)) > cutoff:
            return cutoff + 1
        effective = min(cutoff, max(len(a), len(b)))
        value = self.function(a, b, effective)
        return value if value <= effective else cutoff + 1

    def distance(self, a, b, cutoff):
        self.calls += 1
        key = (a, b, cutoff)
        if key in self.cache:
            self.hits += 1
            self.cache.move_to_end(key)
            return self.cache[key]
        self.kernel_calls += 1
        value = self.uncached(a, b, cutoff)
        self.cache[key] = value
        if len(self.cache) > MAX_DISTANCE_CACHE:
            self.cache.popitem(last=False)
            self.evictions += 1
        return value
