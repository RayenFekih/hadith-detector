"""Download hash-locked dependency wheels before isolated offline installation."""

import argparse
import hashlib
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen

from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename


def acquire(wheel: Path, lock: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    packages = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    tags = {tag: rank for rank, tag in enumerate(sys_tags())}
    with zipfile.ZipFile(wheel) as archive:
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in archive.namelist() if n.endswith("/METADATA")))
        )
    for text in metadata.get_all("Requires-Dist", []):
        requirement = Requirement(text)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        candidates = []
        for package in packages:
            if canonicalize_name(package["name"]) != canonicalize_name(requirement.name):
                continue
            if package["version"] not in requirement.specifier:
                continue
            for item in package.get("wheels", []):
                filename = unquote(urlsplit(item["url"]).path.rsplit("/", 1)[1])
                compatible = tags.keys() & parse_wheel_filename(filename)[3]
                if compatible:
                    candidates.append((min(tags[t] for t in compatible), filename, item))
        if not candidates:
            raise ValueError(f"No locked wheel for {requirement} on this interpreter/platform")
        _, filename, item = min(candidates, key=lambda row: (row[0], row[1]))
        destination = output / filename
        if not destination.exists():
            with urlopen(item["url"], timeout=60) as response:
                content = response.read()
            if "sha256:" + hashlib.sha256(content).hexdigest() != item["hash"]:
                raise ValueError(f"Dependency wheel checksum failure: {filename}")
            destination.write_bytes(content)
        if "sha256:" + hashlib.sha256(destination.read_bytes()).hexdigest() != item["hash"]:
            raise ValueError(f"Existing wheel checksum failure: {filename}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--lock", type=Path, default=Path("uv.lock"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    acquire(args.wheel, args.lock, args.output)


if __name__ == "__main__":
    main()
