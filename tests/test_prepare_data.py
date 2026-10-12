"""Synthetic pipeline tests; no Hub downloads or real-corpus fixtures."""

import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest

pa = pytest.importorskip("pyarrow", reason="Install the data dependency group")
pq = pytest.importorskip("pyarrow.parquet")
if sys.version_info[:2] != (3, 14):
    pytest.skip("The pinned corpus build environment is Python 3.14", allow_module_level=True)

# Import repository tooling explicitly; do not add src or tools to sys.path.
spec = importlib.util.spec_from_file_location(
    "prepare_data", Path(__file__).resolve().parents[1] / "tools/prepare_data.py"
)
assert spec is not None and spec.loader is not None
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)
pytestmark = pytest.mark.data


def record(number: int, text: str = "عَنْ نَافِعٍ عن ابن عمر") -> dict:
    return {
        "hadith_key": f"bukhari:{number}",
        "urn": 100 + number,
        "seq": number,
        "collection": "bukhari",
        "language": "ar",
        "hadith_number": str(number),
        "number_sort": number,
        "book_number": 1,
        "in_book_number": number,
        "sunnah_url": None,
        "text": text,
        "grades": [{"grader": "test", "grade": "test"}],
        "n_grades": 1,
        "grade_summary": None,
        "is_muallaq": False,
        "extra_metadata": {"source": "fixture", "tags": ["one", "two"]},
    }


def fixture_source(tmp_path: Path, rows: list[dict]) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    parquet = source / "records.parquet"
    pq.write_table(pa.Table.from_pylist(rows), parquet)
    lock = {
        "lock_version": 1,
        "repository": "synthetic/fixture",
        "revision": "a" * 40,
        "configs": [
            {
                "name": "bukhari-ar",
                "collection": "bukhari",
                "path": "records.parquet",
                "expected_records": len(rows),
            }
        ],
        "files": [{"path": "records.parquet", "sha256": pipeline.checksum(parquet)}],
    }
    lock_path = tmp_path / "lock.json"
    lock_path.write_bytes(pipeline.canonical(lock))
    return source, lock_path


def no_network(*args: object, **kwargs: object) -> None:
    raise AssertionError("Offline operation attempted network access")


