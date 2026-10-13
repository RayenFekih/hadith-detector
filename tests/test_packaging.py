"""Build artifacts and install them independently of the development checkout."""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.packaging


def run(*args: str, cwd: Path) -> None:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, f"{args!r}\n{result.stdout}\n{result.stderr}"


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path]:
    uv = shutil.which("uv")
    assert uv is not None, "Install uv to run the documented packaging checks"
    workspace = tmp_path_factory.mktemp("packaging")
    output = workspace / "dist"
    run(uv, "build", "--no-sources", "--out-dir", str(output), cwd=ROOT)
    wheel = next(output.glob("*.whl"))
    sdist = next(output.glob("*.tar.gz"))
    unpacked = workspace / "source"
    unpacked.mkdir()
    with tarfile.open(sdist) as archive:
        archive.extractall(unpacked, filter="data")
    source = next(unpacked.iterdir())
    assert not (source / ".git").exists()
    rebuilt = workspace / "rebuilt"
    run(uv, "build", "--wheel", "--no-sources", "--out-dir", str(rebuilt), cwd=source)
    return wheel, sdist, next(rebuilt.glob("*.whl"))


def test_artifact_contents_and_metadata(artifacts: tuple[Path, Path, Path]) -> None:
    wheel, sdist, rebuilt = artifacts
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in names if n.endswith("/METADATA")))
        )
        assert "hadith_detector/__init__.py" in names
        assert "hadith_detector/py.typed" in names
        assert "hadith_detector/_text.py" in names
        for module in ("detector", "models", "_resources"):
            assert f"hadith_detector/{module}.py" in names
        assert metadata["Name"] == "hadith-detector"
        assert metadata["Requires-Python"] == ">=3.11"
        assert metadata["License-Expression"] == "MIT"
        assert metadata.get_all("Requires-Dist", []) == []
        assert metadata["Version"]
        assert any(n.endswith("/licenses/LICENSE") for n in names)
        assert all(n.startswith(("hadith_detector/", "hadith_detector-")) for n in names)
        assert not any(n.endswith((".jsonl", ".parquet", ".bin")) for n in names)
    with zipfile.ZipFile(rebuilt) as archive:
        rebuilt_metadata = BytesParser().parsebytes(
            archive.read(next(n for n in archive.namelist() if n.endswith("/METADATA")))
        )
        assert rebuilt_metadata["Version"] == metadata["Version"]
    with tarfile.open(sdist) as archive:
        relative = [Path(*Path(n).parts[1:]).as_posix() for n in archive.getnames()]
        assert "src/hadith_detector/py.typed" in relative
        assert "docs/roadmap.md" in relative
        assert "data/README.md" in relative
        assert "tools/prepare_data.py" in relative
        assert "tools/build_index.py" in relative
        assert "tools/source-lock.json" in relative
        assert "uv.lock" in relative
        forbidden = {
            ".git",
            ".venv",
            ".cache",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
            "notebooks",
            "others",
            "logs",
            "__pycache__",
        }
        assert all(not forbidden.intersection(Path(n).parts) for n in relative)
        assert all(n in {"data", "data/README.md"} for n in relative if n.startswith("data"))
        assert not any(n.endswith((".csv", ".ipynb", ".pyc", ".zip")) for n in relative)
        assert not {"src/config.py", "src/logger.py", "main.py"}.intersection(relative)


@pytest.mark.parametrize("artifact_index", [0, 2], ids=["checkout-wheel", "sdist-wheel"])
def test_clean_wheel_install(
    artifacts: tuple[Path, Path, Path], tmp_path: Path, artifact_index: int
) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    environment = tmp_path / "venv"
    run(uv, "venv", "--python", sys.executable, str(environment), cwd=tmp_path)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run(
        uv,
        "pip",
        "install",
        "--python",
        str(python),
        "--no-deps",
        str(artifacts[artifact_index]),
        cwd=tmp_path,
    )
    working = tmp_path / "empty"
    working.mkdir()
    script = """
import json
import socket
def forbid_network(*args, **kwargs):
    raise AssertionError('Import attempted network access')
socket.socket = forbid_network
import hadith_detector
from importlib.metadata import version
from importlib.resources import files
assert hadith_detector.__version__ == version('hadith-detector')
assert files('hadith_detector').joinpath('py.typed').is_file()
assert callable(hadith_detector.HadithDetector.from_directory)
assert not hasattr(hadith_detector, 'detect')
print(json.dumps({'file': hadith_detector.__file__}))
"""
    result = subprocess.run(
        [str(python), "-I", "-B", "-c", script],
        cwd=working,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(json.loads(result.stdout)["file"]).is_relative_to(environment)
    assert list(working.iterdir()) == []
