"""One synchronized, lazily populated convenience detector cache."""

from collections.abc import Collection
from pathlib import Path
from threading import RLock

from ._annotation import render, validate
from ._bundled import directory
from .config import DetectorConfig
from .detector import HadithDetector, _accepted, _validator
from .models import Detection, HadithRecord

_lock = RLock()
_entry: tuple[Path, HadithDetector] | None = None


def _detector(index_dir: str | Path | None) -> HadithDetector:
    global _entry
    resolved = directory(index_dir)
    with _lock:
        if _entry is None or _entry[0] != resolved:
            detector = HadithDetector(index_dir)
            _entry = resolved, detector
        return _entry[1]


def clear_cache() -> None:
    """Forget the cached detector without interrupting any in-flight call."""
    global _entry
    with _lock:
        _entry = None


def detect(
    text: str,
    *,
    index_dir: str | Path | None = None,
    config: DetectorConfig | None = None,
    min_match_words: int | None = None,
    max_errors: int | None = None,
    max_missing_words: int | None = None,
    collections: Collection[str] | None = None,
    validation_model: str | None = None,
    validation_api_key: str | None = None,
    validation_api_base: str | None = None,
    validation_threshold: float = 0.5,
) -> list[Detection]:
    """Detect using cached bundled/local resources and independent per-call defaults."""
    if config is not None and not isinstance(config, DetectorConfig):
        raise TypeError("config must be a DetectorConfig or None")
    effective = (config if config is not None else DetectorConfig())._override(
        min_match_words, max_errors, max_missing_words
    )
    validator = _validator(
        validation_model, validation_api_key, validation_api_base, validation_threshold
    )
    matches = _detector(index_dir).detect(
        text,
        min_match_words=effective.min_match_words,
        max_errors=effective.max_errors,
        max_missing_words=effective.max_missing_words,
        collections=collections,
    )
    return _accepted(validator.evaluate(text, matches)) if validator is not None else matches


def annotate(
    text: str,
    *,
    index_dir: str | Path | None = None,
    format: str = "html",
    config: DetectorConfig | None = None,
    min_match_words: int | None = None,
    max_errors: int | None = None,
    max_missing_words: int | None = None,
    collections: Collection[str] | None = None,
    validation_model: str | None = None,
    validation_api_key: str | None = None,
    validation_api_base: str | None = None,
    validation_threshold: float = 0.5,
) -> str:
    """Annotate plain text using the single cached detector and per-call settings."""
    validate(text, format)
    if config is not None and not isinstance(config, DetectorConfig):
        raise TypeError("config must be a DetectorConfig or None")
    effective = (config if config is not None else DetectorConfig())._override(
        min_match_words, max_errors, max_missing_words
    )
    validator = _validator(
        validation_model, validation_api_key, validation_api_base, validation_threshold
    )
    if validator is not None:
        matches = _detector(index_dir).detect(
            text,
            min_match_words=effective.min_match_words,
            max_errors=effective.max_errors,
            max_missing_words=effective.max_missing_words,
            collections=collections,
        )
        return render(text, validator.evaluate(text, matches))
    return _detector(index_dir).annotate(
        text,
        format=format,
        min_match_words=effective.min_match_words,
        max_errors=effective.max_errors,
        max_missing_words=effective.max_missing_words,
        collections=collections,
    )


def get_hadith(hadith_key: str, *, index_dir: str | Path | None = None) -> HadithRecord:
    """Retrieve an isolated source snapshot using the single cached detector."""
    return _detector(index_dir).get_hadith(hadith_key)
