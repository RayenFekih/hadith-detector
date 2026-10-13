"""Run reproducible exact-index experiments in separate worker processes."""

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path

from . import oracle
from .corpus import canonical, digest, load_corpus
from .indexes import CANDIDATES, Index
from .queries import generate

ROOT = Path(__file__).resolve().parents[2]


def result_hash(result: list[dict]) -> str:
    return hashlib.sha256(canonical(result)).hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def worker(corpus_dir: Path, output: Path, candidate: str) -> None:
    import psutil

    started = time.perf_counter()
    corpus = load_corpus(corpus_dir)
    loading = time.perf_counter() - started
    suite = json.loads((output / "queries.json").read_text(encoding="utf-8"))
    if suite["corpus_fingerprint"] != corpus.fingerprint:
        raise ValueError("Query/corpus fingerprint mismatch")
    expected_path = output / "oracle-results.json"
    expected = (
        json.loads(expected_path.read_text(encoding="utf-8")) if candidate != "oracle" else None
    )
    artifact = output / f"{candidate}.jsonl"
    index = None
    started = time.perf_counter()
    if candidate != "oracle":
        index = Index(corpus, candidate)
    construction = time.perf_counter() - started
    timings = {}
    correctness = {}
    all_stats = {}

    def detect(query):
        return (
            oracle.detect(corpus, query["text"], query["minimum"])
            if index is None
            else index.detect(query["text"], query["minimum"])
        )

    cold_query = next(q for q in suite["queries"] if q["category"] == "embedded")
    started = time.perf_counter()
    cold_result, _ = detect(cold_query)
    first_call = time.perf_counter() - started
    del cold_result
    for number, query in enumerate(suite["queries"]):
        result, stats = detect(query)
        correctness[query["id"]] = result_hash(result)
        all_stats[query["id"]] = stats
        if expected is not None and correctness[query["id"]] != expected[query["id"]]:
            raise AssertionError(f"{candidate} disagrees before serialization: {query['id']}")
        del result
        if number % 20 == 0:
            print(f"{candidate}: verified {number + 1}/{len(suite['queries'])}", flush=True)
    serialization = reloading = 0.0
    artifact_size = 0
    deterministic = None
    if index is not None:
        started = time.perf_counter()
        index.save(artifact)
        serialization = time.perf_counter() - started
        artifact_size = artifact.stat().st_size
        first_digest = digest(artifact)
        del index
        index = None
        gc.collect()
        started = time.perf_counter()
        index = Index.load(corpus, artifact)
        reloading = time.perf_counter() - started
    for number, query in enumerate(suite["queries"]):
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            result, stats = detect(query)
            samples.append(time.perf_counter() - started)
            if result_hash(result) != correctness[query["id"]] or stats != all_stats[query["id"]]:
                raise AssertionError(f"Roundtrip/repeat disagreement: {candidate} {query['id']}")
            del result
        timings[query["id"]] = {
            "category": query["category"],
            "seconds": samples,
            "stats": all_stats[query["id"]],
        }
        if number % 20 == 0:
            print(f"{candidate}: timed {number + 1}/{len(suite['queries'])}", flush=True)
    if candidate == "oracle":
        expected_path.write_bytes(canonical(correctness))
    else:
        del index
        index = None
        gc.collect()
        rebuilt = Index(corpus, candidate)
        temporary = output / f"{candidate}-rebuild.jsonl"
        rebuilt.save(temporary)
        deterministic = digest(temporary) == first_digest
        temporary.unlink()
        if not deterministic:
            raise AssertionError("Non-deterministic prototype artifact")
        del rebuilt
        gc.collect()
    info = psutil.Process().memory_info()
    report = {
        "candidate": candidate,
        "corpus_loading_seconds": loading,
        "construction_seconds": construction,
        "serialization_seconds": serialization,
        "reload_seconds": reloading,
        "first_call_seconds": first_call,
        "serialized_bytes": artifact_size,
        "deterministic_rebuild": deterministic,
        "agreement": True,
        "timings": timings,
        "final_rss_bytes": info.rss,
        "os_peak_rss_bytes": getattr(info, "peak_wset", None),
    }
    (output / f"{candidate}-metrics.json").write_bytes(canonical(report))


