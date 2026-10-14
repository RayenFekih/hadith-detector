"""Checks for the installed foundation, without relying on source-path imports."""

import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import hadith_detector


def test_version_matches_distribution() -> None:
    assert hadith_detector.__version__ == version("hadith-detector")
    assert set(hadith_detector.__all__) == {
        "__version__",
        "HadithDetector",
        "HadithRecord",
        "SourceOccurrence",
        "HadithReference",
        "Detection",
        "WordAlignment",
        "OmittedSourceToken",
    }


def test_import_outside_repository_has_no_filesystem_side_effects(tmp_path: Path) -> None:
    script = """
import socket
def forbid_network(*args, **kwargs):
    raise AssertionError('Import attempted network access')
socket.socket = forbid_network
import hadith_detector
from importlib.metadata import version
assert hadith_detector.__version__ == version('hadith-detector')
assert not hasattr(hadith_detector, 'detect')
assert not hasattr(hadith_detector, 'annotate')
"""
    subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        cwd=tmp_path,
        check=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert list(tmp_path.iterdir()) == []
