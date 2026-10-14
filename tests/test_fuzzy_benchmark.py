"""Independent tiny path enumeration, fuzzy retrieval and backend parity."""

import importlib.util
import itertools
import json
import random
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "tools", ROOT / "tools/__init__.py", submodule_search_locations=[str(ROOT / "tools")]
)
module = importlib.util.module_from_spec(spec)
sys.modules["tools"] = module
spec.loader.exec_module(module)
from hadith_detector._text import tokenize  # noqa: E402
from tools.exact_benchmark.corpus import Corpus, canonical, digest  # noqa: E402
from tools.fuzzy_benchmark import oracle  # noqa: E402
from tools.fuzzy_benchmark.common import Evidence, query_tokens  # noqa: E402
from tools.fuzzy_benchmark.distance import Backend, python_distance  # noqa: E402
from tools.fuzzy_benchmark.prototypes import STRATEGIES, Matcher  # noqa: E402


def edit_enumeration(a, b):
    # Deliberately different, tiny recursive reference for character costs.
    if not a or not b:
        return len(a) + len(b)
    if a[0] == b[0]:
        return edit_enumeration(a[1:], b[1:])
    return 1 + min(
        edit_enumeration(a[1:], b), edit_enumeration(a, b[1:]), edit_enumeration(a[1:], b[1:])
    )


def enumerate_paths(corpus, text, minimum, errors, missing, *, results=False):
    tokens, query = query_tokens(corpus, text)
    words = {v: k for k, v in corpus.vocabulary.items()}
    evidence = []
    for qa in range(len(tokens)):
        for qb in range(qa + minimum, len(tokens) + 1):
            if not query.boundary(qa) or not query.boundary(qb) or not query.window(qa, qb - qa):
                continue
            n = qb - qa
            for rid, source in enumerate(corpus.sequences):
                for sa in range(len(source)):
                    for sb in range(sa + n, min(len(source), sa + n + missing) + 1):
                        if (
                            not source.boundary(sa)
                            or not source.boundary(sb)
                            or not source.window(sa, sb - sa)
                        ):
                            continue
                        if n == 1:
                            paths = [(sa,)] if sb == sa + 1 else []
                        else:
                            paths = [
                                (sa, *p, sb - 1)
                                for p in itertools.combinations(range(sa + 1, sb - 1), n - 2)
                            ]
                        choices = []
                        for path in paths:
                            cost = sum(
                                oracle.distance(tokens[qi].term, words[int(source.terms[si])])
                                for qi, si in zip(range(qa, qb), path, strict=True)
                            )
                            if cost <= errors:
                                choices.append((cost, path))
                        if choices:
                            cost, path = min(choices)
                            evidence.append(Evidence(qa, qb, rid, sa, sb, cost, path))
    # Direct interval enumeration and removal, independent of both selectors.
    all_evidence = evidence.copy()
    chosen = []
    while evidence:
        spans = {(e.qa, e.qb) for e in evidence}

        def rank(span, remaining=evidence):
            a, b = span
            cost = min((e.errors, e.missing) for e in remaining if (e.qa, e.qb) == span)
            return (a - b, query.starts[a] - query.ends[b - 1], *cost, query.starts[a], span)

        selected = min(spans, key=rank)
        chosen.append(selected)
        evidence = [e for e in evidence if e.qb <= selected[0] or e.qa >= selected[1]]
    if results:
        from tools.fuzzy_benchmark.common import materialize

        return materialize(corpus, text, tokens, query, chosen, all_evidence, oracle.distance)
    return chosen


@pytest.mark.parametrize("backend", ["python", "rapidfuzz"])
def test_distance_cutoffs(backend):
    if backend == "rapidfuzz":
        pytest.importorskip("rapidfuzz")
    kernel = Backend(backend)
    strings = ["", "ا", "ب", "اب", "با", "عَن", "🙂", "𞸀", "abc"]
    for a, b in itertools.product(strings, repeat=2):
        exact = edit_enumeration(a, b)
        assert oracle.distance(a, b) == exact
        for cutoff in (0, 1, 2, 3, 10**30):
            assert kernel.distance(a, b, cutoff) == min(exact, cutoff + 1)
    assert python_distance("اب", "با", 2) == 2
    assert kernel.distance("اب", "جج", 0) == 1
    assert kernel.distance("اب", "جج", 2) == 2


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("backend", ["python", "rapidfuzz"])
def test_manual_alignment_cases(strategy, backend):
    if backend == "rapidfuzz":
        pytest.importorskip("rapidfuzz")
    corpus = Corpus.synthetic(["ا ب ب ت ث", "ا ب ت", "ا ب ت", "ا � ب ت", "ﷺ", ""])
    matcher = Matcher(corpus, strategy, backend)
    cases = [
        ("ا ب ت", 3, 0, 0),
        ("ا ت", 2, 0, 2),
        ("ج ت", 2, 1, 2),
        ("ج د", 2, 2, 2),
        ("ا ب END ت", 1, 1, 1),
        ("ﷺ", 1, 0, 0),
        ("صلى عليه وسلم", 3, 0, 1),
        ("الله عليه وسلم", 1, 0, 1),
        ("", 1, 0, 0),
        ("ا ب ت ث ج د", 2, 1, 1),
        ("ا", 1, 10**30, 10**30),
    ]
    for text, minimum, errors, missing in cases:
        expected, _ = oracle.detect(corpus, text, minimum, errors, missing)
        assert enumerate_paths(corpus, text, minimum, errors, missing, results=True) == expected
        actual, _ = matcher.detect(text, minimum, errors, missing)
        assert actual == expected
        if len(corpus.query(text)) <= 6 and errors < 10:
            spans = enumerate_paths(corpus, text, minimum, errors, missing)
            query = corpus.query(text)
            assert [(r["start"], r["end"]) for r in expected] == [
                (query.starts[a], query.ends[b - 1]) for a, b in sorted(spans)
            ]
    result = matcher.detect("ا ب ت", 3, 0, 1)[0][0]
    assert len(result["references"]) == 3
    assert result["errors"] == 0
    assert result["references"][0]["occurrences"][0]["missing_words"] == 1
    omitted = matcher.detect("صلى عليه وسلم", 3, 0, 1)[0][0]["references"][0]["occurrences"][0]
    assert omitted["omitted_source_tokens"][0]["term"] == "الله"
    assert all(a["source_start"] == 0 for a in omitted["alignment"])


