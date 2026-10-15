"""Escaped fragments preserve original text and detector-selected passages."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from html.parser import HTMLParser
from threading import Event

import pytest

from hadith_detector import (
    Detection,
    DetectorConfig,
    HadithDetector,
    _annotation,
    _convenience,
    annotate,
    clear_cache,
    detect,
    get_hadith,
)

from .test_detector import build_fixture


class Fragment(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.text = ""
        self.marks = []
        self.current = None
        self.feed(html)
        self.close()
        assert self.current is None

    def handle_starttag(self, tag, attrs):
        assert tag == "mark" and self.current is None
        assert len(attrs) == 7
        attributes = dict(attrs)
        assert set(attributes) == {
            "class",
            "data-match-index",
            "data-start",
            "data-end",
            "data-errors",
            "data-missing-words",
            "data-reference-count",
        }
        assert attributes.pop("class") == "hadith-match"
        assert all(value.isascii() and value.isdecimal() for value in attributes.values())
        self.current = {"attrs": attributes, "text": ""}

    def handle_endtag(self, tag):
        assert tag == "mark" and self.current is not None
        self.marks.append(self.current)
        self.current = None

    def handle_data(self, data):
        self.text += data
        if self.current is not None:
            self.current["text"] += data

    def handle_comment(self, data):
        raise AssertionError("Unexpected HTML comment")

    def handle_decl(self, decl):
        raise AssertionError("Unexpected declaration")


def assert_parity(html, text, matches):
    parsed = Fragment(html)
    assert parsed.text == text
    assert len(parsed.marks) == len(matches)
    for i, (mark, match) in enumerate(zip(parsed.marks, matches, strict=True)):
        assert mark["text"] == text[match.start : match.end] == match.text
        assert mark["attrs"] == {
            "data-match-index": str(i),
            "data-start": str(match.start),
            "data-end": str(match.end),
            "data-errors": str(match.errors),
            "data-missing-words": str(match.missing_words),
            "data-reference-count": str(len(match.references)),
        }


@pytest.fixture
def detector(tmp_path):
    directory, _ = build_fixture(
        tmp_path,
        [
            "عن نافع عن ابن عمر",
            "عن نافع عن ابن عمرو",
            "عن نافع عن ابن عمر",
            "قال ﷺ ثم ذهب",
            "قال عن نافع عن ابن عمر سلام عليكم",
            "عن ابن عمر سلام عليكم",
        ],
    )
    return HadithDetector(directory)


@pytest.fixture(autouse=True)
def cache():
    clear_cache()
    yield
    clear_cache()


@pytest.mark.parametrize(
    "text,settings",
    [
        ("عن نافع عن ابن عمر", {}),
        ("عن نافع عن ابن عمز", {"max_errors": 1}),
        ("عن عن ابن عمز", {"min_match_words": 4, "max_errors": 1, "max_missing_words": 1}),
        ("قال ﷺ ثم ذهب", {}),
        ("قال صلى الله وسلم ثم ذهب", {"max_missing_words": 1}),
        ("عن نافع عن ابن عمر، عن نافع عن ابن عمر", {}),
        ("قال عن نافع عن ابن عمر سلام عليكم", {"min_match_words": 2}),
        ("عن نافع Latin عن ابن عمر", {"min_match_words": 2}),
        ("عن نافع � عن ابن عمر", {"min_match_words": 2}),
        ("", {}),
        ("no matches <script>alert('x')</script> &amp;", {}),
    ],
)
def test_exact_fuzzy_and_overlap_parity(detector, text, settings):
    matches = detector.detect(text, **settings)
    original = [match.to_dict() for match in matches]
    html = detector.annotate(text, **settings)
    assert_parity(html, text, matches)
    assert detector.annotate(text, **settings) == html
    assert [match.to_dict() for match in detector.detect(text, **settings)] == original


def test_unicode_and_injection_roundtrip(detector):
    text = (
        '\r\n\t <script src="x">alert(1)</script><!--evil--> &amp; &#13; '
        '" onmouseover="evil" \' 😀 \u200f\u200d'
        "عَنْ نَافِعٍ عَنْ ابْنِ عُمَرَ\r\n قال ﷺ ثم ذهب\t\r"
    )
    html = detector.annotate(text)
    assert_parity(html, text, detector.detect(text))
    assert "<script" not in html and "<!--" not in html
    assert "\r" not in html and "&#13;" in html
    assert "&amp;amp;" in html and "&#x27;" in html and "&quot;" in html
    assert "😀" in html and "\u200f" in html and "\u200d" in html


def test_overlap_selection_retains_fuzzy_tails(tmp_path):
    directory, _ = build_fixture(
        tmp_path, ["قال عن نافع عن ابن عمر", "عن ابن عمر سلام عليكم", "قال سلام"]
    )
    detector = HadithDetector(directory)
    text = "قال عن نافعز عن ابن عمر سلام عليكم قال سلام"
    matches = detector.detect(text, min_match_words=2, max_errors=1)
    assert [match.text for match in matches] == [
        "قال عن نافعز عن ابن عمر",
        "سلام عليكم",
        "قال سلام",
    ]
    html = detector.annotate(text, min_match_words=2, max_errors=1)
    assert_parity(html, text, matches)


def test_reference_count_does_not_count_occurrences(tmp_path):
    text = "عن نافع عن ابن عمر"
    directory, _ = build_fixture(tmp_path, [f"{text} ثم {text}", text])
    detector = HadithDetector(directory)
    matches = detector.detect(text)
    assert len(matches[0].references) == 2
    assert len(matches[0].references[0].occurrences) == 2
    html = detector.annotate(text)
    assert_parity(html, text, matches)
    assert 'data-reference-count="2"' in html


def test_adjacent_marks_and_defensive_checks():
    text = "أب"
    matches = [Detection(0, 1, "أ", 1, ()), Detection(1, 2, "ب", 1, ())]
    html = _annotation.render(text, matches)
    assert "</mark><mark" in html
    assert_parity(html, text, matches)
    invalid = [
        replace(matches[0], start=-1),
        replace(matches[0], start=True),
        replace(matches[0], end=3),
        replace(matches[0], end=0),
        replace(matches[0], text="different"),
        replace(matches[0], errors='" onclick="evil'),
    ]
    for match in invalid:
        with pytest.raises(ValueError):
            _annotation.render(text, [match])
    for spans in ([matches[0], matches[0]], list(reversed(matches))):
        with pytest.raises(ValueError):
            _annotation.render(text, spans)


@pytest.mark.parametrize("text", ["\x00", "عن نافع\x00عن ابن عمر", "\ud800", "\udfff"])
def test_lossless_html_restriction_leaves_detection_unchanged(detector, text):
    assert detector.detect(text) == []
    for call in (detector.annotate, lambda value: annotate(value, index_dir=detector.index_dir)):
        with pytest.raises(ValueError, match="NUL or lone surrogate"):
            call(text)


@pytest.mark.parametrize(
    "format,exception",
    [("markdown", ValueError), ("HTML", ValueError), (None, TypeError), (1, TypeError)],
)
def test_invalid_format(detector, format, exception):
    with pytest.raises(exception):
        detector.annotate("", format=format)
    with pytest.raises(exception):
        annotate("", index_dir=detector.index_dir, format=format)


def test_settings_and_convenience_cache(detector, monkeypatch):
    config = DetectorConfig(max_errors=1)
    text = "عن نافع عن ابن عمر"
    configured = HadithDetector(detector.index_dir, config)
    assert configured.annotate(text, max_errors=None) == configured.annotate(text)
    html = annotate(text, index_dir=detector.index_dir, config=config)
    assert html == configured.annotate(text)
    cached = _convenience._entry[1]
    assert_parity(html, text, detect(text, index_dir=detector.index_dir, config=config))
    assert annotate(text, index_dir=detector.index_dir, config=config, max_errors=0) == (
        detector.annotate(text)
    )
    assert annotate(text, index_dir=detector.index_dir) == detector.annotate(text)
    get_hadith("fixture:1", index_dir=detector.index_dir)
    assert _convenience._entry[1] is cached
    with pytest.raises(TypeError):
        annotate(text, index_dir=detector.index_dir, config={})
    for settings in ({"min_match_words": 0}, {"max_errors": True}, {"max_missing_words": -1}):
        with pytest.raises(ValueError):
            detector.annotate("", **settings)
        with pytest.raises(ValueError):
            annotate("", index_dir=detector.index_dir, **settings)
    with pytest.raises(TypeError):
        detector.annotate(None)
    with pytest.raises(TypeError):
        annotate(None, index_dir=detector.index_dir)


def test_detect_called_once_without_extra_normalization(detector, monkeypatch):
    import hadith_detector.detector as runtime

    original = runtime.tokenize
    calls = []

    def tracked(text):
        calls.append(text)
        return original(text)

    monkeypatch.setattr(runtime, "tokenize", tracked)
    text = "عن نافع عن ابن عمر"
    detector.annotate(text, max_errors=1)
    assert calls == [text]


def test_lock_covers_rendering_and_cache_clear(detector, monkeypatch):
    import hadith_detector.detector as runtime

    original = runtime.render
    entered, release, attempted = Event(), Event(), Event()
    cached = _convenience._detector(detector.index_dir)

    def wait(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)

    def lookup():
        attempted.set()
        return cached.get_hadith("fixture:1")

    monkeypatch.setattr(runtime, "render", wait)
    with ThreadPoolExecutor(4) as pool:
        future = pool.submit(
            annotate, "عن نافع عن ابن عمر", index_dir=detector.index_dir, max_errors=1
        )
        assert entered.wait(10)
        blocked = pool.submit(lookup)
        assert attempted.wait(10) and not blocked.done()
        pool.submit(clear_cache).result(timeout=5)
        assert _convenience._entry is None
        # Independent instances are not held by the cached instance's lock.
        assert pool.submit(detector.detect, "عن نافع عن ابن عمر").result(timeout=5)
        release.set()
        html = future.result(timeout=10)
        assert blocked.result(timeout=10).hadith_key == "fixture:1"
    assert_parity(html, "عن نافع عن ابن عمر", cached.detect("عن نافع عن ابن عمر", max_errors=1))
    with pytest.raises(ValueError):
        cached.annotate("", format="invalid")
    assert cached.annotate("عن نافع عن ابن عمر")
