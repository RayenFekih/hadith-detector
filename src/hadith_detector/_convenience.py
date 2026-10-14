"""One synchronized, lazily populated convenience detector cache."""

from pathlib import Path
from threading import RLock

from .config import DetectorConfig
from .detector import HadithDetector
from .models import Detection, HadithRecord

_lock = RLock()
_entry: tuple[Path, HadithDetector] | None = None


def _detector(index_dir: str | Path) -> HadithDetector:
    global _entry
    directory = Path(index_dir).resolve()
    with _lock:
        if _entry is None or _entry[0] != directory:
            detector = HadithDetector(directory)
            _entry = directory, detector
        return _entry[1]


def clear_cache() -> None:
    """Forget the cached detector without interrupting any in-flight call."""
    global _entry
    with _lock:
        _entry = None


def detect(
    text: str,
    *,
    index_dir: str | Path,
    config: DetectorConfig | None = None,
    min_match_words: int | None = None,
    max_errors: int | None = None,
    max_missing_words: int | None = None,
) -> list[Detection]:
    """Detect using cached local resources and independent per-call defaults."""
    if config is not None and not isinstance(config, DetectorConfig):
        raise TypeError("config must be a DetectorConfig or None")
    effective = (config if config is not None else DetectorConfig())._override(
        min_match_words, max_errors, max_missing_words
    )
    return _detector(index_dir).detect(
        text,
        min_match_words=effective.min_match_words,
        max_errors=effective.max_errors,
        max_missing_words=effective.max_missing_words,
    )


def get_hadith(hadith_key: str, *, index_dir: str | Path) -> HadithRecord:
    """Retrieve an isolated source snapshot using the single cached detector."""
    return _detector(index_dir).get_hadith(hadith_key)
