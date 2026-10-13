"""Fixed-seed source-linked queries, with exhaustive confirmation of negatives."""

import random
from collections import Counter

from . import oracle
from .corpus import Corpus

CATEGORIES = ("bare", "embedded", "multiple", "full", "common", "short", "negative", "variants")


def excerpt(corpus: Corpus, rid: int, size: int, rng: random.Random) -> str:
    source = corpus.sequences[rid]
    possible = [
        i
        for i in range(len(source) - size + 1)
        if source.window(i, size) and source.boundary(i) and source.boundary(i + size)
    ]
    if not possible:
        raise ValueError("No complete excerpt of requested size")
    start = rng.choice(possible)
    return corpus.records[rid]["text"][source.starts[start] : source.ends[start + size - 1]]


def generate(corpus: Corpus, per_category: int = 20, seed: int = 42) -> dict:
    rng = random.Random(seed)
    eligible = [rid for rid, s in enumerate(corpus.sequences) if len(s) >= 30]
    buckets = [
        [rid for rid in eligible if corpus.records[rid]["collection"] == collection]
        for collection in sorted({r["collection"] for r in corpus.records})
    ]
    if not eligible or not all(buckets):
        raise ValueError("Benchmark generation needs source records of at least 30 tokens")
    reverse = {value: key for key, value in corpus.vocabulary.items()}
    common: Counter[tuple[int, ...]] = Counter()
    for s in corpus.sequences:
        # Count at most once per source record: frequent references, not just repetitions.
        common.update(
            {
                tuple(s.terms[i : i + 5])
                for i in range(len(s) - 4)
                if s.window(i, 5) and s.boundary(i) and s.boundary(i + 5)
            }
        )
    common_phrases = sorted(common, key=lambda key: (-common[key], key))[:per_category]
    filler = "هذا نص تجريبي لعرض الاقتباس في سياق فقرة عربية مع شرح قبل النقل وبعده"
    queries = []
    for category in CATEGORIES:
        for i in range(per_category):
            rid = rng.choice(buckets[i % len(buckets)])
            source_id = corpus.records[rid]["hadith_key"]
            minimum = 5
            size = (5, 12, 30)[i % 3]
            quote = excerpt(corpus, rid, size, rng)
            if category == "bare":
                text = quote
            elif category == "embedded":
                text = f"{filler}. {quote}. ثم نتابع قراءة النص والتعليق على العبارة المذكورة."
            elif category == "multiple":
                other = rng.choice(buckets[(i + 1) % len(buckets)])
                text = f"{quote} END {excerpt(corpus, other, 12, rng)}"
                source_id = [source_id, corpus.records[other]["hadith_key"]]
            elif category == "full":
                ordered = sorted(eligible, key=lambda r: (len(corpus.sequences[r]), r))
                rid = ordered[int((len(ordered) - 1) * i / max(1, per_category - 1))]
                source_id = corpus.records[rid]["hadith_key"]
                text = corpus.records[rid]["text"]
            elif category == "common":
                key = common_phrases[i % len(common_phrases)]
                text = " ".join(reverse[t] for t in key)
                source_id = None
            elif category == "short":
                minimum = i % 4 + 1
                text = excerpt(corpus, rid, minimum, rng)
            elif category == "negative":
                alphabet = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
                words = []
                while len(words) < 8:
                    word = "".join(rng.choice(alphabet) for _ in range(12))
                    if word not in corpus.vocabulary:
                        words.append(word)
                text = " ".join(words)
                source_id = None
                if oracle.detect(corpus, text, minimum)[0]:
                    raise AssertionError("Presumed negative has exact matches")
            else:
                normalized = [reverse[t] for t in corpus.query(quote).terms]
                if i % 2 == 0:
                    text = "، ".join(normalized)
                else:
                    normalized[len(normalized) // 2] = "زظزظزظزظزظ"
                    text = " ".join(normalized)
            queries.append(
                {
                    "id": f"{category}-{i:02d}",
                    "category": category,
                    "text": text,
                    "minimum": minimum,
                    "source_hint": source_id,
                }
            )
    for target in (1024, 4096):
        for i in range(4):
            rid = rng.choice(eligible)
            text = ((filler + " ") * (target // len(corpus.query(filler)) + 1)).split()
            text = text[:target]
            insertion = excerpt(corpus, rid, 30, rng)
            # Two distant copies test repeated input passages as well as common context.
            for position in sorted((target // 4, target * 3 // 4), reverse=True):
                text[position : position + 30] = insertion.split()
            query = " ".join(text)
            queries.append(
                {
                    "id": f"large-{target}-{i}",
                    "category": f"large-{target}",
                    "text": query,
                    "minimum": 5,
                    "source_hint": corpus.records[rid]["hadith_key"],
                }
            )
    return {
        "query_version": 1,
        "seed": seed,
        "per_category": per_category,
        "corpus_fingerprint": corpus.fingerprint,
        "queries": queries,
    }
