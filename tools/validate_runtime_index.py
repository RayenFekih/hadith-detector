"""Compare compact-runtime results to saved Phase 3A oracle fingerprints."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

from hadith_detector import HadithDetector
from hadith_detector._resources import canonical, checksum

ROOT = Path(__file__).resolve().parents[1]


def worker(index: Path, benchmark: Path, output: Path) -> None:
    import psutil

    suite = json.loads((benchmark / "queries.json").read_text(encoding="utf-8"))
    expected = json.loads((benchmark / "oracle-results.json").read_text(encoding="utf-8"))
    manifest = json.loads((index / "manifest.json").read_text(encoding="utf-8"))
    if manifest["source_fingerprint"] != suite["corpus_fingerprint"]:
        raise ValueError("Runtime corpus differs from benchmark corpus")
    started = time.perf_counter()
    detector = HadithDetector.from_directory(index)
    initialization = time.perf_counter() - started
    # Verify every original record field through the public snapshot/serializer.
    with (index / "records.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            if detector.get_hadith(record["hadith_key"]).to_dict() != record:
                raise AssertionError("Original-record serialization mismatch")
    cold = next(q for q in suite["queries"] if q["category"] == "embedded")
    started = time.perf_counter()
    detector.detect(cold["text"], min_match_words=cold["minimum"])
    first_call = time.perf_counter() - started
    timings = {}
    for number, query in enumerate(suite["queries"]):
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            results = detector.detect(query["text"], min_match_words=query["minimum"])
            samples.append(time.perf_counter() - started)
            projected = [
                {
                    "start": r.start,
                    "end": r.end,
                    "text": r.text,
                    "matched_words": r.matched_words,
                    "references": [
                        {
                            "hadith_key": ref.record.hadith_key,
                            "occurrences": [o.to_dict() for o in ref.occurrences],
                        }
                        for ref in r.references
                    ],
                }
                for r in results
            ]
            if hashlib.sha256(canonical(projected)).hexdigest() != expected[query["id"]]:
                raise AssertionError(f"Runtime disagrees with oracle: {query['id']}")
        timings[query["id"]] = {
            "category": query["category"],
            "seconds": samples,
            "stats": {
                "verified_occurrences": sum(
                    len(ref.occurrences) for r in results for ref in r.references
                ),
            },
        }
        if number % 20 == 0:
            print(f"runtime: verified/timed {number + 1}/{len(suite['queries'])}", flush=True)
    info = psutil.Process().memory_info()
    report = {
        "candidate": index.name,
        "agreement": True,
        "records_verified": manifest["counts"]["records"],
        "initialization_seconds": initialization,
        "first_call_seconds": first_call,
        "resource_bytes": sum(p.stat().st_size for p in index.iterdir()),
        "final_rss_bytes": info.rss,
        "os_peak_rss_bytes": getattr(info, "peak_wset", None),
        "timings": timings,
        "manifest_sha256": checksum(index / "manifest.json"),
    }
    output.write_bytes(canonical(report))


def run(indexes: list[Path], benchmark: Path, output: Path) -> None:
    import psutil

    if output.exists():
        raise ValueError("Validation output exists; choose a new directory")
    output.mkdir(parents=True)
    files = sorted(p.name for p in indexes[0].iterdir())
    expected = {name: checksum(indexes[0] / name) for name in files}
    if any(
        sorted(p.name for p in path.iterdir()) != files
        or any(checksum(path / name) != digest for name, digest in expected.items())
        for path in indexes[1:]
    ):
        raise AssertionError("Independent runtime builds are not byte-identical")
    reports = []
    for index in indexes:
        metrics = output / f"{index.name}.json"
        log = output / f"{index.name}.log"
        sampled_peak = 0
        with log.open("w", encoding="utf-8") as stream:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "tools.validate_runtime_index",
                    "worker",
                    "--index-dir",
                    str(index),
                    "--benchmark-dir",
                    str(benchmark),
                    "--output-dir",
                    str(metrics),
                ],
                cwd=ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            process = psutil.Process(child.pid)
            while child.poll() is None:
                try:
                    sampled_peak = max(sampled_peak, process.memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                time.sleep(0.01)
            if child.returncode:
                raise RuntimeError(f"Runtime verification failed; see {log}")
        report = json.loads(metrics.read_text(encoding="utf-8"))
        report["peak_rss_bytes"] = max(sampled_peak, report["os_peak_rss_bytes"] or 0)
        reports.append(report)
        print(f"{index.name}: oracle agreement passed", flush=True)
    summary = {
        "format_version": 1,
        "byte_identical_builds": True,
        "artifact_checksums": expected,
        "environment": {
            "python": platform.python_version(),
            "os": platform.platform(),
            "psutil": version("psutil"),
        },
        "indexes": reports,
    }
    (output / "summary.json").write_bytes(canonical(summary))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "worker"))
    parser.add_argument("--index-dir", type=Path, action="append", required=True)
    parser.add_argument("--benchmark-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    indexes = [p.resolve() for p in args.index_dir]
    if args.command == "worker":
        if len(indexes) != 1:
            parser.error("worker needs one index directory")
        worker(indexes[0], args.benchmark_dir.resolve(), args.output_dir.resolve())
    else:
        run(indexes, args.benchmark_dir.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
