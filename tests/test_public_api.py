"""Public defaults, isolated snapshots, one-entry caching and sequential calls."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from threading import Event, Lock

import pytest

from hadith_detector import (
    Detection,
    DetectorConfig,
    HadithDetector,
    HadithRecord,
    HadithReference,
    OmittedSourceToken,
    SourceOccurrence,
    WordAlignment,
    _convenience,
    clear_cache,
    detect,
    get_hadith,
)

from .test_detector import build_fixture


@pytest.fixture
def directory(tmp_path):
    return build_fixture(tmp_path, ["عن نافع عن ابن عمر", "عن نافع عن ابن عمرو"])[0]


@pytest.fixture(autouse=True)
def empty_cache():
    clear_cache()
    yield
    clear_cache()


@pytest.mark.parametrize("field", ["min_match_words", "max_errors", "max_missing_words"])
@pytest.mark.parametrize("value", [True, False, -1, 1.5, "1"])
def test_invalid_defaults_and_overrides(directory, field, value):
    with pytest.raises(ValueError):
        DetectorConfig(**{field: value})
    detector = HadithDetector(directory)
    with pytest.raises(ValueError):
        detector.detect("", **{field: value})
    with pytest.raises(ValueError):
        detect("", index_dir=directory, **{field: value})


def test_defaults_zero_and_readonly(directory):
    config = DetectorConfig(max_errors=1, max_missing_words=1)
    detector = HadithDetector.from_directory(directory / ".." / directory.name, config)
    assert detector.index_dir == directory.resolve()
    assert detector.config is config
    assert len(detector.detect("عن نافع عن ابن عمر")[0].references) == 2
    strict = detector.detect("عن نافع عن ابن عمر", max_errors=0, max_missing_words=0)
    assert len(strict[0].references) == 1
    assert detector.detect("عن نافع عن ابن عمر", max_errors=None) == detector.detect(
        "عن نافع عن ابن عمر"
    )
    assert detector.config == config
    with pytest.raises(FrozenInstanceError):
        config.max_errors = 0
    for name in ("config", "index_dir"):
        with pytest.raises(AttributeError):
            setattr(detector, name, None)
    with pytest.raises(ValueError):
        DetectorConfig(min_match_words=0)
    with pytest.raises(TypeError):
        HadithDetector(directory, {})
    with pytest.raises(TypeError):
        detect("", index_dir=directory, config={})


def test_convenience_reuse_and_call_defaults(directory, monkeypatch, tmp_path):
    original = _convenience.HadithDetector
    calls = []

    def create(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(_convenience, "HadithDetector", create)
    config = DetectorConfig(max_errors=1)
    query = "عن نافع عن ابن عمر"
    assert detect(query, index_dir=directory, config=config) == original(directory, config).detect(
        query
    )
    assert len(detect(query, index_dir=directory / ".")[0].references) == 1
    assert get_hadith("fixture:1", index_dir=directory).sunnah_url is None
    assert len(calls) == 1
    held = _convenience._entry[1]
    clear_cache()
    assert held.detect(query)
    detect(query, index_dir=directory)
    assert len(calls) == 2
    other_root = tmp_path / "other"
    other_root.mkdir()
    other = build_fixture(other_root, [query])[0]
    detect(query, index_dir=other)
    assert len(calls) == 3
    # A failed replacement must not discard a valid cached instance.
    with pytest.raises(FileNotFoundError):
        detect(query, index_dir=tmp_path / "absent")
    assert _convenience._entry[0] == other.resolve()


def test_concurrent_cache_initialization(directory, monkeypatch):
    original = _convenience.HadithDetector
    entered, release = Event(), Event()
    calls = []

    def create(path):
        calls.append(path)
        entered.set()
        assert release.wait(10)
        return original(path)

    monkeypatch.setattr(_convenience, "HadithDetector", create)
    with ThreadPoolExecutor(4) as pool:
        futures = [pool.submit(get_hadith, "fixture:1", index_dir=directory) for _ in range(4)]
        assert entered.wait(10)
        release.set()
        results = [f.result(timeout=10) for f in futures]
    assert len(calls) == 1 and results.count(results[0]) == 4


def test_sequential_operations_and_exception_recovery(directory, monkeypatch):
    detector = HadithDetector(directory)
    original = HadithDetector._detect
    active = 0
    guard = Lock()
    entered, release = Event(), Event()

    def tracked(self, *args, **kwargs):
        nonlocal active
        with guard:
            active += 1
            assert active == 1
        try:
            entered.set()
            assert release.wait(10)
            return original(self, *args, **kwargs)
        finally:
            with guard:
                active -= 1

    monkeypatch.setattr(HadithDetector, "_detect", tracked)
    with ThreadPoolExecutor(4) as pool:
        first = pool.submit(detector.detect, "عن نافع عن ابن عمر")
        assert entered.wait(10)
        fuzzy = pool.submit(detector.detect, "عن نافع عن ابن عمر", max_errors=1)
        lookup = pool.submit(detector.get_hadith, "fixture:1")
        assert not lookup.done()
        release.set()
        assert first.result(timeout=10)[0].errors == 0
        assert len(fuzzy.result(timeout=10)[0].references) == 2
        assert lookup.result(timeout=10).hadith_key == "fixture:1"
    with pytest.raises(TypeError):
        detector.detect(None)
    with pytest.raises(KeyError):
        detector.get_hadith("missing")
    assert detector.detect("عن نافع عن ابن عمر")
    second = HadithDetector(directory)
    second.detect("عن نافع عن ابن عمر", max_errors=1)
    assert second._fuzzy is not detector._fuzzy


def test_clear_does_not_wait_for_detection(directory, monkeypatch):
    _convenience._detector(directory)
    original = HadithDetector._detect
    entered, release = Event(), Event()

    def wait(self, *args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(HadithDetector, "_detect", wait)
    with ThreadPoolExecutor(2) as pool:
        result = pool.submit(detect, "عن نافع عن ابن عمر", index_dir=directory)
        assert entered.wait(10)
        pool.submit(clear_cache).result(timeout=5)
        assert _convenience._entry is None
        release.set()
        assert result.result(timeout=10)


def test_dictionary_json_roundtrips_and_isolation(directory):
    detector = HadithDetector(directory)
    result = detector.detect("عن نافع عن ابن عمر", max_errors=1)[0]
    restored = Detection.from_dict(json.loads(json.dumps(result.to_dict(), ensure_ascii=False)))
    assert restored == result
    for obj in (
        result,
        result.references[0],
        result.references[0].record,
        result.references[0].occurrences[0],
        result.references[0].occurrences[0].alignment[0],
    ):
        assert type(obj).from_dict(obj.to_dict()) == obj
    assert isinstance(restored.references, tuple)
    restored.references[0].record.additional_metadata["extra"]["values"].append(3)
    assert detector.get_hadith("fixture:1") == result.references[0].record
    payload = result.to_dict()
    other = Detection.from_dict(payload)
    payload["references"][0]["record"]["extra"]["values"].clear()
    assert other.references[0].record == result.references[0].record


def test_omissions_symbols_and_default_traces(tmp_path):
    directory, _ = build_fixture(tmp_path, ["قال ﷺ ثم ذهب", "عن نافع عن ابن عمر"])
    detector = HadithDetector(directory)
    result = detector.detect("قال صلى الله وسلم ثم ذهب", min_match_words=6, max_missing_words=1)[0]
    assert Detection.from_dict(result.to_dict()) == result
    token = result.references[0].occurrences[0].omitted_source_tokens[0]
    assert OmittedSourceToken.from_dict(token.to_dict()) == token
    exact = detector.detect("عن نافع عن ابن عمر")[0].to_dict()
    occurrence = exact["references"][0]["occurrences"][0]
    for field in ("errors", "missing_words", "alignment", "omitted_source_tokens"):
        occurrence.pop(field)
    exact.pop("errors")
    exact.pop("missing_words")
    assert Detection.from_dict(exact).references[0].occurrences[0].alignment == ()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.update(unknown=1),
        lambda p: p.update(start=True),
        lambda p: p.update(end=99),
        lambda p: p.update(matched_words=4),
        lambda p: p.update(errors=1),
        lambda p: p.update(references=[]),
        lambda p: p["references"][0]["occurrences"][0].update(text="bad"),
        lambda p: p["references"][0]["occurrences"][0]["alignment"][1].update(input_token=0),
        lambda p: p["references"][0]["occurrences"][0]["alignment"][0].update(errors=1),
        lambda p: p["references"][0]["record"].update(n_grades=1),
        lambda p: p["references"][0]["record"].update(extra=float("nan")),
    ],
)
def test_reject_inconsistent_payloads(directory, mutation):
    payload = HadithDetector(directory).detect("عن نافع عن ابن عمر")[0].to_dict()
    mutation(payload)
    with pytest.raises((TypeError, ValueError)):
        Detection.from_dict(payload)


@pytest.mark.parametrize(
    "model",
    [Detection, HadithRecord, HadithReference, SourceOccurrence, WordAlignment, OmittedSourceToken],
)
def test_invalid_shapes(model):
    with pytest.raises((TypeError, ValueError)):
        model.from_dict([])
    with pytest.raises((TypeError, ValueError)):
        model.from_dict({})


def test_text_types_and_no_matching_during_restore(directory, monkeypatch):
    import hadith_detector.detector as runtime

    payload = HadithDetector(directory).detect("عن نافع عن ابن عمر")[0].to_dict()

    def forbidden(*args, **kwargs):
        raise AssertionError("Deserialization invoked matching or corpus loading")

    monkeypatch.setattr(runtime, "tokenize", forbidden)
    monkeypatch.setattr(runtime.Resources, "load", forbidden)
    assert Detection.from_dict(payload).to_dict() == payload
    payload["text"] = None
    with pytest.raises(TypeError):
        Detection.from_dict(payload)
    occurrence = {"start": 0, "end": 1, "text": None}
    with pytest.raises(TypeError):
        SourceOccurrence.from_dict(occurrence)
    with pytest.raises(TypeError):
        OmittedSourceToken.from_dict({**occurrence, "source_token": 0, "term": "ع"})


def test_inconsistent_omission_traces(tmp_path):
    directory, _ = build_fixture(tmp_path, ["عن نافع عن ابن عمر"])
    payload = (
        HadithDetector(directory)
        .detect("عن عن ابن عمر", min_match_words=4, max_missing_words=1)[0]
        .to_dict()
    )
    assert Detection.from_dict(payload).missing_words == 1
    occurrence = payload["references"][0]["occurrences"][0]
    occurrence["omitted_source_tokens"][0]["source_token"] = 0
    with pytest.raises(ValueError):
        Detection.from_dict(payload)
