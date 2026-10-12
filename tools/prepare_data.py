"""Repository-only pinned corpus acquisition and offline preprocessing.

Run with ``uv run --group data python -m tools.prepare_data --help``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

from hadith_detector._text import NORMALIZATION_VERSION, tokenize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "tools" / "source-lock.json"
VERSIONS = {"records": 1, "tokens": 1, "manifest": 1, "normalization": NORMALIZATION_VERSION}
OUTPUTS = ("records.jsonl", "tokens.jsonl", "validation.json", "manifest.json")


class DataError(ValueError):
    """Invalid source data, incompatible build, or failed integrity verification."""


def canonical(value: Any) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    def invalid(value: str) -> None:
        raise DataError(f"Non-JSON numeric value: {value}")

    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)
    except (OSError, ValueError) as exc:
        raise DataError(f"Cannot read JSON {path}: {exc}") from exc


def read_lock(path: Path) -> dict[str, Any]:
    lock = _json(path)
    if not isinstance(lock, dict) or lock.get("lock_version") != 1:
        raise DataError("Unsupported source lock")

    def hex_digest(value: Any, length: int) -> bool:
        return (
            isinstance(value, str)
            and len(value) == length
            and all(c in "0123456789abcdef" for c in value)
        )

    if not hex_digest(lock.get("revision"), 40):
        raise DataError("Source lock requires a full commit revision")
    if not isinstance(lock.get("repository"), str) or not lock["repository"]:
        raise DataError("Source lock requires a repository")
    if (
        not isinstance(lock.get("files"), list)
        or not lock["files"]
        or not isinstance(lock.get("configs"), list)
        or not lock["configs"]
    ):
        raise DataError("Source lock must include files and configurations")
    filenames = set()
    for entry in lock["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise DataError("Invalid source file entry")
        name = entry["path"]
        if (
            not name
            or Path(name).is_absolute()
            or ".." in Path(name).parts
            or "\\" in name
            or ":" in name
        ):
            raise DataError("Source filenames must be safe relative paths")
        if name in filenames or not hex_digest(entry.get("sha256"), 64):
            raise DataError("Duplicate filename or invalid checksum in source lock")
        filenames.add(name)
    collections = set()
    for config in lock["configs"]:
        if not isinstance(config, dict) or not isinstance(config.get("collection"), str):
            raise DataError("Invalid configuration entry")
        collection = config["collection"]
        if (
            collection in collections
            or config.get("name") != f"{collection}-ar"
            or config.get("path") not in filenames
            or not _integer(config.get("expected_records"))
            or config["expected_records"] <= 0
        ):
            raise DataError("Invalid configuration or missing configuration file")
        collections.add(collection)
    return lock


def validate_files(source: Path, lock: dict[str, Any]) -> None:
    for entry in lock["files"]:
        path = source / entry["path"]
        if not path.is_file() or checksum(path) != entry["sha256"]:
            raise DataError(f"Missing file or checksum mismatch: {entry['path']}")


def cleanup_staging(staging: Path, parent: Path) -> None:
    """Delete only the newly created staging directory within its checked parent."""
    if staging.exists():
        if staging.resolve().parent != parent.resolve() or not staging.name.startswith("."):
            raise DataError("Refusing cleanup outside the staging parent")
        shutil.rmtree(staging)


def fetch(source: Path, lock_path: Path) -> None:
    """Download exact files once; reuse existing sources only after verification."""
    from huggingface_hub import hf_hub_download

    lock = read_lock(lock_path)
    if source.exists():
        validate_files(source, lock)
        return
    source.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".fetch-", dir=source.parent))
    try:
        for entry in lock["files"]:
            hf_hub_download(
                repo_id=lock["repository"],
                repo_type="dataset",
                revision=lock["revision"],
                filename=entry["path"],
                local_dir=staging,
            )
        validate_files(staging, lock)
        staging.rename(source)
    finally:
        cleanup_staging(staging, source.parent)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_records(source: Path, lock: dict[str, Any]) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    validate_files(source, lock)
    records: list[dict[str, Any]] = []
    keys: set[str] = set()
    urns: set[int] = set()
    required = {
        "hadith_key",
        "urn",
        "seq",
        "collection",
        "language",
        "hadith_number",
        "number_sort",
        "book_number",
        "in_book_number",
        "sunnah_url",
        "text",
        "grades",
        "n_grades",
        "grade_summary",
        "is_muallaq",
    }
    for config in sorted(lock["configs"], key=lambda c: c["collection"]):
        try:
            table = pq.read_table(source / config["path"])
        except (ValueError, OSError) as exc:
            raise DataError(f"Cannot read Parquet for {config['name']}: {exc}") from exc
        if not required.issubset(table.column_names):
            raise DataError(f"Missing required columns in {config['name']}")
        rows = table.to_pylist()
        if len(rows) != config["expected_records"]:
            raise DataError(f"Unexpected record count in {config['name']}")
        sequences: set[int] = set()
        for record in rows:
            key = record["hadith_key"]
            if not isinstance(key, str) or not key or key in keys:
                raise DataError(f"Invalid or duplicate hadith_key: {key!r}")
            if record["collection"] != config["collection"] or record["language"] != "ar":
                raise DataError(f"Collection/language mismatch: {key}")
            if not isinstance(record["hadith_number"], str) or not record["hadith_number"]:
                raise DataError(f"Invalid hadith_number: {key}")
            if key != f"{record['collection']}:{record['hadith_number']}":
                raise DataError(f"Identifier/number mismatch: {key}")
            if not _integer(record["urn"]) or record["urn"] <= 0 or record["urn"] in urns:
                raise DataError(f"Invalid or duplicate urn: {key}")
            if not _integer(record["seq"]) or record["seq"] <= 0 or record["seq"] in sequences:
                raise DataError(f"Invalid or duplicate sequence: {key}")
            for name in ("number_sort", "book_number", "in_book_number", "n_grades"):
                if not _integer(record[name]):
                    raise DataError(f"Invalid integer field {name}: {key}")
            for name in ("sunnah_url", "grade_summary"):
                if record[name] is not None and not isinstance(record[name], str):
                    raise DataError(f"Invalid nullable string {name}: {key}")
            if not isinstance(record["text"], str) or not isinstance(record["is_muallaq"], bool):
                raise DataError(f"Invalid text or flag: {key}")
            if not isinstance(record["grades"], list) or record["n_grades"] != len(
                record["grades"]
            ):
                raise DataError(f"Invalid grades: {key}")
            for grade in record["grades"]:
                if not isinstance(grade, dict) or any(
                    not isinstance(grade.get(name), str) for name in ("grader", "grade")
                ):
                    raise DataError(f"Invalid nested grade: {key}")
            try:
                canonical(record)
            except (ValueError, TypeError) as exc:
                raise DataError(f"Record is not JSON-compatible: {key}") from exc
            keys.add(key)
            urns.add(record["urn"])
            sequences.add(record["seq"])
        records.extend(sorted(rows, key=lambda r: r["seq"]))
    return records


def derive(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    token_rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    warning_counts: Counter[str] = Counter()
    collection_counts: Counter[str] = Counter()
    text_counts: Counter[str] = Counter()
    null_counts: Counter[str] = Counter()
    token_count = empty_tokens = 0
    for record in records:
        text = record["text"]
        result = tokenize(text)
        token_rows.append(
            {"hadith_key": record["hadith_key"], "tokens": [asdict(t) for t in result.tokens]}
        )
        for token in result.tokens:
            if not (0 <= token.start < token.end <= len(text)):
                raise DataError(f"Invalid token span: {record['hadith_key']}")
        for warning in result.warnings:
            warnings.append({"hadith_key": record["hadith_key"], **asdict(warning)})
            warning_counts[warning.kind] += 1
        collection_counts[record["collection"]] += 1
        text_counts[text] += 1
        for field, value in record.items():
            if value is None:
                null_counts[field] += 1
        token_count += len(result.tokens)
        empty_tokens += not result.tokens
    duplicate_groups: dict[str, list[str]] = {}
    sequence_report = {}
    for collection in sorted(collection_counts):
        sequences = {r["seq"] for r in records if r["collection"] == collection}
        sequence_report[collection] = {
            "minimum": min(sequences),
            "maximum": max(sequences),
            "gaps": sorted(set(range(1, max(sequences) + 1)) - sequences),
        }
    for record in records:
        if text_counts[record["text"]] > 1:
            digest = hashlib.sha256(record["text"].encode("utf-8")).hexdigest()
            duplicate_groups.setdefault(digest, []).append(record["hadith_key"])
    report = {
        "validation_version": 1,
        "integrity": "passed",
        "records": len(records),
        "collection_counts": dict(collection_counts),
        "source_sequences": sequence_report,
        "null_counts": dict(null_counts),
        "duplicate_text_groups": duplicate_groups,
        "duplicate_text_extra_records": sum(n - 1 for n in text_counts.values() if n > 1),
        "tokens": token_count,
        "records_without_tokens": empty_tokens,
        "warning_counts": dict(warning_counts),
        "warnings": warnings,
        "affected_hadith_keys": sorted({w["hadith_key"] for w in warnings}),
    }
    return token_rows, report


def environment() -> dict[str, Any]:
    sources = ("tools/prepare_data.py", "src/hadith_detector/_text.py")
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "unicode": unicodedata.unidata_version,
        "dependencies": {name: version(name) for name in ("huggingface-hub", "pyarrow")},
        "dependency_lock_sha256": checksum(ROOT / "uv.lock"),
        "preprocessing_sources": {
            name: hashlib.sha256(
                (ROOT / name).read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
            ).hexdigest()
            for name in sources
        },
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("wb") as stream:
        for row in rows:
            stream.write(canonical(row))


def build(source: Path, output: Path, lock_path: Path) -> dict[str, Any]:
    if sys.version_info[:2] != (3, 14):
        raise DataError(
            "Corpus builds require Python 3.14; normalization supports Python 3.11–3.14"
        )
    if output.exists():
        raise DataError("Output directory already exists; choose a new directory")
    lock = read_lock(lock_path)
    records = load_records(source, lock)
    token_rows, report = derive(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".build-", dir=output.parent))
    try:
        write_jsonl(staging / "records.jsonl", records)
        write_jsonl(staging / "tokens.jsonl", token_rows)
        (staging / "validation.json").write_bytes(canonical(report))
        inputs = {
            "source_lock": lock,
            "versions": VERSIONS,
            "environment": environment(),
            "configuration": {
                "record_order": "collection,seq",
                "encoding": "UTF-8",
                "newline": "LF",
                "barriers": "segment",
                "repair_text": False,
            },
        }
        manifest = {
            **inputs,
            "build_fingerprint": hashlib.sha256(canonical(inputs)).hexdigest(),
            "artifacts": {
                name: checksum(staging / name) for name in OUTPUTS if name != "manifest.json"
            },
        }
        (staging / "manifest.json").write_bytes(canonical(manifest))
        verify(source, staging, lock_path)
        # rename is atomic within this filesystem; refuse a concurrently created target.
        if output.exists():
            raise DataError("Output appeared during build; refusing to overwrite")
        staging.rename(output)
        return manifest
    finally:
        cleanup_staging(staging, output.parent)


def verify(source: Path, output: Path, lock_path: Path) -> dict[str, Any]:
    lock = read_lock(lock_path)
    manifest = _json(output / "manifest.json")
    if not isinstance(manifest, dict):
        raise DataError("Manifest must be an object")
    if manifest.get("versions") != VERSIONS or manifest.get("source_lock") != lock:
        raise DataError("Incompatible artifact versions or source lock")
    if set(manifest.get("artifacts", {})) != set(OUTPUTS) - {"manifest.json"}:
        raise DataError("Invalid artifact inventory")
    if not all(k in manifest for k in ("environment", "configuration", "build_fingerprint")):
        raise DataError("Incomplete build manifest")
    inputs = {k: manifest[k] for k in ("source_lock", "versions", "environment", "configuration")}
    if hashlib.sha256(canonical(inputs)).hexdigest() != manifest.get("build_fingerprint"):
        raise DataError("Invalid build fingerprint")
    for name, digest in manifest["artifacts"].items():
        if not (output / name).is_file() or checksum(output / name) != digest:
            raise DataError(f"Artifact checksum mismatch: {name}")
    records = load_records(source, lock)
    token_rows, report = derive(records)
    for name, rows in (("records.jsonl", records), ("tokens.jsonl", token_rows)):
        expected = hashlib.sha256()
        for row in rows:
            expected.update(canonical(row))
        if expected.hexdigest() != manifest["artifacts"][name]:
            raise DataError(f"Source preservation or token/span integrity failed: {name}")
    if (output / "validation.json").read_bytes() != canonical(report):
        raise DataError("Validation report does not match verified source")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "build", "verify"))
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()
    if args.command != "fetch" and args.output_dir is None:
        parser.error("build and verify require --output-dir")
    started = time.perf_counter()
    try:
        if args.command == "fetch":
            fetch(args.source_dir.resolve(), args.lock)
        elif args.command == "build":
            build(args.source_dir.resolve(), args.output_dir.resolve(), args.lock)
        else:
            verify(args.source_dir.resolve(), args.output_dir.resolve(), args.lock)
    except (DataError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{args.command}: passed ({time.perf_counter() - started:.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
