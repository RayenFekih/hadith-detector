"""Prepare dependencies, then install and probe candidate wheels fully offline."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .release_wheels import acquire

ROOT = Path(__file__).resolve().parents[1]


def check(artifacts: Path, output: Path):
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("Install uv before running candidate installation checks")
    output.mkdir(parents=True, exist_ok=False)
    wheels = sorted(artifacts.rglob("*.whl"))
    if len(wheels) != 2:
        raise ValueError("Expected original and sdist-rebuilt candidate wheels")
    wheelhouse = output / "dependencies"
    acquire(wheels[0], ROOT / "uv.lock", wheelhouse)
    environment = dict(os.environ, UV_OFFLINE="1", PIP_NO_INDEX="1", HF_HUB_OFFLINE="1")
    for i, wheel in enumerate(wheels):
        venv = output / f"venv-{i}"
        subprocess.run(
            [uv, "venv", "--python", sys.executable, str(venv)], check=True, env=environment
        )
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [
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
                str(wheel),
            ],
            check=True,
            env=environment,
        )
        empty = output / f"empty-{i}"
        empty.mkdir()
        subprocess.run(
            [
                str(python.absolute()),
                "-I",
                "-B",
                str(ROOT / "tools/release_probe.py"),
                "--readme",
                str(ROOT / "README.md"),
                "--expectations",
                str(ROOT / "tools/release-cases.json"),
                "--output",
                str((output / f"probe-{i}.json").resolve()),
            ],
            cwd=empty,
            check=True,
            env=environment,
        )
        if list(empty.iterdir()):
            raise ValueError("Installed library created files in its working directory")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    check(args.artifacts_dir.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