def test_random_path_enumeration_and_complete_retrieval():
    rng = random.Random(42)
    for _ in range(35):
        texts = [" ".join(rng.choices(["ا", "ب", "ت"], k=5)) for _ in range(3)]
        text = " ".join(rng.choices(["ا", "ب", "ج"], k=4))
        corpus = Corpus.synthetic(texts)
        minimum, errors, missing = rng.randrange(1, 4), rng.randrange(3), rng.randrange(3)
        expected, _ = oracle.detect(corpus, text, minimum, errors, missing)
        query = corpus.query(text)
        assert enumerate_paths(corpus, text, minimum, errors, missing, results=True) == expected
        assert [(r["start"], r["end"]) for r in expected] == [
            (query.starts[a], query.ends[b - 1])
            for a, b in sorted(enumerate_paths(corpus, text, minimum, errors, missing))
        ]
        for strategy in STRATEGIES:
            assert Matcher(corpus, strategy).detect(text, minimum, errors, missing)[0] == expected


@pytest.mark.parametrize(
    "arguments", [(0, 0, 0), (True, 0, 0), (1, -1, 0), (1, 0, True), (1, 1.0, 0)]
)
def test_invalid_parameters(arguments):
    corpus = Corpus.synthetic(["ا ب"])
    for detector in (oracle.detect, Matcher(corpus).detect):
        with pytest.raises(ValueError):
            if detector == oracle.detect:
                detector(corpus, "ا", *arguments)
            else:
                detector("ا", *arguments)


def test_exact_regression_and_retrieval_guarantees():
    corpus = Corpus.synthetic(["ا ب ت ث ج ح خ د ذ ر", "ا ب ت ث ج ح خ د ذ ر"])
    cases = [
        ("ا ب ت ث ج ح", 6, 1, 0),
        ("ا ب ت ث ج ح خ د ذ ر", 10, 1, 1),
        ("ا ج ح خ د ذ ر", 5, 0, 2),
        ("ا ج ج ث ج ح", 5, 2, 0),
    ]
    for strategy in STRATEGIES:
        for text, m, e, g in cases:
            expected, _ = oracle.detect(corpus, text, m, e, g)
            actual, _ = Matcher(corpus, strategy).detect(text, m, e, g)
            assert actual == expected


def test_deterministic_queries_micro_and_index_reload(tmp_path):
    from tools.exact_benchmark.indexes import Index
    from tools.fuzzy_benchmark.queries import generate, micro_pairs

    corpus = Corpus.synthetic(["ا ب ت ث ج ح خ د ذ ر"])
    assert canonical(generate(corpus, 2)) == canonical(generate(corpus, 2))
    assert canonical(micro_pairs(corpus, 100)) == canonical(micro_pairs(corpus, 100))
    for strategy in STRATEGIES:
        matcher = Matcher(corpus, strategy)
        before = matcher.detect("ا ب خ ث ج ح", 5, 1, 1)[0]
        first, second = tmp_path / f"{strategy}-a", tmp_path / f"{strategy}-b"
        matcher.index.save(first)
        matcher.index.save(second)
        assert first.read_bytes() == second.read_bytes()
        matcher.index = Index.load(corpus, first)
        assert matcher.detect("ا ب خ ث ج ح", 5, 1, 1)[0] == before


