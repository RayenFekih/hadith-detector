"""Typed matching results, with independent metadata snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from math import isfinite
from typing import Any, Literal


def _unit_score(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number between 0 and 1")
    if not 0 <= value <= 1 or not isfinite(value):
        raise ValueError(f"{name} must be a finite number between 0 and 1")
    return float(value)


class ContextualValidationWarning(UserWarning):
    """Jev was unavailable; affected detections were retained without quotation scores."""


@dataclass(frozen=True)
class QuotationValidation:
    """Jev quotation-use score; not authenticity, reference quality or calibrated accuracy."""

    model: str
    quotation_score: float | None
    threshold: float
    decision: Literal["keep", "reject", "unavailable"]
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model:
            raise ValueError("validation model must be a nonempty string")
        object.__setattr__(self, "threshold", _unit_score(self.threshold, "threshold"))
        if self.quotation_score is not None:
            object.__setattr__(
                self, "quotation_score", _unit_score(self.quotation_score, "quotation_score")
            )
        if self.decision == "unavailable":
            if self.quotation_score is not None or self.error not in {
                "timeout",
                "api_error",
                "invalid_response",
                "request_error",
            }:
                raise ValueError("unavailable validation needs a null score and an error code")
        elif self.decision in {"keep", "reject"}:
            if (
                self.quotation_score is None
                or self.error is not None
                or (self.quotation_score >= self.threshold) != (self.decision == "keep")
            ):
                raise ValueError("validation decision does not agree with score and threshold")
        else:
            raise ValueError("unknown validation decision")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.error is None:
            result.pop("error")
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> QuotationValidation:
        from ._serialization import validation

        return validation(value)


@dataclass(frozen=True)
class HadithRecord:
    hadith_key: str
    urn: int
    seq: int
    collection: str
    language: str
    hadith_number: str
    number_sort: int
    book_number: int
    in_book_number: int
    sunnah_url: str | None
    text: str
    grades: list[dict[str, Any]]
    n_grades: int
    grade_summary: str | None
    is_muallaq: bool
    additional_metadata: dict[str, Any]

    @classmethod
    def _from_source(cls, source: dict[str, Any]) -> HadithRecord:
        names = {f.name for f in fields(cls)} - {"additional_metadata"}
        return cls(
            **{name: deepcopy(source[name]) for name in names},
            additional_metadata={k: deepcopy(v) for k, v in source.items() if k not in names},
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> HadithRecord:
        """Restore a structurally validated, isolated snapshot without matching."""
        from ._serialization import record

        return record(value)

    def to_dict(self) -> dict[str, Any]:
        """Reproduce original source fields and values, without sharing mutable data."""
        result = asdict(self)
        extra = result.pop("additional_metadata")
        result.update(extra)
        return result


@dataclass(frozen=True)
class WordAlignment:
    input_token: int
    source_token: int
    input_start: int
    input_end: int
    source_start: int
    source_end: int
    errors: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> WordAlignment:
        """Restore a structurally validated, isolated snapshot without matching."""
        from ._serialization import word

        return word(value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OmittedSourceToken:
    source_token: int
    start: int
    end: int
    text: str
    term: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> OmittedSourceToken:
        """Restore a structurally validated, isolated snapshot without matching."""
        from ._serialization import omitted

        return omitted(value)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceOccurrence:
    start: int
    end: int
    text: str
    errors: int = 0
    missing_words: int = 0
    alignment: tuple[WordAlignment, ...] = ()
    omitted_source_tokens: tuple[OmittedSourceToken, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SourceOccurrence:
        """Restore a structurally validated, isolated snapshot without matching."""
        from ._serialization import occurrence

        return occurrence(value)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["alignment"] = [asdict(word) for word in self.alignment]
        result["omitted_source_tokens"] = [asdict(word) for word in self.omitted_source_tokens]
        return result


@dataclass(frozen=True)
class HadithReference:
    record: HadithRecord
    occurrences: tuple[SourceOccurrence, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> HadithReference:
        """Restore a structurally validated, isolated snapshot without matching."""
        from ._serialization import reference

        return reference(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "occurrences": [occurrence.to_dict() for occurrence in self.occurrences],
        }


@dataclass(frozen=True)
class Detection:
    start: int
    end: int
    text: str
    matched_words: int
    references: tuple[HadithReference, ...]
    errors: int = 0
    missing_words: int = 0
    validation: QuotationValidation | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Detection:
        """Restore a structurally validated, isolated snapshot without matching."""
        from ._serialization import detection

        return detection(value)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "matched_words": self.matched_words,
            "errors": self.errors,
            "missing_words": self.missing_words,
            "references": [reference.to_dict() for reference in self.references],
        }
        if self.validation is not None:
            result["validation"] = self.validation.to_dict()
        return result
