"""Offline, alternating fresh-process baseline/v2 acceptance measurements."""

import argparse
import gc
import json
import platform
import socket
import subprocess
import sys
import time
from collections import defaultdict
from importlib.metadata import version
from pathlib import Path

from hadith_detector import HadithDetector
from hadith_detector._resources import canonical, checksum
from tools.fuzzy_benchmark.common import exact_projection
from tools.validate_fuzzy_runtime import hashed, project

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def install_trial():
    """Only the child process's loader is replaced; no production files change."""
    import hadith_detector.detector as runtime
    from tools.marisa_trial.resources import Resources

    runtime.Resources = Resources
    original = runtime.FuzzyMatcher.__init__

    def initialize(self, resources):
        original(self, resources)
        self.words = dict(sorted(self.words.items()))
        self.buckets = defaultdict(list)
        for wid, word in self.words.items():
            self.buckets[len(word)].append(wid)

    runtime.FuzzyMatcher.__init__ = initialize


def worker(args):
    import psutil

    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    suite = read(args.suite)
    index = args.baseline if args.variant == "baseline" else args.trial
    if checksum(args.baseline / "manifest.json") != suite["manifest_sha256"]:
        raise ValueError("Baseline manifest differs from the oracle suite")
    if read(index / "manifest.json")["source_fingerprint"] != suite["corpus_fingerprint"]:
        raise ValueError("Source corpus differs from the oracle suite")
    if args.variant == "baseline":
        assert "marisa_trie" not in sys.modules
    process = psutil.Process()
    started = time.perf_counter()
    if args.variant == "marisa":
        install_trial()
    setup = time.perf_counter() - started
    started = time.perf_counter()
    detector = HadithDetector.from_directory(index)
    loading = time.perf_counter() - started
    loaded_rss = process.memory_info().rss
    timings = []
    for i, q in enumerate(suite["queries"]):
        if detector._fuzzy is not None:
            detector._fuzzy.distances.clear()
            detector._fuzzy.neighbors.clear()
            detector._fuzzy.neighbor_words = 0
        samples = []
        for _ in range(4):
            started = time.perf_counter()
            results = detector.detect(
                q["text"],
                min_match_words=q["minimum"],
                max_errors=q["errors"],
                max_missing_words=q["missing"],
            )
            samples.append(time.perf_counter() - started)
            projected = project(results)
            if q.get("exact"):
                projected = exact_projection(projected)
            if hashed(projected) != suite["expected"][q["id"]]:
                raise AssertionError(f"Oracle mismatch: {q['id']}")
            # Include the same complete public serialization allocations in both workers.
            canonical([r.to_dict() for r in results])
        timings.append(
            {
                "id": q["id"],
                "exact": q.get("exact", False),
                "category": q["category"],
                "seconds": samples,
            }
        )
        del results, projected
        gc.collect()
        if i % 10 == 0:
            print(f"{args.variant}: {i + 1}/{len(suite['queries'])}", flush=True)
    memory = process.memory_info()
    report = {
        "agreement": True,
        "variant": args.variant,
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "setup_seconds": setup,
        "load_seconds": loading,
        "loaded_rss": loaded_rss,
        "steady_rss": memory.rss,
        "peak_rss": getattr(memory, "peak_wset", None),
        "timings": timings,
        "suite_sha256": checksum(args.suite),
        "manifest_sha256": checksum(index / "manifest.json"),
        "artifact_bytes": sum(p.stat().st_size for p in index.iterdir()),
        "rapidfuzz": version("rapidfuzz"),
        "marisa": version("marisa-trie") if args.variant == "marisa" else None,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): checksum(p)
            for p in [
                *Path("src/hadith_detector").glob("*.py"),
                Path("pyproject.toml"),
                Path("uv.lock"),
            ]
            if p.is_file()
            for p in [p.resolve()]
        },
        "trial_fingerprints": {
            str(p.relative_to(ROOT)): checksum(p) for p in Path(__file__).parent.glob("*.py")
        },
        "cache_sizes": {
            "distance": len(detector._fuzzy.distances),
            "neighbors": len(detector._fuzzy.neighbors),
        },
    }
    args.report.write_bytes(canonical(report))


def full_parity(args):
    """Use all saved Phase 3/4 oracle expectations, outside timed memory workers."""
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    install_trial()
    detector = HadithDetector.from_directory(args.trial)
    expected = read(args.evidence / "expected.json")
    queries = read(args.evidence / "queries.json")["queries"]
    for i, q in enumerate(queries):
        result = detector.detect(
            q["text"],
            min_match_words=q["minimum"],
            max_errors=q["errors"],
            max_missing_words=q["missing"],
        )
        assert hashed(project(result)) == expected[q["id"]]["hash"], q["id"]
        if i % 20 == 0:
            print(f"full fuzzy {i + 1}/{len(queries)}", flush=True)
    exact = read(args.evidence / "exact-queries.json")["queries"]
    expected = read(args.evidence / "exact-expected.json")
    for q in exact:
        result = detector.detect(q["text"], min_match_words=q["minimum"])
        assert hashed(exact_projection(project(result))) == expected[q["id"]], q["id"]
    args.report.write_bytes(
        canonical(
            {
                "agreement": True,
                "fuzzy": len(queries),
                "exact": len(exact),
                "manifest_sha256": checksum(args.trial / "manifest.json"),
            }
        )
    )


def run(args):
    args.output.mkdir()
    for round_id in range(3):
        order = ("baseline", "marisa") if round_id % 2 == 0 else ("marisa", "baseline")
        for variant in order:
            report = args.output / f"{round_id}-{variant}.json"
            with report.with_suffix(".log").open("w", encoding="utf-8") as log:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "tools.marisa_trial.benchmark",
                        "worker",
                        "--baseline",
                        str(args.baseline),
                        "--trial",
                        str(args.trial),
                        "--suite",
                        str(args.suite),
                        "--variant",
                        variant,
                        "--report",
                        str(report),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            print(f"round {round_id}: {variant} complete", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "worker", "parity"))
    for name in ("baseline", "trial", "suite", "output", "report", "evidence"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--variant", choices=("baseline", "marisa"))
    args = parser.parse_args()
    for name in ("baseline", "trial", "suite", "output", "report", "evidence"):
        value = getattr(args, name)
        if value is not None:
            setattr(args, name, value.resolve())
    {"run": run, "worker": worker, "parity": full_parity}[args.command](args)


if __name__ == "__main__":
    main()
