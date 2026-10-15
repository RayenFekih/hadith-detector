"""Build artifacts and install them independently of the development checkout."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

import pytest
from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

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


@pytest.fixture(scope="module")
def wheelhouse(
    artifacts: tuple[Path, Path, Path], tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Acquire hash-locked runtime wheels before the isolated offline installation.

    A frozen uv sync can install wheels without populating the registry metadata
    needed by a subsequent offline pip resolver. Do not depend on that cache.
    """
    destination = tmp_path_factory.mktemp("wheelhouse")
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    tags = {tag: rank for rank, tag in enumerate(sys_tags())}
    with zipfile.ZipFile(artifacts[0]) as archive:
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in archive.namelist() if n.endswith("/METADATA")))
        )
    for value in metadata.get_all("Requires-Dist", []):
        requirement = Requirement(value)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        candidates = []
        for package in lock["package"]:
            if canonicalize_name(package["name"]) != canonicalize_name(requirement.name):
                continue
            if package["version"] not in requirement.specifier:
                continue
            for wheel in package.get("wheels", []):
                filename = unquote(urlsplit(wheel["url"]).path.rsplit("/", 1)[1])
                wheel_tags = parse_wheel_filename(filename)[3]
                compatible = tags.keys() & wheel_tags
                if compatible:
                    candidates.append((min(tags[tag] for tag in compatible), filename, wheel))
        assert candidates, f"No locked compatible wheel for {requirement}"
        _, filename, wheel = min(candidates, key=lambda item: (item[0], item[1]))
        with urlopen(wheel["url"], timeout=60) as response:
            content = response.read()
        assert f"sha256:{hashlib.sha256(content).hexdigest()}" == wheel["hash"]
        (destination / filename).write_bytes(content)
    return destination


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
        for module in (
            "detector",
            "models",
            "config",
            "_convenience",
            "_serialization",
            "_annotation",
            "_resources",
            "_fuzzy",
            "_marisa",
        ):
            assert f"hadith_detector/{module}.py" in names
        assert metadata["Name"] == "hadith-detector"
        assert metadata["Requires-Python"] == ">=3.11"
        assert metadata["License-Expression"] == "MIT"
        assert set(metadata.get_all("Requires-Dist", [])) == {
            "rapidfuzz<4,>=3.14.6",
            "marisa-trie==1.4.1",
        }
        assert metadata.get_all("Provides-Extra", []) == []
        assert metadata["Version"]
        assert any(n.endswith("/licenses/LICENSE") for n in names)
        assert all(n.startswith(("hadith_detector/", "hadith_detector-")) for n in names)
        assert not any(n.endswith((".jsonl", ".parquet", ".bin", ".marisa")) for n in names)
        assert not any("fuzzy_benchmark" in n for n in names)
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
        assert "tools/fuzzy_benchmark/__main__.py" in relative
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
    artifacts: tuple[Path, Path, Path], wheelhouse: Path, tmp_path: Path, artifact_index: int
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
        "--offline",
        "--no-index",
        "--no-cache",
        "--find-links",
        str(wheelhouse),
        "--python",
        str(python),
        str(artifacts[artifact_index]),
        cwd=tmp_path,
    )
    working = tmp_path / "empty"
    working.mkdir()
    from .test_detector import build_fixture

    index, _ = build_fixture(tmp_path, ["عن نافع عن ابن عمر", "عن نافغ عن ابن عمر"])
    script = """
import json
import socket
def forbid_network(*args, **kwargs):
    raise AssertionError('Import attempted network access')
socket.socket = forbid_network
import hadith_detector
from importlib.util import find_spec
from importlib.metadata import version
from importlib.resources import files
assert hadith_detector.__version__ == version('hadith-detector')
assert files('hadith_detector').joinpath('py.typed').is_file()
assert callable(hadith_detector.HadithDetector.from_directory)
assert callable(hadith_detector.detect)
assert find_spec('rapidfuzz') is not None
assert find_spec('marisa_trie') is not None
assert 'rapidfuzz' not in __import__('sys').modules
from rapidfuzz.distance import Levenshtein
assert Levenshtein.distance('سلام', 'سلا', score_cutoff=1) == 1
detector = hadith_detector.HadithDetector.from_directory(__import__('sys').argv[1])
result = detector.detect('عن نافع عن ابن عمر', max_errors=1)
assert len(result) == 1 and len(result[0].references) == 2
assert [ref.occurrences[0].errors for ref in result[0].references] == [0, 1]
assert len(result[0].references[0].occurrences[0].alignment) == 5
assert detector.index_dir == __import__('pathlib').Path(__import__('sys').argv[1]).resolve()
assert hadith_detector.Detection.from_dict(json.loads(json.dumps(result[0].to_dict()))) == result[0]
assert hadith_detector.detect(result[0].text, index_dir=detector.index_dir,
                             config=hadith_detector.DetectorConfig(max_errors=1)) == result
assert hadith_detector.get_hadith('fixture:1', index_dir=detector.index_dir).sunnah_url is None
from html.parser import HTMLParser
class Text(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(html)
        self.close()
    def handle_data(self, value):
        self.parts.append(value)
text = '<script>alert(1)</script> &amp; ' + result[0].text
html = detector.annotate(text, max_errors=1)
assert ''.join(Text(html).parts) == text
assert '<script' not in html and 'class="hadith-match"' in html
assert hadith_detector.annotate(text, index_dir=detector.index_dir, max_errors=1) == html
hadith_detector.clear_cache()
print(json.dumps({'file': hadith_detector.__file__}))
"""
    result = subprocess.run(
        [str(python), "-I", "-B", "-c", script, str(index)],
        cwd=working,
        check=True,
        capture_output=True,
        text=True,
    )
    assert Path(json.loads(result.stdout)["file"]).is_relative_to(environment)
    assert list(working.iterdir()) == []
