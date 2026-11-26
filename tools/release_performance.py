"""Measure one scope from an isolated installation for the v0.4.0 comparison."""

import argparse
import json
import math
import platform
import statistics
import time
from pathlib import Path


def peak_rss():
    if platform.system() == "Windows":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("size", wintypes.DWORD),
                ("faults", wintypes.DWORD),
                ("peak_working_set", ctypes.c_size_t),
                ("other", ctypes.c_size_t * 7),
            ]

        counters = Counters()
        counters.size = ctypes.sizeof(counters)
        current = ctypes.windll.kernel32.GetCurrentProcess
        current.restype = wintypes.HANDLE
        info = ctypes.windll.psapi.GetProcessMemoryInfo
        info.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
        if not info(current(), ctypes.byref(counters), counters.size):
            raise ctypes.WinError()
        return counters.peak_working_set

    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if platform.system() == "Darwin" else peak * 1024


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--two-books", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    from hadith_detector import HadithDetector, __version__

    imported = time.perf_counter()
    scope = {"collections": ("bukhari", "muslim")} if args.two_books else {}
    detector = HadithDetector(**scope)
    initialized = time.perf_counter()
    saved = json.loads(args.cases.read_text(encoding="utf-8"))["cases"]
    report = {
        "version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "two_books": args.two_books,
        "import_seconds": imported - started,
        "initialization_seconds": initialized - imported,
    }
    negative = "تدور الكواكب الصخرية حول نجوم بعيدة في مجرة أخرى"
    for group in ("exact", "fuzzy"):
        settings = {"max_errors": 1, "max_missing_words": 1} if group == "fuzzy" else {}
        cases = [(item["text"], item["settings"]) for item in saved if item["group"] == group]
        cases.extend(
            [
                (" ".join([negative] * 10), settings),
                ("عن النبي صلى الله عليه وسلم قال", settings),
                (" ".join([negative, cases[0][0], negative]), cases[0][1]),
            ]
        )
        for query, options in cases:
            detector.detect(query, **options)
        samples = []
        for _ in range(5):
            for query, options in cases:
                started = time.perf_counter()
                detector.detect(query, **options)
                samples.append(time.perf_counter() - started)
        report[group] = {
            "samples": len(samples),
            "median_seconds": statistics.median(samples),
            "p95_seconds": sorted(samples)[math.ceil(0.95 * len(samples)) - 1],
        }
    report["peak_rss_bytes"] = peak_rss()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
