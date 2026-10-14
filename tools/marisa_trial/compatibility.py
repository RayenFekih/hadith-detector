"""Read Windows-prebuilt native resources offline in each supported interpreter."""

import argparse
import json
import platform
import socket
from importlib.metadata import version
from pathlib import Path

from hadith_detector import HadithDetector
from tools.marisa_trial.benchmark import install_trial
from tools.marisa_trial.resources import canonical, checksum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    install_trial()
    detector = HadithDetector.from_directory(args.index)
    for record in detector._resources.records[:3]:
        text = record["text"]
        assert detector.get_hadith(record["hadith_key"]).text == text
        results = detector.detect(text, min_match_words=5)
        assert any(
            record["hadith_key"] == ref.record.hadith_key
            for result in results
            for ref in result.references
        )
        for result in results:
            assert text[result.start : result.end] == result.text
        detector.detect(text, max_errors=1, max_missing_words=1)
    report = {
        "python": platform.python_version(),
        "os": platform.platform(),
        "marisa": version("marisa-trie"),
        "offline": True,
        "prebuilt_load_and_matching": True,
        "manifest_sha256": checksum(args.index / "manifest.json"),
    }
    args.report.write_bytes(canonical(report))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