def test_reproducible_build_preserves_every_field(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rows = [record(2), record(1), record(3, ""), record(4, "عن�نافع")]
    source, lock = fixture_source(tmp_path, rows)
    monkeypatch.setattr(socket, "socket", no_network)
    first, second = tmp_path / "first", tmp_path / "second"
    pipeline.build(source, first, lock)
    pipeline.build(source, second, lock)
    for name in pipeline.OUTPUTS:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    restored = [
        json.loads(line)
        for line in (first / "records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert restored == sorted(rows, key=lambda r: r["seq"])
    report = json.loads((first / "validation.json").read_text(encoding="utf-8"))
    assert report["duplicate_text_extra_records"] == 1
    assert report["records_without_tokens"] == 1
    assert report["warning_counts"] == {"empty_text": 1, "replacement_character": 1}
    pipeline.verify(source, first, lock)
    with pytest.raises(pipeline.DataError, match="already exists"):
        pipeline.build(source, first, lock)


@pytest.mark.parametrize(
    "mutation", ["key", "urn", "sequence", "schema", "language", "number", "grades"]
)
def test_rejects_invalid_sources(tmp_path: Path, mutation: str):
    rows = [record(1), record(2)]
    if mutation == "schema":
        for row in rows:
            del row["text"]
    elif mutation == "key":
        rows[1]["hadith_key"] = rows[0]["hadith_key"]
    elif mutation == "urn":
        rows[1]["urn"] = rows[0]["urn"]
    elif mutation == "sequence":
        rows[1]["seq"] = 0
    elif mutation == "language":
        rows[1]["language"] = "en"
    elif mutation == "number":
        for row in rows:
            row["hadith_number"] = 1
    else:
        rows[1]["n_grades"] = 0
    source, lock = fixture_source(tmp_path, rows)
    output = tmp_path / "output"
    with pytest.raises(pipeline.DataError):
        pipeline.build(source, output, lock)
    assert not output.exists()
    assert not list(tmp_path.glob(".build-*"))


def test_missing_and_corrupted_sources(tmp_path: Path):
    source, lock = fixture_source(tmp_path, [record(1)])
    (source / "records.parquet").write_bytes(b"corrupt")
    with pytest.raises(pipeline.DataError, match="checksum"):
        pipeline.build(source, tmp_path / "output", lock)
    (source / "records.parquet").unlink()
    with pytest.raises(pipeline.DataError, match="Missing"):
        pipeline.build(source, tmp_path / "output", lock)


def test_tampering_detected_even_with_updated_checksum(tmp_path: Path):
    source, lock = fixture_source(tmp_path, [record(1)])
    output = tmp_path / "output"
    pipeline.build(source, output, lock)
    path = output / "tokens.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows[0]["tokens"][0]["start"] += 1
    pipeline.write_jsonl(path, rows)
    with pytest.raises(pipeline.DataError, match="checksum"):
        pipeline.verify(source, output, lock)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["artifacts"]["tokens.jsonl"] = pipeline.checksum(path)
    (output / "manifest.json").write_bytes(pipeline.canonical(manifest))
    with pytest.raises(pipeline.DataError, match="integrity"):
        pipeline.verify(source, output, lock)


def test_failed_staging_is_cleaned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source, lock = fixture_source(tmp_path, [record(1)])

    def fail(*args, **kwargs):
        raise pipeline.DataError("simulated validation failure")

    monkeypatch.setattr(pipeline, "verify", fail)
    with pytest.raises(pipeline.DataError, match="simulated"):
        pipeline.build(source, tmp_path / "output", lock)
    assert not (tmp_path / "output").exists()
    assert not list(tmp_path.glob(".build-*"))


def test_non_json_values_are_rejected():
    with pytest.raises(ValueError):
        pipeline.canonical({"extra": float("nan")})


def test_source_sequence_gaps_are_preserved(tmp_path: Path):
    row = record(1)
    row["seq"] = 3
    source, lock = fixture_source(tmp_path, [row])
    output = tmp_path / "output"
    pipeline.build(source, output, lock)
    restored = json.loads((output / "records.jsonl").read_text(encoding="utf-8"))
    assert restored["seq"] == 3
    report = json.loads((output / "validation.json").read_text(encoding="utf-8"))
    assert report["source_sequences"]["bukhari"]["gaps"] == [1, 2]


def test_expected_record_count_is_checked(tmp_path: Path):
    source, lock = fixture_source(tmp_path, [record(1)])
    contents = json.loads(lock.read_text(encoding="utf-8"))
    contents["configs"][0]["expected_records"] = 2
    lock.write_bytes(pipeline.canonical(contents))
    with pytest.raises(pipeline.DataError, match="record count"):
        pipeline.build(source, tmp_path / "output", lock)


def test_fetch_uses_pinned_files_and_reuses_verified_source(tmp_path: Path, monkeypatch):
    import huggingface_hub

    source, lock = fixture_source(tmp_path, [record(1)])
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        destination = Path(kwargs["local_dir"]) / kwargs["filename"]
        destination.write_bytes((source / kwargs["filename"]).read_bytes())
        return str(destination)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    target = tmp_path / "download"
    pipeline.fetch(target, lock)
    pipeline.fetch(target, lock)
    assert len(calls) == 1
    assert calls[0]["revision"] == "a" * 40
    assert calls[0]["repo_type"] == "dataset"
    assert not list(tmp_path.glob(".fetch-*"))


def test_corrupted_fetch_leaves_no_accepted_source(tmp_path: Path, monkeypatch):
    import huggingface_hub

    _, lock = fixture_source(tmp_path, [record(1)])

    def download(**kwargs):
        (Path(kwargs["local_dir"]) / kwargs["filename"]).write_bytes(b"corrupt")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", download)
    with pytest.raises(pipeline.DataError, match="checksum"):
        pipeline.fetch(tmp_path / "download", lock)
    assert not (tmp_path / "download").exists()
    assert not list(tmp_path.glob(".fetch-*"))