@pytest.mark.benchmark
def test_isolated_fuzzy_pipeline_smoke(tmp_path):
    pytest.importorskip("psutil")
    pytest.importorskip("rapidfuzz")
    from tools.exact_benchmark import oracle as exact_oracle
    from tools.fuzzy_benchmark.__main__ import hashed

    corpus = Corpus.synthetic(["عن ابن عمر قال الله حدثنا رسول نافع عمر قال"])
    source = tmp_path / "corpus"
    source.mkdir()
    (source / "records.jsonl").write_bytes(b"".join(canonical(r) for r in corpus.records))
    (source / "tokens.jsonl").write_bytes(
        canonical(
            {
                "hadith_key": "fixture:1",
                "tokens": [asdict(t) for t in tokenize(corpus.records[0]["text"]).tokens],
            }
        )
    )
    (source / "validation.json").write_bytes(b"{}\n")
    (source / "manifest.json").write_bytes(
        canonical(
            {
                "versions": {"manifest": 1, "records": 1, "tokens": 1, "normalization": 1},
                "artifacts": {
                    n: digest(source / n)
                    for n in ("records.jsonl", "tokens.jsonl", "validation.json")
                },
            }
        )
    )
    corpus = __import__("tools.exact_benchmark.corpus", fromlist=["load_corpus"]).load_corpus(
        source
    )
    exact = tmp_path / "exact"
    exact.mkdir()
    query = {"id": "exact-0", "text": "عن ابن عمر قال الله", "minimum": 5, "category": "bare"}
    (exact / "queries.json").write_bytes(
        canonical({"corpus_fingerprint": corpus.fingerprint, "queries": [query]})
    )
    (exact / "oracle-results.json").write_bytes(
        canonical({query["id"]: hashed(exact_oracle.detect(corpus, query["text"], 5)[0])})
    )
    output = tmp_path / "experiment"
    for command, extra in (
        ("prepare", ["--exact-dir", str(exact), "--per-category", "1", "--micro-count", "50"]),
        ("run", []),
    ):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.fuzzy_benchmark",
                command,
                "--corpus-dir",
                str(source),
                "--output-dir",
                str(output),
                *extra,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["reports"]) == 6
    assert len({r["index_sha256"] for r in summary["reports"]}) == 1
    assert all(r["agreement"] and len(r["timings"]) == 16 for r in summary["reports"])
    assert all(r["peak_rss"] > 0 and r["micro_pairs"] == 50 for r in summary["reports"])
    from tools.fuzzy_benchmark.__main__ import verify_preparation

    (output / "queries.json").write_bytes((output / "queries.json").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        verify_preparation(output)


def test_lru_eviction_preserves_distance_and_neighbors(monkeypatch):
    from tools.fuzzy_benchmark import distance, prototypes

    monkeypatch.setattr(distance, "MAX_DISTANCE_CACHE", 2)
    monkeypatch.setattr(prototypes, "MAX_NEIGHBOR_CACHE", 1)
    corpus = Corpus.synthetic(["ا ب ت ث ج"])
    matcher = Matcher(corpus, "first")
    for text in ("ا ب", "ت ث", "ج ا", "ا ب"):
        assert matcher.detect(text, 1, 1, 0)[0] == oracle.detect(corpus, text, 1, 1, 0)[0]
        assert len(matcher.backend.cache) <= 2
        assert len(matcher.neighbors) <= 1
    assert matcher.backend.evictions > 0


def test_original_slices_and_cost_accounting():
    corpus = Corpus.synthetic(["عَنْ نَافِعٍ زَائِدٌ عَنِ ابْنِ عُمَرَ", "ﷺ"])
    text = "🙂عَن نَافِع، عن ابن عُمر � صَلى عليه وسلم"
    results = Matcher(corpus, "anchors").detect(text, 3, 1, 1)[0]
    assert len(results) == 2
    tokens, query = query_tokens(corpus, text)
    records = {r["hadith_key"]: i for i, r in enumerate(corpus.records)}
    words = {v: k for k, v in corpus.vocabulary.items()}
    for passage in results:
        assert text[passage["start"] : passage["end"]] == passage["text"]
        assert "�" not in passage["text"] and "🙂" not in passage["text"]
        costs = []
        for reference in passage["references"]:
            rid = records[reference["hadith_key"]]
            source = corpus.sequences[rid]
            original = corpus.records[rid]["text"]
            for occurrence in reference["occurrences"]:
                assert original[occurrence["start"] : occurrence["end"]] == occurrence["text"]
                alignment = occurrence["alignment"]
                assert len(alignment) == passage["matched_words"]
                assert occurrence["errors"] == sum(w["errors"] for w in alignment)
                assert occurrence["missing_words"] == len(occurrence["omitted_source_tokens"])
                assert occurrence["errors"] <= 1 and occurrence["missing_words"] <= 1
                costs.append((occurrence["errors"], occurrence["missing_words"]))
                assert query.boundary(alignment[0]["input_token"])
                assert query.boundary(alignment[-1]["input_token"] + 1)
                assert source.boundary(alignment[0]["source_token"])
                assert source.boundary(alignment[-1]["source_token"] + 1)
                for item in alignment:
                    qi, si = item["input_token"], item["source_token"]
                    assert (
                        text[item["input_start"] : item["input_end"]]
                        == text[tokens[qi].start : tokens[qi].end]
                    )
                    assert (
                        original[item["source_start"] : item["source_end"]]
                        == original[source.starts[si] : source.ends[si]]
                    )
                    assert item["errors"] == oracle.distance(
                        tokens[qi].term, words[int(source.terms[si])]
                    )
        assert (passage["errors"], passage["missing_words"]) == min(costs)
