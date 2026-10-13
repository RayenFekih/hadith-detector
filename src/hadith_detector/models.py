"""Provisional typed exact-match results, with independent metadata snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, fields
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        """Reproduce original source fields and values, without sharing mutable data."""
        result = asdict(self)
        extra = result.pop("additional_metadata")
        result.update(extra)
        return result


@dataclass(frozen=True)
class SourceOccurrence:
    start: int
    end: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HadithReference:
    record: HadithRecord
    occurrences: tuple[SourceOccurrence, ...]

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "matched_words": self.matched_words,
            "references": [reference.to_dict() for reference in self.references],
        }
