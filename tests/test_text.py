"""Matching words and offsets remain tied to the untouched original input."""

import pytest

from hadith_detector._text import tokenize


def terms(text: str) -> list[str]:
    return [t.term for t in tokenize(text).tokens]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("أَ إِ آ ٱ ة ى ی", ["ا", "ا", "ا", "ا", "ه", "ي", "ي"]),
        ("ؤ ئ ؤ ئ", ["ؤ", "ئ", "ؤ", "ئ"]),
        ("و وبالنية عن", ["و", "وبالنيه", "عن"]),
        ("عـن\u200f نا\u200dفع", ["عن", "نافع"]),
        ("عن،نافع.عن\nابن؟عمر!", ["عن", "نافع", "عن", "ابن", "عمر"]),
        ("ﷲ ﷺ", ["الله", "صلي", "الله", "عليه", "وسلم"]),
        ("ﻻ", ["لا"]),
        ("", []),
    ],
)
def test_normalization(text: str, expected: list[str]) -> None:
    assert terms(text) == expected


def test_original_spans_include_marks_and_controls() -> None:
    text = "😀 عَنْ\u200f نَافِعٍ"
    result = tokenize(text)
    assert [text[t.start : t.end] for t in result.tokens] == ["عَنْ\u200f", "نَافِعٍ"]
    assert result.tokens[0].start == 2  # Python codepoints, not UTF-16 units.


def test_expansions_are_indivisible_and_do_not_merge_neighbours() -> None:
    text = "قالﷺقال"
    result = tokenize(text)
    assert terms(text) == ["قال", "صلي", "الله", "عليه", "وسلم", "قال"]
    expanded = result.tokens[1:5]
    assert {(t.start, t.end) for t in expanded} == {(3, 4)}
    assert all(text[t.start : t.end] == "ﷺ" for t in expanded)


@pytest.mark.parametrize("barrier", ["abc", "123", "١٢٣", "😀", "�", "\u0301", "\u200b"])
def test_barriers_split_segments(barrier: str) -> None:
    result = tokenize(f"عن {barrier} نافع")
    assert [t.term for t in result.tokens] == ["عن", "نافع"]
    assert result.tokens[0].segment != result.tokens[1].segment
    assert result.warnings


def test_punctuation_is_not_a_barrier() -> None:
    result = tokenize('عن، "نافع".\n\nعن')
    assert [t.term for t in result.tokens] == ["عن", "نافع", "عن"]
    assert {t.segment for t in result.tokens} == {0}


def test_damaged_and_orphan_marks_are_reported() -> None:
    result = tokenize("َعن�نافع")
    assert [(w.kind, w.start, w.end) for w in result.warnings] == [
        ("orphan_mark", 0, 1),
        ("replacement_character", 3, 4),
    ]
    assert [t.term for t in result.tokens] == ["عن", "نافع"]
    assert tokenize("").warnings[0].kind == "empty_text"


def test_repeated_words_have_independent_spans() -> None:
    result = tokenize("عن عن")
    assert [(t.term, t.start, t.end) for t in result.tokens] == [("عن", 0, 2), ("عن", 3, 5)]
