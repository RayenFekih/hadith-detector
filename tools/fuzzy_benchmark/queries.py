"""Seeded, source-linked fuzzy cases and uncached scalar distance workloads."""

import random
from collections import Counter

from . import oracle

CATEGORIES = (
    "edits",
    "omissions",
    "combined",
    "destroyed-seeds",
    "common",
    "short",
    "mixed",
    "adversarial",
)
BUDGETS = ((1, 0), (0, 1), (1, 1), (2, 2))


def generate(corpus, per_category=20, seed=42):
    rng = random.Random(seed)
    words = {v: k for k, v in corpus.vocabulary.items()}
    eligible = [rid for rid, s in enumerate(corpus.sequences) if len(s) >= 10]
    short_records = [rid for rid, s in enumerate(corpus.sequences) if 5 <= len(s) <= 35]
    if not eligible:
        raise ValueError("Query generation needs narrations of at least ten words")
    queries = []
    frequencies = Counter()
    for source in corpus.sequences:
        frequencies.update(
            {
                tuple(source.terms[i : i + 5])
                for i in range(len(source) - 4)
                if source.window(i, 5) and source.boundary(i) and source.boundary(i + 5)
            }
        )
    common = sorted(frequencies, key=lambda key: (-frequencies[key], key))[:per_category]
    for category in CATEGORIES:
        for number in range(per_category):
            e, g = BUDGETS[number % len(BUDGETS)]
            rid = rng.choice(eligible)
            source = corpus.sequences[rid]
            length = (5, 8, 12)[number % 3]
            length = min(length, len(source))
            starts = [
                i
                for i in range(len(source) - length + 1)
                if source.window(i, length) and source.boundary(i) and source.boundary(i + length)
            ]
            if not starts:
                rid = eligible[0]
                source = corpus.sequences[rid]
                starts = [0]
                length = min(5, len(source))
            begin = rng.choice(starts)
            terms = [words[int(w)] for w in source.terms[begin : begin + length]]
            mutations = []
            minimum = 5
            if category == "mixed" and number % 3 == 0 and short_records:
                rid = rng.choice(short_records)
                source = corpus.sequences[rid]
                begin = 0
                terms = [words[int(w)] for w in source.terms]
            if category == "common":
                terms = [words[int(w)] for w in common[number % len(common)]]
            if category == "short":
                terms = terms[: number % 4 + 1]
                minimum = len(terms)
                e = max(e, minimum) if number % 2 else e
            if category == "destroyed-seeds":
                terms = terms[: 5 if e else 5]
                if not e:
                    minimum = 4
                if e:
                    terms[2] += "ز"
                    mutations.append({"kind": "insert", "input_word": 2, "character": "ز"})
                elif g:
                    removed = terms.pop(2)
                    mutations.append({"kind": "omit", "source_word": 2, "term": removed})
            else:
                if category in ("omissions", "combined", "mixed") and g and len(terms) > minimum:
                    for _ in range(min(g, len(terms) - minimum)):
                        index = rng.randrange(1, len(terms) - 1)
                        removed = terms.pop(index)
                        mutations.append({"kind": "omit", "current_word": index, "term": removed})
                if category in ("edits", "combined", "short") and e:
                    index = rng.randrange(len(terms))
                    original = terms[index]
                    kind = ("insert", "delete", "substitute")[number % 3]
                    if kind == "delete" and len(original) > 1:
                        terms[index] = original[:-1]
                    elif kind == "substitute":
                        terms[index] = (
                            "ز" + original[1:] if original[0] != "ز" else "ظ" + original[1:]
                        )
                    else:
                        kind = "insert"
                        terms[index] = original + "ز"
                    mutations.append(
                        {
                            "kind": kind,
                            "input_word": index,
                            "original": original,
                            "mutated": terms[index],
                        }
                    )
            text = " ".join(terms)
            if category == "mixed":
                if number % 3 == 1:
                    text = text + " END " + " ".join(terms)
                elif number % 3 == 2:
                    text = "، ".join(terms)
            presumed_negative = False
            if category == "adversarial":
                if number % 4 == 0:
                    text = " ".join(["زظ" * 12] * 7)
                    presumed_negative = True
                elif number % 4 == 1:
                    text = " ".join(terms[:2]) + " � " + " ".join(terms[2:])
                elif number % 4 == 2:
                    text = " ".join(reversed(terms))
                else:
                    text = " ".join(terms) + " 123 Latin 🙂 " + " ".join(terms)
            queries.append(
                {
                    "id": f"{category}-{number:02d}",
                    "category": category,
                    "text": text,
                    "minimum": minimum,
                    "errors": e,
                    "missing": g,
                    "source_hint": None
                    if category == "common"
                    else corpus.records[rid]["hadith_key"],
                    "source_token_start": None if category == "common" else begin,
                    "mutations": mutations,
                    "presumed_negative": presumed_negative,
                }
            )
    for size in (1024, 4096):
        for number in range(4):
            rid = rng.choice(eligible)
            source = corpus.sequences[rid]
            terms = [words[int(w)] for w in source.terms[:8]]
            e, g = BUDGETS[number]
            mutations = []
            if e:
                original = terms[2]
                terms[2] += "ز"
                mutations.append({"kind": "insert", "input_word": 2, "original": original})
            if g:
                omitted = terms.pop(4)
                mutations.append({"kind": "omit", "source_word": 4, "term": omitted})
            filler = ["زظ" * 12] * (size - len(terms))
            half = len(filler) // 2
            text = " ".join(filler[:half] + terms + filler[half:])
            queries.append(
                {
                    "id": f"large-{size}-{number}",
                    "category": f"large-{size}",
                    "text": text,
                    "minimum": 5,
                    "errors": e,
                    "missing": g,
                    "source_hint": corpus.records[rid]["hadith_key"],
                    "source_token_start": 0,
                    "mutations": mutations,
                    "presumed_negative": False,
                }
            )
    return {
        "format_version": 1,
        "seed": seed,
        "per_category": per_category,
        "corpus_fingerprint": corpus.fingerprint,
        "queries": queries,
    }


def micro_pairs(corpus, count=10_000, seed=42):
    rng = random.Random(seed)
    vocabulary = list(corpus.vocabulary)
    pairs = []
    for i in range(count):
        a = rng.choice(vocabulary)
        mode = i % 7
        if mode == 0:
            b = a
        elif mode == 1:
            b = a + "ز"
        elif mode == 2:
            b = a[:-1]
        elif mode == 3:
            b = "ظ" + a[1:]
        elif mode == 4:
            b = rng.choice(vocabulary)
        elif mode == 5:
            a = "ابتث" * (16 if i % 2 else 32)
            b = a[:-2] + "زز"
        else:
            a, b = "", a
        cutoff = (0, 1, 2, 3, max(len(a), len(b)))[i % 5]
        expected = oracle.distance(a, b)
        pairs.append({"a": a, "b": b, "cutoff": cutoff, "expected": min(expected, cutoff + 1)})
    return {"format_version": 1, "seed": seed, "pairs": pairs}
