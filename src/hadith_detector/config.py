"""Immutable defaults for detection calls."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectorConfig:
    """Positive word minimum and independent nonnegative edit/omission budgets."""

    min_match_words: int = 5
    max_errors: int = 0
    max_missing_words: int = 0

    def __post_init__(self) -> None:
        for name, value, lower in (
            ("min_match_words", self.min_match_words, 1),
            ("max_errors", self.max_errors, 0),
            ("max_missing_words", self.max_missing_words, 0),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < lower:
                bound = "positive" if lower else "nonnegative"
                raise ValueError(f"{name} must be a {bound} integer")

    def _override(
        self, minimum: int | None, errors: int | None, missing: int | None
    ) -> "DetectorConfig":
        return DetectorConfig(
            self.min_match_words if minimum is None else minimum,
            self.max_errors if errors is None else errors,
            self.max_missing_words if missing is None else missing,
        )
