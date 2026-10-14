"""Offline production/oracle agreement, full metadata timing and long narration checks."""

import argparse
import hashlib
import json
import platform
import socket
import time
from importlib.metadata import version
from pathlib import Path

from hadith_detector import HadithDetector
from hadith_detector._resources import canonical, checksum
from hadith_detector._text import tokenize
from tools.exact_benchmark.corpus import Corpus
from tools.fuzzy_benchmark import oracle
from tools.fuzzy_benchmark.common import exact_projection


def project(results):
    rows = []
    for item in results:
        row = item.to_dict()
        row["references"] = [
            {"hadith_key": ref["record"]["hadith_key"], "occurrences": ref["occurrences"]}
            for ref in row["references"]
        ]
        rows.append(row)
    return rows


def hashed(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def memory_probe(index, benchmark, output):
    """Fresh-process RSS without loading oracle traces or running oracle algorithms."""
    import psutil

    if output.exists():
        raise FileExistsError(output)
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    process = psutil.Process()
    baseline = process.memory_info().rss
    detector = HadithDetector.from_directory(index)
    loaded = process.memory_info().rss
    suite = json.loads((benchmark / "queries.json").read_text(encoding="utf-8"))
    expected = json.loads((benchmark / "expected.json").read_text(encoding="utf-8"))
    measurements = []
    for identity in ["edits-00", "short-19", "large-4096-0"]:
        query = next(q for q in suite["queries"] if q["id"] == identity)
        result = detector.detect(
            query["text"],
            min_match_words=query["minimum"],
            max_errors=query["errors"],
            max_missing_words=query["missing"],
        )
        if hashed(project(result)) != expected[identity]["hash"]:
            raise AssertionError(identity)
        info = process.memory_info()
        measurements.append(
            {"id": identity, "rss": info.rss, "peak": getattr(info, "peak_wset", None)}
        )
        del result
    info = process.memory_info()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(
        canonical(
            {
                "baseline_rss": baseline,
                "loaded_rss": loaded,
                "final_rss": info.rss,
                "peak_rss": getattr(info, "peak_wset", None),
                "measurements": measurements,
                "cpu": platform.processor(),
                "python": platform.python_version(),
                "code_fingerprints": {
                    p.name: checksum(p) for p in sorted(Path("src/hadith_detector").glob("*.py"))
                },
                "lock_sha256": checksum(Path("uv.lock")),
            }
        )
    )


def run(index, benchmark, output):
    import psutil

    if output.exists():
        raise FileExistsError(output)
    suite = json.loads((benchmark / "queries.json").read_text(encoding="utf-8"))
    ready = json.loads((benchmark / "ready.json").read_text(encoding="utf-8"))
    for name, field in [
        ("queries.json", "queries_sha256"),
        ("oracle-results.jsonl", "oracle_sha256"),
    ]:
        if checksum(benchmark / name) != ready[field]:
            raise ValueError(f"Oracle evidence checksum mismatch: {name}")
    expected = json.loads((benchmark / "expected.json").read_text(encoding="utf-8"))
    # Hash the actual independent oracle rows too, rather than trusting expected.json alone.
    with (benchmark / "oracle-results.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if hashed(row["result"]) != expected[row["id"]]["hash"]:
                raise ValueError("Oracle result/hash mismatch")
    manifest = json.loads((index / "manifest.json").read_text(encoding="utf-8"))
    if manifest["source_fingerprint"] != suite["corpus_fingerprint"]:
        raise ValueError("Corpus fingerprint mismatch")
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    started = time.perf_counter()
    detector = HadithDetector.from_directory(index)
    loading = time.perf_counter() - started
    timings = []
    for i, query in enumerate(suite["queries"]):
        samples = []
        for _ in range(4):
            started = time.perf_counter()
            result = detector.detect(
                query["text"],
                min_match_words=query["minimum"],
                max_errors=query["errors"],
                max_missing_words=query["missing"],
            )
            samples.append(time.perf_counter() - started)
            if hashed(project(result)) != expected[query["id"]]["hash"]:
                raise AssertionError(f"Production disagrees with oracle: {query['id']}")
        timings.append({"id": query["id"], "category": query["category"], "seconds": samples})
        if i % 20 == 0:
            print(f"fuzzy {i + 1}/{len(suite['queries'])}", flush=True)
    exact = json.loads((benchmark / "exact-queries.json").read_text(encoding="utf-8"))
    exact_expected = json.loads((benchmark / "exact-expected.json").read_text(encoding="utf-8"))
    for query in exact["queries"]:
        results = detector.detect(query["text"], min_match_words=query["minimum"])
        if hashed(exact_projection(project(results))) != exact_expected[query["id"]]:
            raise AssertionError(f"Exact regression: {query['id']}")
    print("exact 168/168", flush=True)
    # Real long source segments, with a corrupted middle word and an internal omission.
    # Independent oracle validates every returned identity, not just the originating record.
    long_cases = []
    for target in [100, 250, 500]:
        chosen = next(
            (record, tokenize(record["text"]).tokens)
            for record in detector._resources.records
            if len(tokenize(record["text"]).tokens) >= target
            and len({t.segment for t in tokenize(record["text"]).tokens}) == 1
        )
        record, tokens = chosen
        words = [t.term for t in tokens[:target]]
        words[target // 2] += "ز"
        del words[target // 2 + 1]
        text = " ".join(words)
        started = time.perf_counter()
        result = detector.detect(text, max_errors=1, max_missing_words=1)
        seconds = time.perf_counter() - started
        # Full input is supported, so no competing shorter passage can supersede it.
        if len(result) != 1 or result[0].text != text:
            raise AssertionError("Long quotation was not recovered completely")
        references = result[0].references
        texts = [ref.record.text for ref in references]
        corpus = Corpus.synthetic(texts)
        expected_long, _ = oracle.detect(corpus, text, 5, 1, 1)
        actual = project(result)
        for rid, ref in enumerate(actual[0]["references"], 1):
            ref["hadith_key"] = f"fixture:{rid}"
        if actual != expected_long:
            raise AssertionError("Long occurrence alignment disagrees with independent oracle")
        long_cases.append(
            {
                "source": record["hadith_key"],
                "tokens": len(words),
                "seconds": seconds,
                "references": len(references),
            }
        )
        print(f"long {target}: {seconds:.3f}s", flush=True)
    helper = detector._fuzzy
    info = psutil.Process().memory_info()
    report = {
        "agreement": True,
        "fuzzy_queries": len(timings),
        "exact_queries": len(exact["queries"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "rapidfuzz": version("rapidfuzz"),
        "backend": helper.kernel.__module__,
        "loading_seconds": loading,
        "timings": timings,
        "long_cases": long_cases,
        "final_rss_bytes": info.rss,
        "peak_rss_bytes": getattr(info, "peak_wset", None),
        "distance_cache_entries": len(helper.distances),
        "neighbor_cache_entries": len(helper.neighbors),
        "neighbor_cached_words": helper.neighbor_words,
        "fingerprints": {
            "manifest": checksum(index / "manifest.json"),
            "queries": checksum(benchmark / "queries.json"),
            "oracle": checksum(benchmark / "oracle-results.jsonl"),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--benchmark-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-only", action="store_true")
    args = parser.parse_args()
    (memory_probe if args.memory_only else run)(args.index_dir, args.benchmark_dir, args.output)
