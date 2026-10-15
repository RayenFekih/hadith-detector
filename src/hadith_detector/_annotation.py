"""Lossless plain-text escaping and deterministic HTML fragments."""

from collections.abc import Sequence
from html import escape

from .models import Detection


def validate(text: str, format: str) -> None:
    """Reject unsupported formats and characters HTML cannot preserve losslessly."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not isinstance(format, str):
        raise TypeError("format must be a string")
    if format != "html":
        raise ValueError("Only format='html' is supported")
    if any(char == "\x00" or 0xD800 <= ord(char) <= 0xDFFF for char in text):
        raise ValueError("HTML annotation cannot preserve NUL or lone surrogate characters")


def _escape(text: str) -> str:
    # Character references keep CR intact through HTML's newline preprocessing.
    return escape(text, quote=True).replace("\r", "&#13;")


def render(text: str, detections: Sequence[Detection]) -> str:
    """Render detector-selected spans without repeating matching or overlap selection."""
    parts = []
    cursor = 0
    for index, match in enumerate(detections):
        for value in (match.start, match.end, match.errors, match.missing_words):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Annotation offsets and costs must be nonnegative integers")
        if not cursor <= match.start < match.end <= len(text):
            raise ValueError("Annotation spans must be in bounds, ordered and non-overlapping")
        if text[match.start : match.end] != match.text:
            raise ValueError("Annotation span differs from original input text")
        parts.append(_escape(text[cursor : match.start]))
        parts.append(
            f'<mark class="hadith-match" data-match-index="{index}" '
            f'data-start="{match.start}" data-end="{match.end}" '
            f'data-errors="{match.errors}" data-missing-words="{match.missing_words}" '
            f'data-reference-count="{len(match.references)}">'
        )
        parts.append(_escape(text[match.start : match.end]))
        parts.append("</mark>")
        cursor = match.end
    parts.append(_escape(text[cursor:]))
    return "".join(parts)
