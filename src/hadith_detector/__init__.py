"""Offline exact Arabic Hadith detection using explicitly supplied local resources."""

from importlib.metadata import version

from .detector import HadithDetector
from .models import Detection, HadithRecord, HadithReference, SourceOccurrence

__version__ = version("hadith-detector")

__all__ = [
    "__version__",
    "HadithDetector",
    "HadithRecord",
    "SourceOccurrence",
    "HadithReference",
    "Detection",
]
