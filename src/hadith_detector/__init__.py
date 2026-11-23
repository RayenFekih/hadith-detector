"""Arabic Hadith matching, offline by default, with optional Jev quotation validation."""

from importlib.metadata import version

from ._convenience import annotate, clear_cache, detect, get_hadith
from .config import DetectorConfig
from .detector import HadithDetector
from .models import (
    ContextualValidationWarning,
    Detection,
    HadithRecord,
    HadithReference,
    OmittedSourceToken,
    QuotationValidation,
    SourceOccurrence,
    WordAlignment,
)

__version__ = version("hadith-detector")

__all__ = [
    "ContextualValidationWarning",
    "__version__",
    "HadithDetector",
    "DetectorConfig",
    "detect",
    "annotate",
    "get_hadith",
    "clear_cache",
    "HadithRecord",
    "SourceOccurrence",
    "HadithReference",
    "Detection",
    "WordAlignment",
    "OmittedSourceToken",
    "QuotationValidation",
]
