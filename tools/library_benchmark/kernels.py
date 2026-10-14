"""Raw JSON kernels on checksum-verified valid corpus, separate from policy adapters."""

import argparse
import gc
import json
import socket
import time
from pathlib import Path

from hadith_detector._resources import canonical, checksum


def run(name, index, output):
    import psutil

    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    manifest = json.loads((index / "manifest.json").read_text(encoding="utf-8"))
    source = index / "records.jsonl"
    assert checksum(source) == manifest["artifacts"]["records.jsonl"]
    raw = source.read_bytes()
    lines = raw.splitlines()
    library = __import__(name) if name != "baseline" else json
    loads = (
        json.loads
        if name == "baseline"
        else library.loads
        if name == "orjson"
        else library.json.decode
    )

    def encode(record):
        if name == "baseline":
            return canonical(record)
        if name == "orjson":
            return library.dumps(record, option=library.OPT_SORT_KEYS) + b"\n"
        return library.json.encode(record, order="sorted") + b"\n"

    samples = []
    for _ in range(3):
        started = time.perf_counter()
        records = [loads(line) for line in lines]
        decode = time.perf_counter() - started
        started = time.perf_counter()
        encoded = b"".join(encode(record) for record in records)
        samples.append({"decode": decode, "encode": time.perf_counter() - started})
        assert encoded == raw
        del records, encoded
        gc.collect()
    info = psutil.Process().memory_info()
    output.write_bytes(
        canonical(
            {
                "codec": name,
                "samples": samples,
                "bytes": len(raw),
                "final_rss": info.rss,
                "peak_rss": getattr(info, "peak_wset", None),
                "source_sha256": checksum(source),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codec", choices=("baseline", "msgspec", "orjson"), required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.codec, args.index_dir, args.output)
