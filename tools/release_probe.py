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
    """Execute README examples that can run with the network blocked."""
    examples = [
        code
        for code in re.findall(r"```python\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
        if code.split("\n", 1)[0] != "# release-probe: requires-network"
    ]
    if not examples:
        raise ValueError("README contains no Python examples to verify")
    namespace = {}
    with contextlib.redirect_stdout(io.StringIO()):
        for i, code in enumerate(examples, 1):
            exec(compile(code, f"README example {i}", "exec"), namespace)
    return len(examples)


def check_six_books(detector):
    # Manually selected Arabic source excerpts with externally assigned QuranLab keys.
    excerpts = (
        ("abudawud:1", "حدثنا عبد الله بن مسلمة بن قعنب القعنبي حدثنا"),
        ("ibnmajah:1", "حدثنا أبو بكر بن أبي شيبة قال حدثنا شريك"),
        ("nasai:1", "أخبرنا قتيبة بن سعيد قال حدثنا سفيان عن الزهري"),
        ("tirmidhi:1", "حدثنا قتيبة بن سعيد حدثنا أبو عوانة عن سماك"),
    )
    checked = 0
    for key, excerpt in excerpts:
        variants = (
            (excerpt, {}),
            (excerpt[:-1] + "ظ", {"max_errors": 1}),
            (" ".join(excerpt.split()[:3] + excerpt.split()[4:]), {"max_missing_words": 1}),
        )
        for text, budgets in variants:
            query = "🙂 " + text + "!"
            (match,) = detector.detect(query, min_match_words=len(text.split()), **budgets)
            assert (match.start, match.end, match.text) == (2, 2 + len(text), text), key
            assert key in {reference.record.hadith_key for reference in match.references}, key
            checked += 1
    overlap = "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى"
    (match,) = detector.detect(overlap, min_match_words=5)
    assert "bukhari:1" in {reference.record.hadith_key for reference in match.references}
    assert len({reference.record.collection for reference in match.references}) > 1
    assert not detector.detect("تدور الكواكب الصخرية حول نجوم بعيدة في مجرة أخرى")
    assert not detector.detect("عن النبي صلى الله عليه وسلم قال", min_match_words=9)
    return checked + 3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, required=True)
    parser.add_argument("--expectations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-two-books", action="store_true")
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
    scope = {"collections": ("bukhari", "muslim")} if args.baseline_two_books else {}
    for case in cases["cases"]:
        results = detector.detect(case["text"], **case["settings"], **scope)
        data = [r.to_dict() for r in results]
        assert hashlib.sha256(canonical(data)).hexdigest() == case["sha256"], case["id"]
        for result in results:
            assert case["text"][result.start : result.end] == result.text
            for reference in result.references:
                source = detector.get_hadith(reference.record.hadith_key)
                for occurrence in reference.occurrences:
                    assert source.text[occurrence.start : occurrence.end] == occurrence.text
        checked += 1
    expanded_cases = check_six_books(detector) if args.baseline_two_books else 0
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
        "six_book_acceptance_cases": expanded_cases,
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
