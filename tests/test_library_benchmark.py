"""Experimental adapters must retain all occurrence traces and original JSON values."""

import importlib
import json

import pytest

for library in ("numpy", "pyroaring", "msgspec", "orjson", "marisa_trie"):
    pytest.importorskip(library, reason="Isolated library benchmark environment required")

from hadith_detector import HadithDetector  # noqa: E402

from .test_detector import build_fixture, corpus_module  # noqa: E402
from .test_fuzzy_detector import oracle, projection  # noqa: E402

adapters = importlib.import_module("tools.library_benchmark.adapters")


@pytest.mark.parametrize("variant", adapters.VARIANTS)
def test_experimental_detector_against_oracle(tmp_path, monkeypatch, variant):
    texts = [
        "عن نافع عن ابن عمر",
        "عن نافغ عن ابن عمر",
        "عن نافع عن ابن عمر",
        "قال ﷺ سلام عليكم",
        "قال صلى عليه وسلم سلام عليكم",
        "قال Latin سلام",
        "سلام سلام سلام عليكم",
        "قال عن نافع عن ابن عمر",
        "عن ابن عمر سلام عليكم",
    ]
    index, _ = build_fixture(tmp_path, texts)
    runtime = importlib.import_module("hadith_detector.detector")
    resources = importlib.import_module("hadith_detector._resources")
    monkeypatch.setattr(runtime, "FuzzyMatcher", runtime.FuzzyMatcher)
    monkeypatch.setattr(resources, "json", resources.json)
    adapters.install_matcher(variant)
    codec = adapters.Codec(variant if variant in ("msgspec", "orjson") else "baseline")
    if variant in ("msgspec", "orjson"):
        codec.install_loader()
    detector = HadithDetector.from_directory(index)
    if variant.startswith("marisa"):
        detector._resources = adapters.trie_resources(detector._resources, tmp_path / "trie")
    corpus = corpus_module.Corpus.synthetic(texts)
    for text in (
        "عن نافغ ابن عمر",
        "قال ﷺ سلام عليكم",
        "سلا عليكم",
        "غغغ عن",
        "قال سلام",
        "قال عن نافعز عن ابن عمر سلام عليكم",
    ):
        for minimum, errors, missing in ((1, 2, 2), (3, 1, 1), (1, 0, 0), (2, 1, 0)):
            actual = detector.detect(
                text, min_match_words=minimum, max_errors=errors, max_missing_words=missing
            )
            assert projection(actual) == oracle.detect(corpus, text, minimum, errors, missing)[0]
            payload = [r.to_dict() for r in actual]
            assert codec.loads(codec.encode(payload)) == payload
            assert codec.encode(payload) == codec.encode(payload)


@pytest.mark.parametrize("name", ("msgspec", "orjson"))
def test_codec_preserves_numeric_policy_and_unknown_fields(name):
    codec = adapters.Codec(name)
    value = {"text": "سلام", "extra": {"number": 10**100, "null": None, "list": [True, 1, 1.5]}}
    assert codec.loads(codec.encode(value)) == value
    for raw in (b'{"value":NaN}', b'{"value":Infinity}', b'{"value":1e999}'):
        with pytest.raises(ValueError):
            codec.loads(raw)
    with pytest.raises(ValueError):
        codec.encode({"value": float("nan")})
    assert codec.loads(b'{"number":123456789012345678901234567890}') == json.loads(
        b'{"number":123456789012345678901234567890}'
    )
