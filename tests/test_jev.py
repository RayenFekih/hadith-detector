"""Optional Jev behavior, always using synthetic resources and mocked HTTP."""

import http.client
import io
import json
import threading
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from html.parser import HTMLParser

import pytest

from hadith_detector import (
    ContextualValidationWarning,
    Detection,
    HadithDetector,
    QuotationValidation,
    annotate,
    clear_cache,
    detect,
)
from hadith_detector import _validation as v

from .test_detector import build_fixture

FIRST = "عن نافع عن ابن عمر"
SECOND = "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى"
TEXT = FIRST + "، " + SECOND


@pytest.fixture
def directory(tmp_path):
    clear_cache()
    index, _ = build_fixture(tmp_path, [FIRST, FIRST, SECOND])
    yield index
    clear_cache()


class Marks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.marks = []
        self.text = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "mark":
            self.marks.append(dict(attrs))

    def handle_data(self, data):
        self.text.append(data)


class MockAPI:
    def __init__(self, scores, failure=None, mutate=None):
        self.scores = scores
        self.failure = failure
        self.mutate = mutate
        self.requests = []

    def open(self, request, timeout):
        payload = json.loads(request.data)
        self.requests.append((request, payload, timeout))
        if self.failure:
            raise self.failure
        response = {
            "model": "jev-1.14.0",
            "answers": {
                name: {"type": "noul", "noul": self.scores.get(candidate["marked_candidate"], 0.8)}
                for name, candidate in payload["state"]["candidates"].items()
            },
            "usage": {"input_tokens": 100, "output_tokens": 10},
        }
        if self.mutate:
            self.mutate(response)
        return io.BytesIO(json.dumps(response).encode())


@pytest.fixture
def api(monkeypatch):
    fake = MockAPI({FIRST: 0.2, SECOND: 0.5})
    monkeypatch.setattr(v.urllib.request, "build_opener", lambda *args: fake)
    return fake


def enabled(directory, **kwargs):
    return HadithDetector(
        directory, validation_model="jev", validation_api_key="test-key", **kwargs
    )


