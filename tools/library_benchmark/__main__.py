"""Isolated library experiments against fixed oracle evidence, without production edits."""

import argparse
import gc
import hashlib
import json
import platform
import socket
import subprocess
import sys
import time
from importlib.metadata import distribution
from pathlib import Path

from hadith_detector import HadithDetector
from hadith_detector._resources import canonical, checksum, query_sequence
from hadith_detector._text import tokenize
from tools.exact_benchmark.corpus import Corpus
from tools.fuzzy_benchmark import oracle
from tools.fuzzy_benchmark.common import exact_projection
from tools.library_benchmark.adapters import VARIANTS, Codec, install_matcher, trie_resources
from tools.validate_fuzzy_runtime import hashed, project

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(index, evidence, output):
    output.mkdir()
    suite, ready = read(evidence / "queries.json"), read(evidence / "ready.json")
    for name, field in [
        ("queries.json", "queries_sha256"),
        ("oracle-results.jsonl", "oracle_sha256"),
    ]:
        assert checksum(evidence / name) == ready[field]
    # Two cases per category, worst-ish short case, and one of each large input size.
    queries = [
        q
        for q in suite["queries"]
        if q["id"].endswith(("-00", "-01"))
        or q["id"] in ("short-19", "common-19", "large-1024-0", "large-4096-0")
    ]
    wanted = {q["id"] for q in queries}
    expected = {}
    with (evidence / "oracle-results.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["id"] in wanted:
                expected[row["id"]] = hashed(row["result"])
    assert set(expected) == wanted
    detector = HadithDetector.from_directory(index)
    data = detector._resources
    corpus = Corpus(data.records, data.sequences, data.vocabulary, suite["corpus_fingerprint"])
    for target in (100, 250, 500):
        tokens = next(
            tokenize(r["text"]).tokens
            for r in data.records
            if len(tokenize(r["text"]).tokens) >= target
            and len({t.segment for t in tokenize(r["text"]).tokens}) == 1
        )
        words = [t.term for t in tokens[:target]]
        words[target // 2] += "ز"
        del words[target // 2 + 1]
        q = {
            "id": f"long-{target}",
            "category": "long",
            "text": " ".join(words),
            "minimum": 5,
            "errors": 1,
            "missing": 1,
        }
        results = detector.detect(q["text"], max_errors=1, max_missing_words=1)
        assert len(results) == 1 and results[0].matched_words == len(words)
        independent, _ = oracle.detect(corpus, q["text"], len(words), 1, 1)
        assert project(results) == independent
        expected[q["id"]] = hashed(independent)
        queries.append(q)
        print(f"prepared independent full-corpus long-{target}", flush=True)
    exact = read(evidence / "exact-queries.json")
    exact_expected = read(evidence / "exact-expected.json")
    for q in exact["queries"]:
        if q["id"].endswith(("-00", "-01")):
            q = dict(q, id="exact-" + q["id"], errors=0, missing=0, exact=True)
            expected[q["id"]] = exact_expected[q["id"][6:]]
            queries.append(q)
    payload = {
        "queries": queries,
        "expected": expected,
        "corpus_fingerprint": suite["corpus_fingerprint"],
        "manifest_sha256": checksum(index / "manifest.json"),
        "oracle_sha256": ready["oracle_sha256"],
        "versions": {"suite": 1},
    }
    (output / "suite.json").write_bytes(canonical(payload))


def footprint(name):
    package = distribution(name)
    return {
        "version": package.version,
        "installed_bytes": sum(
            package.locate_file(p).stat().st_size
            for p in package.files or ()
            if package.locate_file(p).is_file()
        ),
        "requires": package.requires or [],
        "wheel": package.read_text("WHEEL"),
    }


def worker(variant, index, output):
    import psutil

    suite = read(output / "suite.json")
    assert checksum(index / "manifest.json") == suite["manifest_sha256"]
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    process = psutil.Process()
    baseline = process.memory_info().rss
    modules = {
        "numpy": ["numpy"],
        "roaring": ["pyroaring"],
        "numpy-roaring": ["numpy", "pyroaring"],
        "msgspec": ["msgspec"],
        "orjson": ["orjson"],
        "marisa": ["marisa_trie"],
        "marisa-mmap": ["marisa_trie"],
        "rf-iter": ["rapidfuzz.process"],
        "rf-extract": ["rapidfuzz.process"],
    }.get(variant, [])
    started = time.perf_counter()
    for module in modules:
        __import__(module)
    imports = time.perf_counter() - started
    import_delta = process.memory_info().rss - baseline
    codec = Codec(variant if variant in ("msgspec", "orjson") else "baseline")
    if variant in ("msgspec", "orjson"):
        codec.install_loader()
    install_matcher(variant)
    started = time.perf_counter()
    detector = HadithDetector.from_directory(index)
    loading = time.perf_counter() - started
    build, reload_seconds, artifact_bytes = 0.0, 0.0, 0
    if variant.startswith("marisa"):
        started = time.perf_counter()
        directory = output / (variant + "-artifacts")
        detector._resources = trie_resources(detector._resources, directory)
        build = time.perf_counter() - started
        artifact_bytes = sum(p.stat().st_size for p in directory.iterdir())
        from dataclasses import replace

        import marisa_trie

        from tools.library_benchmark.adapters import TrieMapping

        started = time.perf_counter()
        method = "mmap" if variant == "marisa-mmap" else "load"
        vocabulary = getattr(marisa_trie.RecordTrie("<I"), method)(
            str(directory / "vocabulary.marisa")
        )
        trigrams = getattr(marisa_trie.RecordTrie("<I"), method)(str(directory / "trigrams.marisa"))
        detector._resources = replace(
            detector._resources,
            vocabulary=TrieMapping(vocabulary),
            trigrams=TrieMapping(trigrams, True),
        )
        reload_seconds = time.perf_counter() - started
        gc.collect()
    loaded_rss = process.memory_info().rss
    timings = []
    for i, q in enumerate(suite["queries"]):
        # First sample is application-cache cold; OS filesystem caches are not flushed.
        if detector._fuzzy is not None:
            detector._fuzzy.neighbors.clear()
            detector._fuzzy.neighbor_words = 0
            detector._fuzzy.distances.clear()
        detection, serialization, pipeline = [], [], []
        occurrence_count = 0
        for _ in range(4):
            started = time.perf_counter()
            results = detector.detect(
                q["text"],
                min_match_words=q["minimum"],
                max_errors=q["errors"],
                max_missing_words=q["missing"],
            )
            detection.append(time.perf_counter() - started)
            started = time.perf_counter()
            payload = [r.to_dict() for r in results]
            encoded = codec.encode(payload)
            serialization.append(time.perf_counter() - started)
            pipeline.append(detection[-1] + serialization[-1])
            projected = project(results)
            if q.get("exact"):
                projected = exact_projection(projected)
            if hashed(projected) != suite["expected"][q["id"]]:
                raise AssertionError(f"{variant}: {q['id']} oracle mismatch")
            if codec.loads(encoded) != payload or codec.encode(payload) != encoded:
                raise AssertionError("Codec values/determinism mismatch")
            occurrence_count = sum(len(ref.occurrences) for r in results for ref in r.references)
        timings.append(
            {
                "id": q["id"],
                "category": q["category"],
                "exact": q.get("exact", False),
                "detect": detection,
                "serialize": serialization,
                "pipeline": pipeline,
                "output_bytes": len(encoded),
                "occurrences": occurrence_count,
            }
        )
        if i % 10 == 0:
            print(f"{variant}: {i + 1}/{len(suite['queries'])}", flush=True)
        del results, payload, projected, encoded
        gc.collect()
    detection_memory = process.memory_info()
    steady_rss = detection_memory.rss
    detection_peak = getattr(detection_memory, "peak_wset", None)
    # Micro operations have no effect on the end-to-end timings recorded above.
    micro = {"vocabulary": [], "positions": [], "json": []}
    matcher = detector._fuzzy
    operation_queries = [q for q in suite["queries"] if not q.get("exact")][:8]
    operation_queries += [q for q in suite["queries"] if q["id"] in ("short-19", "common-19")]
    for q in operation_queries:
        tokens = tokenize(q["text"]).tokens
        if not tokens:
            continue
        query = query_sequence(tokens, detector._resources.vocabulary)
        baseline_matcher = __import__(
            "hadith_detector._fuzzy", fromlist=["FuzzyMatcher"]
        ).FuzzyMatcher(detector._resources)
        wanted = baseline_matcher.approximate(tokens[0].term, q["errors"])
        samples = []
        for _ in range(3):
            matcher.neighbors.clear()
            matcher.neighbor_words = 0
            matcher.distances.clear()
            started = time.perf_counter()
            actual = matcher.approximate(tokens[0].term, q["errors"])
            samples.append(time.perf_counter() - started)
            assert actual == wanted
        micro["vocabulary"].append({"id": q["id"], "seconds": samples, "terms": len(actual)})
        expected_positions = sorted(
            baseline_matcher.starts(tokens, query, 0, q["minimum"], q["errors"], q["missing"])
        )
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            actual = sorted(
                matcher.starts(tokens, query, 0, q["minimum"], q["errors"], q["missing"])
            )
            samples.append(time.perf_counter() - started)
            assert actual == expected_positions
        micro["positions"].append({"id": q["id"], "seconds": samples, "starts": len(actual)})
        packed = [(rid << 32) | position for rid, position in actual]
        if variant in ("roaring", "numpy-roaring"):
            from pyroaring import BitMap64

            blob = BitMap64(packed).serialize()
            assert list(BitMap64.deserialize(blob)) == packed
        elif variant == "numpy":
            import numpy as np

            blob = np.array(packed, dtype="<u8").tobytes()
            assert np.frombuffer(blob, dtype="<u8").tolist() == packed
        else:
            blob = canonical(packed)
            assert json.loads(blob) == packed
        micro["positions"][-1]["serialized_bytes"] = len(blob)
        assert blob == (
            BitMap64(packed).serialize()
            if variant in ("roaring", "numpy-roaring")
            else np.array(packed, dtype="<u8").tobytes()
            if variant == "numpy"
            else canonical(packed)
        )
        del baseline_matcher
    for filename in ("records.jsonl", "vocabulary.json", "manifest.json"):
        raw = (index / filename).read_bytes()
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            values = (
                [codec.loads(line) for line in raw.splitlines()]
                if filename.endswith("jsonl")
                else codec.loads(raw)
            )
            elapsed = time.perf_counter() - started
            started = time.perf_counter()
            encoded = (
                b"".join(codec.encode(v) for v in values)
                if filename.endswith("jsonl")
                else codec.encode(values)
            )
            samples.append({"decode": elapsed, "encode": time.perf_counter() - started})
            assert encoded == raw, "Current corpus canonical bytes changed"
        micro["json"].append(
            {
                "file": filename,
                "seconds": samples,
                "bytes": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
        del values, raw, encoded
    gc.collect()
    info = process.memory_info()
    dependencies = {
        name: footprint(name)
        for name in ("rapidfuzz", "numpy", "pyroaring", "msgspec", "orjson", "marisa-trie")
    }
    report = {
        "variant": variant,
        "agreement": True,
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "dependencies": dependencies,
        "import_seconds": imports,
        "import_rss_delta": import_delta,
        "load_seconds": loading,
        "build_seconds": build,
        "reload_seconds": reload_seconds,
        "key_artifact_bytes": artifact_bytes,
        "original_resource_bytes": sum(p.stat().st_size for p in index.iterdir()),
        "baseline_rss": baseline,
        "loaded_rss": loaded_rss,
        "detection_steady_rss": steady_rss,
        "detection_peak_rss": detection_peak,
        "final_rss": info.rss,
        "peak_rss": getattr(info, "peak_wset", None),
        "timings": timings,
        "micro": micro,
        "suite_sha256": checksum(output / "suite.json"),
        "production_fingerprints": {
            str(p.relative_to(ROOT)): checksum(p)
            for p in list((ROOT / "src/hadith_detector").glob("*.py"))
            + [ROOT / "pyproject.toml", ROOT / "uv.lock"]
        },
        "code_fingerprints": {
            str(p.relative_to(ROOT)): checksum(p) for p in Path(__file__).parent.glob("*.py")
        },
    }
    (output / (variant + ".json")).write_bytes(canonical(report))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "worker"))
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--variant", choices=VARIANTS)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.index_dir, args.evidence_dir, args.output_dir)
    elif args.command == "worker":
        worker(args.variant, args.index_dir, args.output_dir)
    else:
        for variant in VARIANTS:
            with (args.output_dir / (variant + ".log")).open("w", encoding="utf-8") as log:
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "tools.library_benchmark",
                        "worker",
                        "--variant",
                        variant,
                        "--index-dir",
                        str(args.index_dir),
                        "--output-dir",
                        str(args.output_dir),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
            print(f"completed {variant}", flush=True)


if __name__ == "__main__":
    main()
