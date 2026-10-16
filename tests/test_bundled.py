"""Default resources preserve explicit-directory behavior and fail closed."""

import ast
import json
import shutil
from pathlib import Path

import pytest

from hadith_detector import HadithDetector, _bundled, clear_cache, detect, get_hadith
from hadith_detector._resources import canonical, checksum
from tools.stage_bundle import stage

from .test_detector import build_fixture

ROOT = Path(__file__).resolve().parents[1]


def synthetic_package(tmp_path):
    index, _ = build_fixture(tmp_path, ["عن نافع عن ابن عمر", "عن نافغ عن ابن عمر"])
    package = tmp_path / "src/hadith_detector"
    package.mkdir(parents=True)
    manifest = json.loads((index / "manifest.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "src/hadith_detector/_bundle.json").read_text(encoding="utf-8"))
    lock.update({k: manifest[k] for k in ("artifacts", "counts", "source_dataset", "versions")})
    (package / "_bundle.json").write_bytes(canonical(lock))
    return package, index


def test_defaults_cache_and_explicit_equivalence(tmp_path, monkeypatch):
    package, index = synthetic_package(tmp_path)
    stage(index, package=package)
    monkeypatch.setattr(_bundled, "__file__", str(package / "_bundled.py"))
    clear_cache()
    try:
        implicit = HadithDetector()
        explicit = HadithDetector.from_directory(index)
        text = "عن نافع عن ابن عمر"
        assert implicit.index_dir == package / "_data"
        assert implicit.detect(text, max_errors=1) == explicit.detect(text, max_errors=1)
        assert detect(text, max_errors=1) == implicit.detect(text, max_errors=1)
        assert get_hadith("fixture:1") == implicit.get_hadith("fixture:1")
        from hadith_detector import _convenience, annotate

        cached = _convenience._entry[1]
        assert annotate(text) == implicit.annotate(text)
        assert _convenience._entry[1] is cached
        assert detect(text, index_dir=implicit.index_dir) == implicit.detect(text)
        assert _convenience._entry[1] is cached
        with pytest.raises(FileNotFoundError):
            detect(text, index_dir=tmp_path / "missing")
        with pytest.raises(TypeError):
            HadithDetector.from_directory()
    finally:
        clear_cache()


def test_missing_corrupt_and_refused_overwrite(tmp_path, monkeypatch):
    package, index = synthetic_package(tmp_path)
    monkeypatch.setattr(_bundled, "__file__", str(package / "_bundled.py"))
    with pytest.raises(FileNotFoundError, match="Reinstall"):
        HadithDetector()
    output = stage(index, package=package)
    before = {p.name: checksum(p) for p in output.iterdir() if p.is_file()}
    with pytest.raises(FileExistsError):
        stage(index, package=package)
    assert before == {p.name: checksum(p) for p in output.iterdir() if p.is_file()}
    with (output / "records.jsonl").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="reinstall"):
        HadithDetector()


def test_lock_rejects_different_corpus_and_bad_notice(tmp_path, monkeypatch):
    package, index = synthetic_package(tmp_path)
    lock = json.loads((package / "_bundle.json").read_text())
    lock["counts"]["records"] += 1
    (package / "_bundle.json").write_bytes(canonical(lock))
    with pytest.raises(ValueError, match="lock"):
        stage(index, package=package)
    assert not (package / "_data").exists()
    lock["counts"]["records"] -= 1
    lock["notices"]["LICENSES.md"] = "0" * 64
    (package / "_bundle.json").write_bytes(canonical(lock))
    with pytest.raises(ValueError, match="notice"):
        stage(index, package=package)
    assert not (package / "_data").exists()


def test_failed_copy_never_publishes_partial_bundle(tmp_path, monkeypatch):
    package, index = synthetic_package(tmp_path)

    def fail(*args):
        raise OSError("simulated copy failure")

    monkeypatch.setattr(shutil, "copyfile", fail)
    with pytest.raises(OSError, match="simulated"):
        stage(index, package=package)
    assert not (package / "_data").exists()
    assert not list(package.glob(".bundle-*"))


def test_staging_is_byte_identical_and_build_guard(tmp_path, monkeypatch):
    package, index = synthetic_package(tmp_path)
    first = stage(index, package=package)
    other = tmp_path / "other/src/hadith_detector"
    other.mkdir(parents=True)
    shutil.copyfile(package / "_bundle.json", other / "_bundle.json")
    second = stage(index, package=other)
    assert {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()} == {
        p.relative_to(second): p.read_bytes() for p in second.rglob("*") if p.is_file()
    }
    import hashlib

    tree = ast.parse((ROOT / "setup.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef))
    namespace = {"ROOT": package.parents[1], "hashlib": hashlib, "json": json}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "setup.py", "exec"), namespace)
    guard = namespace["verify_bundle"]
    guard()
    (first / "unexpected.txt").write_text("not an approved artifact")
    with pytest.raises(RuntimeError, match="Unexpected"):
        guard()
    (first / "manifest.json").unlink()
    with pytest.raises(RuntimeError, match="Stage approved"):
        guard()