def test_disabled_preserves_results_html_and_serialization(directory, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Disabled detector attempted validation")

    monkeypatch.setattr(v, "_request", forbidden)
    monkeypatch.setenv("TYPESAFE_API_KEY", "present-but-not-an-opt-in")
    a = HadithDetector(directory)
    b = HadithDetector(directory, validation_model=None)
    assert a.detect(TEXT) == b.detect(TEXT)
    assert a.annotate(TEXT) == b.annotate(TEXT)
    assert all(m.validation is None and "validation" not in m.to_dict() for m in a.detect(TEXT))


def test_detect_filters_whole_span_and_preserves_all_matching_evidence(directory, api, monkeypatch):
    raw = HadithDetector(directory).detect(TEXT)
    assert len(raw[0].references) == 2
    monkeypatch.setattr(HadithDetector, "_detect", lambda *args, **kwargs: raw)
    matches = enabled(directory).detect(TEXT)
    assert len(matches) == 1
    assert matches[0].text == SECOND
    assert matches[0].validation == QuotationValidation("jev-1.14.0", 0.5, 0.5, "keep")
    assert matches[0].references is raw[1].references
    payload = matches[0].to_dict()
    payload.pop("validation")
    assert payload == raw[1].to_dict()
    assert raw[1].validation is None
    assert len(api.requests) == 1
    request, payload, timeout = api.requests[0]
    assert len(payload["questions"]) == 2  # not three references
    assert request.full_url == "https://api.typesafe.ai/v1/systemone"
    assert request.get_header("Content-encoding") is None
    assert timeout <= 30
    assert all(
        set(c) == {"before", "marked_candidate", "after"}
        for c in payload["state"]["candidates"].values()
    )


def test_annotate_keeps_rejected_candidates_with_scores(directory, api):
    parsed = Marks(enabled(directory).annotate(TEXT))
    assert "".join(parsed.text) == TEXT
    assert len(parsed.marks) == 2
    metadata = [json.loads(m["data-validation"]) for m in parsed.marks]
    assert [m["decision"] for m in metadata] == ["reject", "keep"]
    assert [m["quotation_score"] for m in metadata] == [0.2, 0.5]
    assert parsed.marks[0]["data-reference-count"] == "2"
    assert len(api.requests) == 1


def test_zero_is_a_real_score_and_unrelated_confidence_is_not_used(directory, api):
    api.scores[FIRST] = 0
    api.mutate = lambda response: response["answers"]["candidate_0"].update(confidence=0.99)
    metadata = json.loads(Marks(enabled(directory).annotate(TEXT)).marks[0]["data-validation"])
    assert metadata["quotation_score"] == 0
    assert metadata["decision"] == "reject"
    assert "error" not in metadata


def test_acceptance_preserves_every_reference_on_a_shared_span(directory, api):
    api.scores[FIRST] = 0.9
    match = enabled(directory).detect(FIRST)[0]
    original = HadithDetector(directory).detect(FIRST)[0].to_dict()
    actual = match.to_dict()
    actual.pop("validation")
    assert len(match.references) == 2
    assert actual == original
    assert len(api.requests[0][1]["questions"]) == 1


def test_duplicate_span_is_evaluated_once_without_mutating_references(directory, api, monkeypatch):
    raw = HadithDetector(directory).detect(FIRST)[0]
    split = [replace(raw, references=(r,)) for r in raw.references]
    monkeypatch.setattr(HadithDetector, "_detect", lambda *args, **kwargs: split)
    api.scores[FIRST] = 0.9
    matches = enabled(directory).detect(FIRST)
    assert len(api.requests[0][1]["questions"]) == 1
    assert len(matches) == 2
    assert matches[0].validation is matches[1].validation
    assert all(new.references is old.references for new, old in zip(matches, split, strict=True))


def test_same_words_at_different_offsets_are_separate_candidates(directory, api):
    text = FIRST + "، " + FIRST
    enabled(directory).annotate(text)
    assert len(api.requests[0][1]["questions"]) == 2


def test_batches_twenty_questions_and_preserves_complete_cross_paragraph_span(api):
    text = "x " * 21
    ds = [Detection(i * 2, i * 2 + 1, "x", 1, ()) for i in range(21)]
    validator = v.JevValidator("jev-latest", "test-key", v.DEFAULT_BASE, 0.5)
    assert len(validator.evaluate(text, ds)) == 21
    assert [len(r[1]["questions"]) for r in api.requests] == [20, 1]
    api.requests.clear()
    text = "before\n\ninside\n\nafter"
    d = Detection(3, len(text) - 2, text[3:-2], 1, ())
    validator.evaluate(text, [d])
    candidate = api.requests[0][1]["state"]["candidates"]["candidate_0"]
    assert candidate["marked_candidate"] == d.text


@pytest.mark.parametrize(
    "value",
    [None, True, "0.1", float("nan"), -0.1, 1.1, pytest.param(10**1000, id="oversized_integer")],
)
def test_missing_or_invalid_scores_are_unavailable_not_rejected(directory, api, value):
    api.mutate = lambda result: result["answers"]["candidate_0"].update(noul=value)
    with pytest.warns(ContextualValidationWarning, match="invalid_response"):
        matches = enabled(directory).detect(TEXT)
    assert len(matches) == 2  # malformed batch fails open as a unit
    assert all(m.validation.quotation_score is None for m in matches)
    assert all(m.validation.decision == "unavailable" for m in matches)
    assert all(m.validation.error == "invalid_response" for m in matches)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r["answers"].pop("candidate_0"),
        lambda r: r.update(model="unrelated-model"),
        lambda r: r.update(usage={}),
    ],
)
def test_partial_or_wrong_response_keeps_candidates(directory, api, mutate):
    api.mutate = mutate
    with pytest.warns(ContextualValidationWarning):
        parsed = Marks(enabled(directory).annotate(TEXT))
    assert len(parsed.marks) == 2
    assert all(json.loads(m["data-validation"])["quotation_score"] is None for m in parsed.marks)


