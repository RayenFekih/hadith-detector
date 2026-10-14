"""Prepare deterministic evidence and benchmark isolated fuzzy worker processes."""

import argparse
import gc
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib.metadata import distribution, version
from pathlib import Path

from tools.exact_benchmark.corpus import canonical, digest, load_corpus
from tools.exact_benchmark.indexes import Index

from . import oracle
from .common import exact_projection
from .distance import Backend
from .prototypes import STRATEGIES, Matcher
from .queries import generate, micro_pairs

ROOT = Path(__file__).resolve().parents[2]


def hashed(result):
    return hashlib.sha256(canonical(result)).hexdigest()


def verify_preparation(output):
    ready = json.loads((output / "ready.json").read_text(encoding="utf-8"))
    for name, field in (
        ("queries.json", "queries_sha256"),
        ("micro.json", "micro_sha256"),
        ("oracle-results.jsonl", "oracle_sha256"),
    ):
        if digest(output / name) != ready[field]:
            raise ValueError(f"Prepared experiment checksum mismatch: {name}")
    return ready


def prepare(corpus_dir, exact_dir, output, per_category=20, micro_count=10_000):
    if output.exists():
        raise ValueError("Output directory exists; choose a new directory")
    corpus = load_corpus(corpus_dir)
    suite = generate(corpus, per_category)
    output.mkdir(parents=True)
    (output / "queries.json").write_bytes(canonical(suite))
    (output / "micro.json").write_bytes(canonical(micro_pairs(corpus, micro_count)))
    expected = {}
    for i, q in enumerate(suite["queries"]):
        result, stats = oracle.detect(corpus, q["text"], q["minimum"], q["errors"], q["missing"])
        if q["presumed_negative"] and result:
            raise AssertionError(f"Presumed negative has fuzzy support: {q['id']}")
        expected[q["id"]] = {"hash": hashed(result), "stats": stats}
        with (output / "oracle-results.jsonl").open("ab") as stream:
            stream.write(canonical({"id": q["id"], "result": result}))
        print(f"oracle {i + 1}/{len(suite['queries'])}: {q['id']}", flush=True)
    exact = json.loads((exact_dir / "queries.json").read_text(encoding="utf-8"))
    exact_expected = json.loads((exact_dir / "oracle-results.json").read_text(encoding="utf-8"))
    if exact["corpus_fingerprint"] != corpus.fingerprint:
        raise ValueError("Exact query corpus mismatch")
    for i, q in enumerate(exact["queries"]):
        result, _ = oracle.detect(corpus, q["text"], q["minimum"], 0, 0)
        if hashed(exact_projection(result)) != exact_expected[q["id"]]:
            raise AssertionError(f"Zero-budget oracle regression: {q['id']}")
        print(f"exact oracle {i + 1}/{len(exact['queries'])}", flush=True)
    (output / "expected.json").write_bytes(canonical(expected))
    (output / "exact-queries.json").write_bytes(canonical(exact))
    (output / "exact-expected.json").write_bytes(canonical(exact_expected))
    (output / "ready.json").write_bytes(
        canonical(
            {
                "corpus_fingerprint": corpus.fingerprint,
                "queries_sha256": digest(output / "queries.json"),
                "micro_sha256": digest(output / "micro.json"),
                "oracle_sha256": digest(output / "oracle-results.jsonl"),
            }
        )
    )


