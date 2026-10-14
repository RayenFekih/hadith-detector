"""Production two-pass matching compared with the independent exhaustive oracle."""

import builtins
import json
import random
import socket

import pytest

from hadith_detector import HadithDetector, SourceOccurrence, _fuzzy

from .test_detector import build_fixture, corpus_module
from .test_fuzzy_benchmark import oracle


def projection(results):
    output = []
    for result in results:
        row = result.to_dict()
        row["references"] = [
            {"hadith_key": ref["record"]["hadith_key"], "occurrences": ref["occurrences"]}
            for ref in row["references"]
        ]
        output.append(row)
    return output


@pytest.fixture
def fixture(tmp_path):
    texts = [
        "عن نافع عن ابن عمر قال سلام عليكم",
        "عن نافغ عن ابن عمر قال سلام عليكم",
        "عن نافع عن ابن عمر قال سلام عليكم",
        "سلام سلام عليكم سلام عليكم",
        "قال ﷺ سلام الله عليكم",
        "قال صلى عليه وسلم سلام الله عليكم",
        "عن نافع Latin عن ابن عمر � سلام عليكم",
    ]
    index, _ = build_fixture(tmp_path, texts)
    return HadithDetector.from_directory(index), corpus_module.Corpus.synthetic(texts)


def test_full_traces_against_oracle(fixture):
    detector, corpus = fixture
    queries = [
        "عن نافغ ابن عمر قال سلام عليكم",
        "عن نافع عن ابن عمر قال سلام عليكم",
        "سلام عليكم سلام عليكم",
        "قال ﷺ سلام الله عليكم",
        "قال صلى عليه وسلم سلام الله عليكم",
        "قال صلى الله عليه وسلم",
        "عن نافع Latin عن ابن عمر",
        "سلا عليكم",
        "غغغ غغغ",
        "",
    ]
    for query in queries:
        for minimum, errors, missing in [
            (1, 1, 1),
            (3, 2, 2),
            (5, 1, 1),
            (2, 0, 2),
            (1, 2, 0),
            (1, 0, 0),
        ]:
            result = detector.detect(
                query, min_match_words=minimum, max_errors=errors, max_missing_words=missing
            )
            expected, _ = oracle.detect(corpus, query, minimum, errors, missing)
            assert projection(result) == expected, (query, minimum, errors, missing)
            for passage in result:
                assert query[passage.start : passage.end] == passage.text
                assert json.loads(json.dumps(passage.to_dict())) == passage.to_dict()


def test_randomized_two_pass_canonical_paths(tmp_path):
    rng = random.Random(94)
    words = ["قال", "عن", "سلام", "سلا", "الله", "عليه", "ﷺ", "Latin"]
    texts = [" ".join(rng.choices(words, k=7)) for _ in range(8)]
    index, _ = build_fixture(tmp_path, texts)
    detector = HadithDetector.from_directory(index)
    corpus = corpus_module.Corpus.synthetic(texts)
    for _ in range(50):
        query = " ".join(rng.choices(words, k=rng.randrange(1, 8)))
        minimum, errors, missing = rng.randint(1, 4), rng.randint(0, 3), rng.randint(0, 3)
        expected, _ = oracle.detect(corpus, query, minimum, errors, missing)
        assert (
            projection(
                detector.detect(
                    query, min_match_words=minimum, max_errors=errors, max_missing_words=missing
                )
            )
            == expected
        )


@pytest.mark.parametrize("name", ["max_errors", "max_missing_words"])
@pytest.mark.parametrize("value", [True, False, -1, 1.5, "1"])
def test_invalid_budgets(fixture, name, value):
    detector, _ = fixture
    with pytest.raises(ValueError, match=name):
        detector.detect("", **{name: value})


def test_large_budgets_offline_cache_eviction(fixture, monkeypatch):
    detector, corpus = fixture
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network access"))
    monkeypatch.setattr(_fuzzy, "DISTANCE_LIMIT", 3)
    monkeypatch.setattr(_fuzzy, "NEIGHBOR_LIMIT", 2)
    monkeypatch.setattr(_fuzzy, "NEIGHBOR_WORD_LIMIT", 3)
    for query in ["سلا عليكم", "عن نافع", "قال سلام", "سلا عليكم"]:
        expected, _ = oracle.detect(corpus, query, 1, 100, 100)
        assert (
            projection(
                detector.detect(
                    query, min_match_words=1, max_errors=10**100, max_missing_words=10**100
                )
            )
            == expected
        )
        helper = detector._fuzzy
        assert len(helper.distances) <= 3
        assert len(helper.neighbors) <= 2
        assert helper.neighbor_words <= 3


def test_lazy_helpers_and_old_occurrence_constructor(fixture):
    detector, _ = fixture
    detector.detect("عن نافع عن ابن عمر")
    assert detector._fuzzy is None
    detector.detect("عن نافغ عن ابن عمر", max_errors=1)
    helper = detector._fuzzy
    detector.detect("عن نافغ عن ابن عمر", max_errors=1)
    assert detector._fuzzy is helper
    assert SourceOccurrence(0, 1, "و").errors == 0


def test_missing_dependency_and_metadata_isolation(fixture, monkeypatch):
    detector, _ = fixture
    original_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.startswith("rapidfuzz"):
            raise ImportError("unavailable")
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "__import__", blocked)
        detector.detect("عن نافع عن ابن عمر")
        with pytest.raises(RuntimeError, match="RapidFuzz"):
            detector.detect("عن نافغ عن ابن عمر", max_errors=1)
    results = detector.detect("عن نافغ عن ابن عمر", max_errors=1)
    saved = projection(results)
    results[0].references[0].record.additional_metadata["extra"]["values"].append("changed")
    assert projection(detector.detect("عن نافغ عن ابن عمر", max_errors=1)) == saved
    assert detector.get_hadith("fixture:1").additional_metadata["extra"]["values"] == [
        1,
        None,
        "metadata",
    ]


def test_eligible_tails_and_adjacent_passages(tmp_path):
    texts = ["قال عن نافع عن ابن عمر", "عن ابن عمر سلام عليكم", "قال سلام"]
    index, _ = build_fixture(tmp_path, texts)
    detector = HadithDetector.from_directory(index)
    query = "قال عن نافعز عن ابن عمر سلام عليكم قال سلام"
    results = detector.detect(query, min_match_words=2, max_errors=1)
    assert [r.text for r in results] == ["قال عن نافعز عن ابن عمر", "سلام عليكم", "قال سلام"]
    assert (
        projection(results)
        == oracle.detect(corpus_module.Corpus.synthetic(texts), query, 2, 1, 0)[0]
    )


def test_barriers_and_transposition_cost(tmp_path):
    texts = ["قال 12 سلام", "سلام"]
    index, _ = build_fixture(tmp_path, texts)
    detector = HadithDetector.from_directory(index)
    assert detector.detect("قال سلام", min_match_words=2, max_missing_words=100) == []
    assert detector.detect("سالم", min_match_words=1, max_errors=1) == []
    results = detector.detect("سالم", min_match_words=1, max_errors=2)
    assert results[0].errors == 2
    assert [r.record.hadith_key for r in results[0].references] == ["fixture:1", "fixture:2"]
