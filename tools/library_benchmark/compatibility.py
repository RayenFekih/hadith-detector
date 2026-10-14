"""Installed-wheel operation checks for the isolated supported-version environments."""

import argparse
import importlib
import json
import platform
import socket
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path


def run(output):
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    packages = {
        "numpy": "numpy",
        "pyroaring": "pyroaring",
        "msgspec": "msgspec",
        "orjson": "orjson",
        "marisa-trie": "marisa_trie",
        "rapidfuzz": "rapidfuzz",
    }
    for module in packages.values():
        importlib.import_module(module)
    from rapidfuzz.distance import Levenshtein

    assert Levenshtein.distance("سلام", "سلا", score_cutoff=1) == 1
    root = Path(__file__).resolve().parents[2]
    cache = root / ".cache/tmp"
    cache.mkdir(exist_ok=True)
    temporary = tempfile.mkdtemp(prefix="library-compat-", dir=cache)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_library_benchmark.py",
            "-q",
            "-p",
            "no:cacheprovider",
            "--tb=short",
            "--basetemp",
            temporary,
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )
    print(result.stdout, result.stderr, flush=True)
    if result.returncode or "12 passed" not in result.stdout:
        raise AssertionError("Adapter parity/installation checks failed or skipped")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "python": platform.python_version(),
                "os": platform.platform(),
                "versions": {name: version(name) for name in packages},
                "offline_native_imports": True,
                "tests_passed": 12,
                "rapidfuzz_backend": Levenshtein.distance.__module__,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
