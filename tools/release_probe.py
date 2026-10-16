"""Run against an installed wheel, outside the checkout, without network or writes.

This file is intentionally standalone: it imports no repository tooling.
"""

import argparse
import contextlib
import hashlib
import io
import json
import platform
import re
import socket
import sys
import time
from pathlib import Path


def canonical(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def run_readme(path: Path) -> int:
    """Execute the actual examples without depending on their variable names."""
    examples = re.findall(r"```python\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    if not examples:
        raise ValueError("README contains no Python examples to verify")
    namespace = {}
    with contextlib.redirect_stdout(io.StringIO()):
        for i, code in enumerate(examples, 1):
            exec(compile(code, f"README example {i}", "exec"), namespace)
    return len(examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, required=True)
    parser.add_argument("--expectations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    def forbidden(*args, **kwargs):
        raise AssertionError("Installed-library operation attempted network access")

    socket.socket = forbidden
    socket.create_connection = forbidden
    started = time.perf_counter()
    import hadith_detector as hd
    from hadith_detector import _convenience

    import_seconds = time.perf_counter() - started
    assert _convenience._entry is None
    root = Path(hd.__file__).resolve().parent
    bundle = root / "_data"
    assert bundle.is_dir()
    original = {
        p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in bundle.rglob("*")
        if p.is_file()
    }

    def read_only_resources(event, values):
        if event == "open" and isinstance(values[0], (str, bytes)):
            name, mode, flags = values
            if Path(name).resolve().is_relative_to(root):
                import os

                if (isinstance(mode, str) and any(c in mode for c in "wax+")) or flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
                ):
                    raise AssertionError("Attempt to write installed package resources")

    sys.addaudithook(read_only_resources)
    cases = json.loads(args.expectations.read_text(encoding="utf-8"))
    started = time.perf_counter()
    detector = hd.HadithDetector()
    initialization_seconds = time.perf_counter() - started
    assert detector.index_dir == bundle
    checked = 0
    for case in cases["cases"]:
        results = detector.detect(case["text"], **case["settings"])
        data = [r.to_dict() for r in results]
        assert hashlib.sha256(canonical(data)).hexdigest() == case["sha256"], case["id"]
        for result in results:
            assert case["text"][result.start : result.end] == result.text
            for reference in result.references:
                source = detector.get_hadith(reference.record.hadith_key)
                for occurrence in reference.occurrences:
                    assert source.text[occurrence.start : occurrence.end] == occurrence.text
        checked += 1
    explicit = hd.HadithDetector.from_directory(bundle)
    query = cases["cases"][0]
    assert explicit.detect(query["text"], **query["settings"]) == detector.detect(
        query["text"], **query["settings"]
    )
    example_count = run_readme(args.readme)
    assert original == {
        p.relative_to(bundle).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in bundle.rglob("*")
        if p.is_file()
    }
    hd.clear_cache()
    report = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "version": hd.__version__,
        "package": str(root),
        "import_seconds": import_seconds,
        "initialization_seconds": initialization_seconds,
        "saved_expectation_cases": checked,
        "readme_examples": example_count,
        "resource_files": len(original),
        "installed_package_bytes": sum(p.stat().st_size for p in root.rglob("*") if p.is_file()),
        "network_blocked": True,
        "resource_writes_blocked": True,
        "resource_hashes_unchanged": True,
    }
    args.output.write_bytes(canonical(report))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
