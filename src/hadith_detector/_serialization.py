"""Structural result validation, without corpus access or matching."""

from __future__ import annotations

import math
from dataclasses import fields
from typing import Any

from .models import (
    Detection,
    HadithRecord,
    HadithReference,
    OmittedSourceToken,
    SourceOccurrence,
    WordAlignment,
)


def _object(value: Any, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise TypeError("Expected a dictionary with string keys")
    if not required <= value.keys() or value.keys() - required - (optional or set()):
        raise ValueError("Missing or unknown structural fields")
    return value


def _integer(value: Any, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("Expected an integer, excluding booleans")
    if value < lower:
        raise ValueError(f"Integer must be at least {lower}")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected a string")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise TypeError("Expected a list")
    return value


def _json(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    if isinstance(value, list):
        for item in value:
            _json(item)
        return
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for item in value.values():
            _json(item)
        return
    raise TypeError("Metadata must contain finite JSON values with string keys")


def _span(start: Any, end: Any, text: Any = None) -> tuple[int, int]:
    a, b = _integer(start), _integer(end)
    if b <= a:
        raise ValueError("Offsets must describe a nonempty exclusive-end span")
    if text is not None and len(_string(text)) != b - a:
        raise ValueError("Text length differs from span")
    return a, b


def record(value: Any) -> HadithRecord:
    names = {f.name for f in fields(HadithRecord)} - {"additional_metadata"}
    if not isinstance(value, dict) or not names <= value.keys():
        raise ValueError("Missing record fields")
    _json(value)
    for name in ("hadith_key", "collection", "language", "hadith_number", "text"):
        if not _string(value[name]) and name != "text":
            raise ValueError("Record identity fields cannot be empty")
    for name in ("urn", "seq", "number_sort", "book_number", "in_book_number", "n_grades"):
        _integer(value[name], 1 if name in ("urn", "seq") else 0)
    for name in ("sunnah_url", "grade_summary"):
        if value[name] is not None:
            _string(value[name])
    if not isinstance(value["is_muallaq"], bool):
        raise TypeError("is_muallaq must be a boolean")
    grades = _list(value["grades"])
    if any(not isinstance(g, dict) for g in grades) or len(grades) != value["n_grades"]:
        raise ValueError("Invalid grades or grade count")
    return HadithRecord._from_source(value)


def word(value: Any) -> WordAlignment:
    data = _object(value, {f.name for f in fields(WordAlignment)})
    for item in data.values():
        _integer(item)
    _span(data["input_start"], data["input_end"])
    _span(data["source_start"], data["source_end"])
    return WordAlignment(**data)


def omitted(value: Any) -> OmittedSourceToken:
    data = _object(value, {f.name for f in fields(OmittedSourceToken)})
    _integer(data["source_token"])
    _span(data["start"], data["end"], _string(data["text"]))
    if not _string(data["term"]):
        raise ValueError("An omitted normalized term cannot be empty")
    return OmittedSourceToken(**data)


def occurrence(value: Any) -> SourceOccurrence:
    data = _object(
        value,
        {"start", "end", "text"},
        {"errors", "missing_words", "alignment", "omitted_source_tokens"},
    )
    a, b = _span(data["start"], data["end"], _string(data["text"]))
    errors = _integer(data.get("errors", 0))
    missing = _integer(data.get("missing_words", 0))
    alignment = tuple(word(v) for v in _list(data.get("alignment", [])))
    omissions = tuple(omitted(v) for v in _list(data.get("omitted_source_tokens", [])))
    if alignment:
        if alignment[0].source_start != a or alignment[-1].source_end != b:
            raise ValueError("Trace endpoints differ from occurrence")
        if sum(w.errors for w in alignment) != errors or len(omissions) != missing:
            raise ValueError("Trace costs differ from occurrence costs")
        for left, right in zip(alignment, alignment[1:], strict=False):
            if right.input_token != left.input_token + 1 or right.source_token <= left.source_token:
                raise ValueError("Aligned tokens must be ordered and input-contiguous")
            if right.input_start < left.input_start or right.input_end < left.input_end:
                raise ValueError("Input spans must be ordered")
            if right.source_start < left.source_start or right.source_end < left.source_end:
                raise ValueError("Source spans must be ordered")
        aligned = {w.source_token for w in alignment}
        positions = [o.source_token for o in omissions]
        if positions != sorted(set(positions)) or aligned.intersection(positions):
            raise ValueError("Omitted tokens must be distinct, ordered and unaligned")
        lo, hi = alignment[0].source_token, alignment[-1].source_token
        if any(not lo < p < hi for p in positions) or hi - lo + 1 != len(aligned) + missing:
            raise ValueError("Only internal source omissions are allowed")
    elif omissions or errors or missing:
        raise ValueError("Nonzero costs require an alignment trace")
    trace: tuple[WordAlignment | OmittedSourceToken, ...] = (*alignment, *omissions)
    for token in trace:
        start = token.source_start if isinstance(token, WordAlignment) else token.start
        end = token.source_end if isinstance(token, WordAlignment) else token.end
        if not a <= start < end <= b:
            raise ValueError("Source trace lies outside occurrence")
        if (
            isinstance(token, OmittedSourceToken)
            and data["text"][start - a : end - a] != token.text
        ):
            raise ValueError("Omitted substring differs from occurrence")
    source_spans = sorted((w.source_token, w.source_start, w.source_end) for w in alignment) + [
        (o.source_token, o.start, o.end) for o in omissions
    ]
    ordered = sorted(source_spans)
    for previous_span, current_span in zip(ordered, ordered[1:], strict=False):
        if current_span[1:] != previous_span[1:] and current_span[1] < previous_span[2]:
            raise ValueError("Source token spans must be disjoint or share a symbol span")
    return SourceOccurrence(a, b, data["text"], errors, missing, alignment, omissions)


def reference(value: Any) -> HadithReference:
    data = _object(value, {"record", "occurrences"})
    source = record(data["record"])
    occurrences = tuple(occurrence(v) for v in _list(data["occurrences"]))
    spans = [(o.start, o.end) for o in occurrences]
    if not spans or spans != sorted(set(spans)):
        raise ValueError("Occurrences must be nonempty, distinct and ordered")
    for item in occurrences:
        if source.text[item.start : item.end] != item.text:
            raise ValueError("Occurrence does not reproduce record substring")
    return HadithReference(source, occurrences)


def detection(value: Any) -> Detection:
    data = _object(
        value, {"start", "end", "text", "matched_words", "references"}, {"errors", "missing_words"}
    )
    a, b = _span(data["start"], data["end"], _string(data["text"]))
    count = _integer(data["matched_words"], 1)
    errors = _integer(data.get("errors", 0))
    missing = _integer(data.get("missing_words", 0))
    references = tuple(reference(v) for v in _list(data["references"]))
    identities = [r.record.hadith_key for r in references]
    if not references or len(set(identities)) != len(identities):
        raise ValueError("References must be nonempty and have distinct identities")
    ordering = [(r.record.collection, r.record.seq) for r in references]
    if ordering != sorted(ordering):
        raise ValueError("References must be in collection/sequence order")
    costs = []
    input_trace: tuple[tuple[int, int, int], ...] | None = None
    for ref in references:
        for item in ref.occurrences:
            costs.append((item.errors, item.missing_words))
            if item.alignment:
                if len(item.alignment) != count:
                    raise ValueError("Aligned word count differs from matched_words")
                if item.alignment[0].input_start != a or item.alignment[-1].input_end != b:
                    raise ValueError("Input trace endpoints differ from detection")
                if any(not a <= w.input_start < w.input_end <= b for w in item.alignment):
                    raise ValueError("Input trace lies outside detection")
                current = tuple((w.input_token, w.input_start, w.input_end) for w in item.alignment)
                if input_trace is not None and current != input_trace:
                    raise ValueError("Supporting traces must describe the same input tokens")
                input_trace = current
    if min(costs) != (errors, missing):
        raise ValueError("Detection costs must be the best supporting cost pair")
    return Detection(a, b, data["text"], count, references, errors, missing)