@pytest.mark.parametrize(
    "failure,reason",
    [
        (TimeoutError("secret-value"), "timeout"),
        (urllib.error.URLError("private key and input"), "api_error"),
        (http.client.IncompleteRead(b"private body", 10), "api_error"),
        (urllib.error.HTTPError("https://example.test", 401, "private key", {}, None), "api_error"),
    ],
)
def test_api_failures_are_sanitized_and_preserve_detections(directory, api, failure, reason):
    api.failure = failure
    with pytest.warns(ContextualValidationWarning) as warnings:
        matches = enabled(directory).detect(TEXT)
    assert len(matches) == 2
    assert all(m.validation.error == reason for m in matches)
    assert all(m.validation.quotation_score is None for m in matches)
    assert "secret-value" not in str(warnings[0].message)
    assert "private key" not in str(warnings[0].message)


def test_retries_are_bounded_and_respect_deadline(directory, api, monkeypatch):
    api.failure = urllib.error.HTTPError("https://example.test", 429, "limit", {}, None)
    sleeps = []
    monkeypatch.setattr(v.time, "sleep", sleeps.append)
    with pytest.warns(ContextualValidationWarning):
        assert len(enabled(directory).detect(TEXT)) == 2
    assert len(api.requests) == 3
    assert sleeps == [1, 2]


def test_failed_batch_does_not_discard_successful_batch_scores(directory, monkeypatch):
    fake = MockAPI({FIRST: 0.2})
    calls = []

    def open_response(request, timeout):
        calls.append(request)
        if len(calls) == 2:
            raise TimeoutError()
        return fake.open(request, timeout)

    opener = type("Opener", (), {"open": staticmethod(open_response)})()
    monkeypatch.setattr(v.urllib.request, "build_opener", lambda *args: opener)
    with pytest.warns(ContextualValidationWarning):
        matches = enabled(directory).detect(FIRST + "\n\n" + SECOND)
    assert len(matches) == 1
    assert matches[0].text == SECOND
    assert matches[0].validation.quotation_score is None
    assert matches[0].validation.decision == "unavailable"


def test_non_json_response_is_unavailable(directory, monkeypatch):
    opener = type(
        "Opener", (), {"open": staticmethod(lambda *args, **kwargs: io.BytesIO(b"not json"))}
    )()
    monkeypatch.setattr(v.urllib.request, "build_opener", lambda *args: opener)
    with pytest.warns(ContextualValidationWarning):
        assert len(enabled(directory).detect(TEXT)) == 2


def test_from_directory_forwards_validation_settings(directory, api):
    detector = HadithDetector.from_directory(
        directory, validation_model="jev", validation_api_key="test-key"
    )
    assert len(detector.detect(TEXT)) == 1


@pytest.mark.parametrize("threshold,expected", [(0, 2), (0.2, 2), (0.5, 1), (1, 0)])
def test_inclusive_threshold_and_actual_score_direction(directory, api, threshold, expected):
    assert len(enabled(directory, validation_threshold=threshold).detect(TEXT)) == expected


def test_roundtrip_validated_and_unavailable_metadata(directory, api):
    match = enabled(directory).detect(TEXT)[0]
    assert Detection.from_dict(json.loads(json.dumps(match.to_dict()))) == match
    assert QuotationValidation.from_dict(match.validation.to_dict()) == match.validation
    failed = replace(
        match, validation=QuotationValidation("jev-latest", None, 0.5, "unavailable", "timeout")
    )
    assert Detection.from_dict(failed.to_dict()) == failed
    payload = match.to_dict()
    payload["validation"]["decision"] = "reject"
    with pytest.raises(ValueError):
        Detection.from_dict(payload)


