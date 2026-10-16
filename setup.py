"""Fail closed on incomplete production distributions; editable checkouts stay usable."""

import hashlib
import json
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

ROOT = Path(__file__).resolve().parent


def verify_bundle():
    package = ROOT / "src/hadith_detector"
    try:
        lock = json.loads((package / "_bundle.json").read_text(encoding="utf-8"))
        resources = package / "_data"
        manifest = json.loads((resources / "manifest.json").read_text(encoding="utf-8"))
        receipt = json.loads((resources / "bundle.json").read_text(encoding="utf-8"))
        for key in ("artifacts", "counts", "source_dataset", "versions"):
            if manifest[key] != lock[key]:
                raise ValueError(f"Bundle lock mismatch: {key}")
        if (
            receipt["lock_sha256"]
            != hashlib.sha256((package / "_bundle.json").read_bytes()).hexdigest()
        ):
            raise ValueError("Bundle receipt does not match the approved lock")
        expected = {*lock["artifacts"], "manifest.json", "notices/PROVENANCE.md"}
        expected.update("notices/" + n for n in lock["notices"])
        if set(receipt["files"]) != expected:
            raise ValueError("Incomplete bundle receipt")
        actual = {p.relative_to(resources).as_posix() for p in resources.rglob("*") if p.is_file()}
        if actual != expected | {"bundle.json"}:
            raise ValueError("Unexpected or missing package-data files")
        for name, sha in receipt["files"].items():
            if hashlib.sha256((resources / name).read_bytes()).hexdigest() != sha:
                raise ValueError(f"Corrupt bundled file: {name}")
        for name, sha in lock["artifacts"].items():
            if receipt["files"][name] != sha:
                raise ValueError(f"Unapproved bundled resource: {name}")
        for name, sha in lock["notices"].items():
            if receipt["files"]["notices/" + name] != sha:
                raise ValueError(f"Unapproved provenance notice: {name}")
    except (OSError, KeyError, ValueError) as exc:
        raise RuntimeError(
            "Cannot build a complete hadith-detector distribution: "
            f"{exc}. Stage approved resources with python -m tools.stage_bundle. "
            "See docs/release-readiness.md."
        ) from exc


class VerifiedBuild(build_py):
    def run(self):
        if not self.editable_mode:
            verify_bundle()
        super().run()


class VerifiedSdist(sdist):
    def run(self):
        verify_bundle()
        super().run()


setup(cmdclass={"build_py": VerifiedBuild, "sdist": VerifiedSdist})