def run(corpus_dir: Path, output: Path, per_category: int) -> None:
    import psutil

    if output.exists():
        raise ValueError("Benchmark output exists; choose a new directory")
    corpus = load_corpus(corpus_dir)
    suite = generate(corpus, per_category)
    output.mkdir(parents=True)
    (output / "queries.json").write_bytes(canonical(suite))
    fingerprint = corpus.fingerprint
    del corpus
    gc.collect()
    reports = []
    for candidate in ("oracle", *CANDIDATES):
        command = [
            sys.executable,
            "-m",
            "tools.exact_benchmark",
            "worker",
            "--corpus-dir",
            str(corpus_dir),
            "--output-dir",
            str(output),
            "--candidate",
            candidate,
        ]
        log_path = output / f"{candidate}.log"
        sampled_peak = 0
        with log_path.open("w", encoding="utf-8") as log:
            child = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=log,
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
                raise RuntimeError(f"{candidate} failed; see {log_path}")
        report = json.loads((output / f"{candidate}-metrics.json").read_text(encoding="utf-8"))
        report["peak_rss_bytes"] = max(sampled_peak, report["os_peak_rss_bytes"] or 0)
        reports.append(report)
        print(
            f"{candidate}: passed, peak RSS {report['peak_rss_bytes'] / 1024**2:.1f} MiB",
            flush=True,
        )
    code_files = sorted(Path(__file__).parent.glob("*.py"))
    code_files.append(ROOT / "src/hadith_detector/_text.py")
    environment = {
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "logical_cpus": psutil.cpu_count(),
        "physical_cpus": psutil.cpu_count(logical=False),
        "ram_bytes": psutil.virtual_memory().total,
        "psutil": version("psutil"),
        "unicode": __import__("unicodedata").unidata_version,
        "uv_lock_sha256": digest(ROOT / "uv.lock"),
        "code_fingerprints": {
            str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(
                p.read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest()
            for p in code_files
        },
    }
    summary = {
        "benchmark_version": 1,
        "corpus_fingerprint": fingerprint,
        "queries_sha256": digest(output / "queries.json"),
        "seed": 42,
        "per_category": per_category,
        "warm_repetitions": 3,
        "environment": environment,
        "candidates": reports,
    }
    (output / "summary.json").write_bytes(canonical(summary))
    write_markdown(summary, output / "report.md")


def write_markdown(summary: dict, path: Path) -> None:
    lines = [
        "# Phase 3A measured index benchmark",
        "",
        "## Environment and method",
        "",
        f"- Python {summary['environment']['python']}; {summary['environment']['os']}.",
        f"- CPU: {summary['environment']['cpu']}; "
        f"logical CPUs: {summary['environment']['logical_cpus']}.",
        f"- Corpus fingerprint: `{summary['corpus_fingerprint']}`.",
        f"- Queries SHA-256: `{summary['queries_sha256']}`.",
        f"- Seed 42; {summary['per_category']} queries in each of eight categories "
        "plus eight larger inputs.",
        "- Three warm repetitions per query; complete results agree with the independent oracle.",
        "- Each candidate runs in a fresh subprocess. Peak RSS includes corpus, index, "
        "serialization and result allocation.",
        "- Corpus loading includes checksums and regeneration of mapped tokens for integrity; "
        "it is not a production startup estimate.",
        "- Warm times include tokenization, verification, selection and complete result "
        "construction; result hashing is outside timing.",
        "- Prototype formats are uncompressed canonical JSONL; "
        "n-gram sizes include unigram fallback.",
        "",
        "## Build, loading and memory",
        "",
        "| Candidate | Build s | Write s | Reload s | First call ms | Index MiB | Peak RSS MiB |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["candidates"]:
        cells = [
            row["candidate"],
            f"{row['construction_seconds']:.3f}",
            f"{row['serialization_seconds']:.3f}",
            f"{row['reload_seconds']:.3f}",
            f"{row['first_call_seconds'] * 1000:.3f}",
            f"{row['serialized_bytes'] / 1024**2:.2f}",
            f"{row['peak_rss_bytes'] / 1024**2:.1f}",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Warm query categories",
        "",
        "| Candidate | Category | Median ms | p95 ms | Retrieved candidates | "
        "Verified source occurrences |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["candidates"]:
        for category in sorted({q["category"] for q in row["timings"].values()}):
            queries = [q for q in row["timings"].values() if q["category"] == category]
            values = [s * 1000 for q in queries for s in q["seconds"]]
            cells = [
                row["candidate"],
                category,
                f"{statistics.median(values):.3f}",
                f"{percentile(values, 0.95):.3f}",
                f"{sum(q['stats']['candidates'] for q in queries):,}",
                f"{sum(q['stats']['verified_occurrences'] for q in queries):,}",
            ]
            lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "All indexed candidates agree before and after reload, and their independent",
        "rebuilds produce identical artifact checksums. Performance is machine/workload",
        "specific; these are exact lexical correctness checks, not semantic accuracy",
        "or fuzzy matching evaluation.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "worker"))
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate", choices=("oracle", *CANDIDATES))
    parser.add_argument("--per-category", type=int, default=20)
    args = parser.parse_args()
    if args.per_category < 1:
        parser.error("--per-category must be positive")
    if args.command == "worker":
        if args.candidate is None:
            parser.error("worker needs --candidate")
        worker(args.corpus_dir.resolve(), args.output_dir.resolve(), args.candidate)
    else:
        run(args.corpus_dir.resolve(), args.output_dir.resolve(), args.per_category)


if __name__ == "__main__":
    main()