@pytest.mark.parametrize("threshold", [True, float("nan"), float("inf"), -1, 2, "0.5"])
def test_invalid_thresholds_are_configuration_errors(directory, threshold):
    with pytest.raises(ValueError):
        enabled(directory, validation_threshold=threshold)


def test_only_jev_and_safe_explicit_endpoints(directory, monkeypatch, api):
    monkeypatch.setenv("TYPESAFE_API_KEY", "default-provider-key")
    HadithDetector(directory, validation_model="jev").detect(FIRST)
    assert api.requests[0][0].get_header("Authorization") == "Bearer default-provider-key"
    with pytest.raises(ValueError):
        HadithDetector(directory, validation_model="gpt-6", validation_api_key="test-key")
    with pytest.raises(ValueError):
        HadithDetector(
            directory, validation_model="jev", validation_api_base="https://api.tunai.tn/v1"
        )
    with pytest.raises(ValueError):
        enabled(directory, validation_api_base="http://example.test/v1")
    with pytest.raises(ValueError):
        enabled(directory, validation_api_base="https://user:pass@example.test/v1")
    with pytest.raises(ValueError):
        HadithDetector(directory, validation_api_key="test-key")
    assert v._NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.test") is None


def test_convenience_functions_do_not_store_credentials_or_enable_global_cache(directory, api):
    options = {
        "validation_model": "jev",
        "validation_api_key": "test-key",
        "validation_api_base": "https://api.tunai.tn/v1",
    }
    assert len(detect(TEXT, index_dir=directory, **options)) == 1
    assert len(Marks(annotate(TEXT, index_dir=directory, **options)).marks) == 2
    count = len(api.requests)
    assert len(detect(TEXT, index_dir=directory)) == 2
    assert len(api.requests) == count
    assert all(m.validation is None for m in detect(TEXT, index_dir=directory))
    assert api.requests[0][0].full_url == "https://api.tunai.tn/v1/systemone"


@pytest.mark.parametrize("method", ["detect", "annotate"])
def test_network_validation_does_not_hold_resource_lock(directory, monkeypatch, method):
    entered, release = threading.Event(), threading.Event()

    def blocking(payload, *args):
        entered.set()
        assert release.wait(10)
        return {
            "model": "jev-1.14.0",
            "answers": {name: {"noul": 0.9} for name in payload["questions"]},
        }

    monkeypatch.setattr(v, "_request", blocking)
    detector = enabled(directory)
    with ThreadPoolExecutor(max_workers=2) as pool:
        task = pool.submit(getattr(detector, method), FIRST)
        try:
            assert entered.wait(5)
            assert pool.submit(detector.get_hadith, "fixture:1").result(timeout=2).text == FIRST
        finally:
            release.set()
        assert task.result(timeout=5)


def test_no_candidates_or_invalid_annotation_make_no_request(directory, api):
    detector = enabled(directory)
    assert detector.detect("") == []
    assert detector.annotate("no matching words") == "no matching words"
    with pytest.raises(ValueError):
        detector.annotate(TEXT, format="json")
    assert api.requests == []


def test_protocol_matches_existing_evaluated_prompt_and_context(directory, api):
    evaluation = pytest.importorskip("tools.evaluation.contextual")
    raw = HadithDetector(directory).detect(TEXT)
    detector = enabled(directory)
    detector.annotate(TEXT)
    candidates = [
        {"case_id": "one", "candidate_id": str(i), "start": d.start, "end": d.end}
        for i, d in enumerate(raw)
    ]
    expected, _ = next(evaluation.batches({"one": {"text": TEXT}}, candidates, "paragraph"))
    actual = api.requests[0][1]
    assert v.INSTRUCTIONS == evaluation.INSTRUCTIONS
    assert actual["state"] == expected["state"]
    assert actual["questions"] == expected["questions"]
