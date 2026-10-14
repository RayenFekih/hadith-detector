"""Summarize paired trials; never silently approve production adoption."""

import argparse
import math
import statistics
from pathlib import Path

from tools.marisa_trial.benchmark import read
from tools.marisa_trial.resources import canonical


def median(values):
    return statistics.median(values)


def p95(values):
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * 0.95) - 1]


def summarize(directory):
    pairs = [
        (read(directory / f"{i}-baseline.json"), read(directory / f"{i}-marisa.json"))
        for i in range(3)
    ]
    assert all(row["agreement"] for pair in pairs for row in pair)
    assert len({row["suite_sha256"] for pair in pairs for row in pair}) == 1
    assert len({str(row["source_fingerprints"]) for pair in pairs for row in pair}) == 1
    result = {
        "agreement": True,
        "rounds": 3,
        "warm_repetitions": 3,
        "timing_ratio": "MARISA/baseline; values above 1 are slower",
        "os_caches_flushed": False,
        "automatic_adoption": False,
    }
    for metric in (
        "steady_rss",
        "peak_rss",
        "loaded_rss",
        "load_seconds",
        "setup_seconds",
        "artifact_bytes",
    ):
        values = [[row[metric] for row in variant] for variant in zip(*pairs, strict=True)]
        result[metric] = {
            "baseline": median(values[0]),
            "marisa": median(values[1]),
            "baseline_range": [min(values[0]), max(values[0])],
            "marisa_range": [min(values[1]), max(values[1])],
        }
    saving = result["steady_rss"]["baseline"] - result["steady_rss"]["marisa"]
    result["memory_saving_mib"] = saving / 2**20
    result["memory_target_met"] = saving >= 60 * 2**20
    result["groups"] = {}
    for exact in (True, False):
        ratios, cold_ratios = [], []
        samples = [[], []]
        for baseline, native in pairs:
            for a, b in zip(baseline["timings"], native["timings"], strict=True):
                assert a["id"] == b["id"]
                if a["exact"] != exact:
                    continue
                ratios.append(median(b["seconds"][1:]) / median(a["seconds"][1:]))
                cold_ratios.append(b["seconds"][0] / a["seconds"][0])
                samples[0].extend(a["seconds"][1:])
                samples[1].extend(b["seconds"][1:])
        result["groups"]["exact" if exact else "fuzzy"] = {
            "paired_warm_ratio": median(ratios),
            "paired_cold_ratio": median(cold_ratios),
            "baseline_median_ms": median(samples[0]) * 1000,
            "marisa_median_ms": median(samples[1]) * 1000,
            "baseline_p95_ms": p95(samples[0]) * 1000,
            "marisa_p95_ms": p95(samples[1]) * 1000,
        }
    result["cases"] = {}
    for q in pairs[0][0]["timings"]:
        identity = q["id"]
        if identity not in (
            "short-00",
            "short-19",
            "common-19",
            "long-100",
            "long-250",
            "long-500",
            "large-1024-0",
            "large-4096-0",
        ):
            continue
        a = [
            sample
            for baseline, _ in pairs
            for t in baseline["timings"]
            if t["id"] == identity
            for sample in t["seconds"][1:]
        ]
        b = [
            sample
            for _, native in pairs
            for t in native["timings"]
            if t["id"] == identity
            for sample in t["seconds"][1:]
        ]
        result["cases"][identity] = {
            "baseline_median_ms": median(a) * 1000,
            "marisa_median_ms": median(b) * 1000,
            "baseline_p95_ms": p95(a) * 1000,
            "marisa_p95_ms": p95(b) * 1000,
        }
    result["first_fuzzy_ms"] = {
        "baseline": median(a["timings"][0]["seconds"][0] for a, _ in pairs) * 1000,
        "marisa": median(b["timings"][0]["seconds"][0] for _, b in pairs) * 1000,
    }
    result["needs_review"] = []
    if not result["memory_target_met"]:
        result["needs_review"].append("Memory saving below 60 MiB")
    if result["load_seconds"]["marisa"] > result["load_seconds"]["baseline"] * 1.1:
        result["needs_review"].append("Initialization regression exceeds 10%")
    for name, group in result["groups"].items():
        if group["paired_warm_ratio"] > 1.1:
            result["needs_review"].append(f"Typical {name} latency regression exceeds 10%")
        if group["marisa_p95_ms"] > group["baseline_p95_ms"] * 1.1:
            result["needs_review"].append(f"{name} p95 regression exceeds 10%")
    for name, case in result["cases"].items():
        if case["marisa_median_ms"] > case["baseline_median_ms"] * 1.1:
            result["needs_review"].append(f"{name} regression exceeds 10%")
    (directory / "summary.json").write_bytes(canonical(result))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(summarize(parser.parse_args().directory))