def worker(corpus_dir, output, strategy, backend):
    import psutil

    ready = verify_preparation(output)
    process = psutil.Process()
    before = process.memory_info().rss
    started = time.perf_counter()
    distance = Backend(backend)
    setup = time.perf_counter() - started
    import_delta = process.memory_info().rss - before
    micro = json.loads((output / "micro.json").read_text(encoding="utf-8"))
    groups = {}
    for pair in micro["pairs"]:
        length = max(len(pair["a"]), len(pair["b"]))
        bucket = (
            "1-4" if length <= 4 else "5-8" if length <= 8 else "9-16" if length <= 16 else "17+"
        )
        cutoff = str(pair["cutoff"]) if pair["cutoff"] <= 3 else "unrestricted"
        groups.setdefault(f"length={bucket}/cutoff={cutoff}", []).append(pair)
    group_samples = {key: [] for key in groups}
    samples = []
    for _ in range(3):
        started = time.perf_counter()
        for key, pairs in sorted(groups.items()):
            batch_started = time.perf_counter()
            for p in pairs:
                if distance.uncached(p["a"], p["b"], p["cutoff"]) != p["expected"]:
                    raise AssertionError("Bounded distance mismatch")
            group_samples[key].append(time.perf_counter() - batch_started)
        samples.append(time.perf_counter() - started)
    started = time.perf_counter()
    corpus = load_corpus(corpus_dir)
    loading = time.perf_counter() - started
    if ready["corpus_fingerprint"] != corpus.fingerprint:
        raise ValueError("Corpus mismatch")
    started = time.perf_counter()
    matcher = Matcher(corpus, strategy, backend)
    construction = time.perf_counter() - started
    artifact = output / f"{strategy}-{backend}-index.jsonl"
    matcher.index.save(artifact)
    suite = json.loads((output / "queries.json").read_text(encoding="utf-8"))
    expected = json.loads((output / "expected.json").read_text(encoding="utf-8"))
    timings = {}
    q = suite["queries"][0]
    started = time.perf_counter()
    matcher.detect(q["text"], q["minimum"], q["errors"], q["missing"])
    first_call = time.perf_counter() - started
    for i, q in enumerate(suite["queries"]):
        # A correctness pass warms each case before the three warm repetitions.
        started = time.perf_counter()
        result, stats = matcher.detect(q["text"], q["minimum"], q["errors"], q["missing"])
        cold_seconds = time.perf_counter() - started
        if hashed(result) != expected[q["id"]]["hash"]:
            raise AssertionError(f"{strategy}/{backend} disagrees: {q['id']}")
        cold_stats = stats
        values = []
        for _ in range(3):
            started = time.perf_counter()
            result, stats = matcher.detect(q["text"], q["minimum"], q["errors"], q["missing"])
            values.append(time.perf_counter() - started)
            if hashed(result) != expected[q["id"]]["hash"]:
                raise AssertionError(f"Warm results disagree: {q['id']}")
        timings[q["id"]] = {
            "category": q["category"],
            "cold_seconds": cold_seconds,
            "seconds": values,
            "cold_stats": cold_stats,
            "warm_stats": stats,
        }
        print(f"{strategy}/{backend} {i + 1}/{len(suite['queries'])}", flush=True)
    matcher.index = None
    gc.collect()
    started = time.perf_counter()
    matcher.index = Index.load(corpus, artifact)
    reload_seconds = time.perf_counter() - started
    for q in suite["queries"]:
        result, _ = matcher.detect(q["text"], q["minimum"], q["errors"], q["missing"])
        if hashed(result) != expected[q["id"]]["hash"]:
            raise AssertionError(f"Reload results disagree: {q['id']}")
    exact = json.loads((output / "exact-queries.json").read_text(encoding="utf-8"))
    exact_expected = json.loads((output / "exact-expected.json").read_text(encoding="utf-8"))
    for i, q in enumerate(exact["queries"]):
        result, _ = matcher.detect(q["text"], q["minimum"], 0, 0)
        if hashed(exact_projection(result)) != exact_expected[q["id"]]:
            raise AssertionError(f"Exact regression: {q['id']}")
        print(f"{strategy}/{backend} exact {i + 1}/{len(exact['queries'])}", flush=True)
    if backend == "python" and any(k.startswith("rapidfuzz") for k in sys.modules):
        raise AssertionError("Pure Python worker imported RapidFuzz")
    info = process.memory_info()
    report = {
        "strategy": strategy,
        "backend": backend,
        "implementation": distance.implementation,
        "agreement": True,
        "import_seconds": setup,
        "import_rss_delta": import_delta,
        "loading_seconds": loading,
        "construction_seconds": construction,
        "reload_seconds": reload_seconds,
        "index_sha256": digest(artifact),
        "micro_pairs": len(micro["pairs"]),
        "first_call_seconds": first_call,
        "micro_seconds": samples,
        "micro_groups": {
            key: {"pairs": len(groups[key]), "seconds": values}
            for key, values in group_samples.items()
        },
        "timings": timings,
        "final_rss": info.rss,
        "os_peak_rss": getattr(info, "peak_wset", None),
        "cache_entries": len(matcher.backend.cache),
        "neighbor_entries": len(matcher.neighbors),
        "cache_evictions": matcher.backend.evictions,
    }
    (output / f"{strategy}-{backend}.json").write_bytes(canonical(report))


