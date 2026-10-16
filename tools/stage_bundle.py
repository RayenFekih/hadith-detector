"""Validate and stage an approved corpus into package data, entirely offline."""

import argparse
import shutil
import tempfile
from pathlib import Path

from hadith_detector._resources import Resources, canonical, checksum, read_json

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/hadith_detector"


def stage(index_dir: Path, *, package: Path = PACKAGE) -> Path:
    lock = read_json(package / "_bundle.json")
    manifest = read_json(index_dir / "manifest.json")
    for key in ("artifacts", "counts", "source_dataset", "versions"):
        if manifest[key] != lock[key]:
            raise ValueError(f"Resources differ from approved bundle lock: {key}")
    output = package / "_data"
    if output.exists():
        raise FileExistsError("Bundle directory already exists; use a clean staging checkout")
    Resources.load(index_dir)
    notices = ROOT / "tools/bundle-notices"
    for name, sha in lock["notices"].items():
        if checksum(notices / name) != sha:
            raise ValueError(f"Unapproved provenance notice: {name}")
    temporary = Path(tempfile.mkdtemp(prefix=".bundle-", dir=package))
    try:
        for name in (*sorted(lock["artifacts"]), "manifest.json"):
            shutil.copyfile(index_dir / name, temporary / name)
        (temporary / "notices").mkdir()
        for name in lock["notices"]:
            shutil.copyfile(notices / name, temporary / "notices" / name)
        shutil.copyfile(notices / "PROVENANCE.md", temporary / "notices/PROVENANCE.md")
        Resources.load(temporary)
        files = {
            p.relative_to(temporary).as_posix(): checksum(p)
            for p in sorted(temporary.rglob("*"))
            if p.is_file()
        }
        (temporary / "bundle.json").write_bytes(
            canonical(
                {"version": 1, "lock_sha256": checksum(package / "_bundle.json"), "files": files}
            )
        )
        # Refuse publication if another process created the destination.
        temporary.rename(output)
    finally:
        if temporary.exists():
            if temporary.resolve().parent != package.resolve() or not temporary.name.startswith(
                ".bundle-"
            ):
                raise ValueError("Refusing cleanup outside the bundle staging directory")
            shutil.rmtree(temporary)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, required=True)
    args = parser.parse_args()
    print(stage(args.index_dir))


if __name__ == "__main__":
    main()
