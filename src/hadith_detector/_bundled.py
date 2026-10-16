"""Resolve preinstalled resources without extraction, downloads or construction."""

from pathlib import Path


def directory(index_dir: str | Path | None) -> Path:
    if index_dir is not None:
        return Path(index_dir).resolve()
    bundled = Path(__file__).resolve().parent / "_data"
    if not (bundled / "manifest.json").is_file():
        raise FileNotFoundError(
            "Bundled Hadith resources are missing. Reinstall the complete hadith-detector "
            "distribution, or pass index_dir explicitly. Development checkouts must run "
            "python -m tools.stage_bundle before using bundled resources."
        )
    return bundled
