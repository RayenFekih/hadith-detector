"""Inspect full release artifacts and rebuild the sdist wheel without Git/network."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inspect(wheel, lock):
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in names if n.endswith("/METADATA")))
        )
        prefix = "hadith_detector/_data/"
        manifest = json.loads(archive.read(prefix + "manifest.json"))
        receipt = json.loads(archive.read(prefix + "bundle.json"))
        assert manifest["artifacts"] == lock["artifacts"]
        assert manifest["counts"] == lock["counts"]
        for name, sha in receipt["files"].items():
            assert hashlib.sha256(archive.read(prefix + name)).hexdigest() == sha, name
        for name, sha in lock["artifacts"].items():
            assert receipt["files"][name] == sha, name
        for name, sha in lock["notices"].items():
            assert receipt["files"]["notices/" + name] == sha, name
        assert metadata["Requires-Python"] == ">=3.11"
        assert set(metadata.get_all("Requires-Dist")) == {
            "rapidfuzz<4,>=3.14.6",
            "marisa-trie==1.4.1",
            'mcp<2,>=1.30; extra == "mcp"',
        }
        assert metadata["License-Expression"] == "MIT"
        assert metadata.get_all("Provides-Extra") == ["mcp"]
        assert not any(n.endswith((".parquet", ".ipynb")) for n in names)
        return {
            "version": metadata["Version"],
            "installed_bytes": sum(i.file_size for i in archive.infolist()),
        }


def validate(dist, rebuild):
    lock = json.loads((ROOT / "src/hadith_detector/_bundle.json").read_text(encoding="utf-8"))
    wheel = next(dist.glob("*.whl"))
    sdist = next(dist.glob("*.tar.gz"))
    assert all(p.stat().st_size < 100_000_000 for p in (wheel, sdist))
    original = inspect(wheel, lock)
    rebuild.mkdir(parents=True, exist_ok=False)
    source = rebuild / "source"
    source.mkdir()
    with tarfile.open(sdist) as archive:
        archive.extractall(source, filter="data")
    tree = next(source.iterdir())
    assert not (tree / ".git").exists()
    assert not any((tree / "data").glob("**/*.jsonl"))
    environment = dict(os.environ, UV_OFFLINE="1", PIP_NO_INDEX="1", HF_HUB_OFFLINE="1")
    environment.pop("SETUPTOOLS_SCM_PRETEND_VERSION_FOR_HADITH_DETECTOR", None)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(rebuild.resolve()),
        ],
        cwd=tree,
        env=environment,
        check=True,
    )
    rebuilt = next(rebuild.glob("*.whl"))
    assert inspect(rebuilt, lock) == original
    with zipfile.ZipFile(wheel) as a, zipfile.ZipFile(rebuilt) as b:
        for name in a.namelist():
            if name.startswith("hadith_detector/"):
                assert a.read(name) == b.read(name), name
    report = {
        "version": original["version"],
        "installed_distribution_bytes": original["installed_bytes"],
        "artifacts": {
            p.name: {
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in (wheel, sdist)
        },
        "rebuilt_wheel_sha256": hashlib.sha256(rebuilt.read_bytes()).hexdigest(),
        "sdist_rebuild_offline": True,
        "runtime_payloads_identical": True,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--rebuild-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=Path("data/release-artifacts.json"))
    args = parser.parse_args()
    report = validate(args.dist_dir, args.rebuild_dir)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
