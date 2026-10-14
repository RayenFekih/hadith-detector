"""Validate the installed production v2 engine offline against all saved oracles."""

import argparse
import gc
import json
import platform
import socket
import time
from importlib.metadata import version
from pathlib import Path

from hadith_detector import HadithDetector
from hadith_detector._resources import canonical, checksum
from tools.fuzzy_benchmark.common import exact_projection
from tools.validate_fuzzy_runtime import hashed, project


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(index, evidence, representative, output):
    import psutil

    if output.exists():
        raise FileExistsError(output)
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    suite = read(evidence / "queries.json")
    manifest = read(index / "manifest.json")
    if manifest["source_fingerprint"] != suite["corpus_fingerprint"]:
        raise ValueError("Corpus fingerprint differs from saved oracle evidence")
    started = time.perf_counter()
    detector = HadithDetector.from_directory(index)
    loading = time.perf_counter() - started
    for record in detector._resources.records:
        if detector.get_hadith(record["hadith_key"]).to_dict() != record:
            raise AssertionError("Complete original metadata round-trip mismatch")
    process = psutil.Process()
    loaded_rss = process.memory_info().rss
    timings = []

    def check(q, expected, exact=False):
        started = time.perf_counter()
        results = detector.detect(
            q["text"],
            min_match_words=q["minimum"],
            max_errors=q.get("errors", 0),
            max_missing_words=q.get("missing", 0),
        )
        seconds = time.perf_counter() - started
        projected = project(results)
        if exact:
            projected = exact_projection(projected)
        if hashed(projected) != expected:
            raise AssertionError(f"Oracle mismatch: {q['id']}")
        for result in results:
            assert q["text"][result.start : result.end] == result.text
            for reference in result.references:
                original = detector.get_hadith(reference.record.hadith_key).text
                assert reference.record.text == original
                for occurrence in reference.occurrences:
                    assert original[occurrence.start : occurrence.end] == occurrence.text
        return seconds

    expected = read(evidence / "expected.json")
    for i, q in enumerate(suite["queries"]):
        seconds = check(q, expected[q["id"]]["hash"])
        timings.append({"id": q["id"], "seconds": seconds})
        if i % 20 == 0:
            print(f"fuzzy {i + 1}/{len(suite['queries'])}", flush=True)
    exact = read(evidence / "exact-queries.json")["queries"]
    exact_expected = read(evidence / "exact-expected.json")
    for q in exact:
        check(q, exact_expected[q["id"]], True)
    representative_suite = read(representative)
    if representative_suite["corpus_fingerprint"] != manifest["source_fingerprint"]:
        raise ValueError("Representative corpus fingerprint differs")
    for q in representative_suite["queries"]:
        check(q, representative_suite["expected"][q["id"]], q.get("exact", False))
    gc.collect()
    memory = process.memory_info()
    report = {
        "agreement": True,
        "index_version": manifest["versions"]["index"],
        "fuzzy_cases": len(suite["queries"]),
        "exact_cases": len(exact),
        "representative_cases": len(representative_suite["queries"]),
        "metadata_records": len(detector._resources.records),
        "python": platform.python_version(),
        "os": platform.platform(),
        "rapidfuzz": version("rapidfuzz"),
        "marisa": version("marisa-trie"),
        "load_seconds": loading,
        "loaded_rss": loaded_rss,
        "steady_rss": memory.rss,
        "peak_rss": getattr(memory, "peak_wset", None),
        "timings": timings,
        "offline": True,
        "fingerprints": {
            "manifest": checksum(index / "manifest.json"),
            "queries": checksum(evidence / "queries.json"),
            "expected": checksum(evidence / "expected.json"),
            "representative": checksum(representative),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(report))
    print(
        f"Passed: {report['fuzzy_cases']} fuzzy, {report['exact_cases']} exact, "
        f"{report['representative_cases']} representative",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--representative-suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(
        args.index_dir.resolve(),
        args.evidence_dir.resolve(),
        args.representative_suite.resolve(),
        args.output.resolve(),
    )