def run(corpus_dir, output):
    import psutil

    if not (output / "ready.json").exists():
        raise ValueError("Preparation did not finish successfully")
    verify_preparation(output)
    reports = []
    for strategy in STRATEGIES:
        for backend in ("python", "rapidfuzz"):
            name = f"{strategy}-{backend}"
            if (output / f"{name}.json").exists():
                raise ValueError("Worker output exists; use a new prepared directory")
            peak = 0
            with (output / f"{name}.log").open("w", encoding="utf-8") as log:
                child = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "tools.fuzzy_benchmark",
                        "worker",
                        "--corpus-dir",
                        str(corpus_dir),
                        "--output-dir",
                        str(output),
                        "--strategy",
                        strategy,
                        "--backend",
                        backend,
                    ],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                process = psutil.Process(child.pid)
                while child.poll() is None:
                    try:
                        peak = max(peak, process.memory_info().rss)
                    except psutil.NoSuchProcess:
                        pass
                    time.sleep(0.02)
                if child.returncode:
                    raise RuntimeError(f"Worker failed: {name}; see its log")
            report = json.loads((output / f"{name}.json").read_text(encoding="utf-8"))
            report["peak_rss"] = max(peak, report["os_peak_rss"] or 0)
            reports.append(report)
            print(f"{name}: complete", flush=True)
    if len({r["index_sha256"] for r in reports}) != 1:
        raise AssertionError("Prototype indexes are not byte-identical")
    for strategy in STRATEGIES:
        paired = [r for r in reports if r["strategy"] == strategy]
        for qid in paired[0]["timings"]:
            for key in ("cold_stats", "warm_stats"):
                if paired[0]["timings"][qid][key] != paired[1]["timings"][qid][key]:
                    raise AssertionError("Backends performed different logical work")
    dependency = distribution("rapidfuzz")
    summary = {
        "format_version": 1,
        "reports": reports,
        "environment": {
            "python": platform.python_version(),
            "unicode": __import__("unicodedata").unidata_version,
            "os": platform.platform(),
            "cpu": os.environ.get("PROCESSOR_IDENTIFIER", platform.processor()),
            "logical_cpus": os.cpu_count(),
            "rapidfuzz": version("rapidfuzz"),
            "psutil": version("psutil"),
        },
        "dependency": {
            "requires_python": dependency.metadata.get("Requires-Python"),
            "requires_dist": dependency.requires or [],
            "installed_bytes": sum(
                dependency.locate_file(f).stat().st_size
                for f in dependency.files
                if dependency.locate_file(f).is_file()
            ),
        },
        "fingerprints": {
            n: digest(output / n)
            for n in ("queries.json", "micro.json", "oracle-results.jsonl", "ready.json")
        },
        "code_fingerprints": {
            p.relative_to(ROOT).as_posix(): digest(p)
            for p in sorted(Path(__file__).parent.glob("*.py"))
        },
        "lock_sha256": digest(ROOT / "uv.lock"),
    }
    (output / "summary.json").write_bytes(canonical(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "worker", "run"))
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--exact-dir", type=Path)
    parser.add_argument("--strategy", choices=STRATEGIES, default="hybrid")
    parser.add_argument("--backend", choices=("python", "rapidfuzz"), default="python")
    parser.add_argument("--per-category", type=int, default=20)
    parser.add_argument("--micro-count", type=int, default=10_000)
    args = parser.parse_args()
    corpus, args.output_dir = args.corpus_dir.resolve(), args.output_dir.resolve()
    if args.command == "prepare":
        if args.exact_dir is None:
            parser.error("prepare requires --exact-dir")
        if args.per_category < 1 or args.micro_count < 1:
            parser.error("query and micro counts must be positive")
        prepare(
            corpus, args.exact_dir.resolve(), args.output_dir, args.per_category, args.micro_count
        )
    elif args.command == "worker":
        worker(corpus, args.output_dir, args.strategy, args.backend)
    else:
        run(corpus, args.output_dir)


if __name__ == "__main__":
    main()
