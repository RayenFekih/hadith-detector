"""Standalone offline installed-wheel probe, runnable outside the checkout with -I."""

import argparse
import hashlib
import json
import platform
import socket
from html.parser import HTMLParser
from importlib.metadata import requires, version
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--legacy-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    before = set(Path.cwd().iterdir())
    socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network access"))
    import hadith_detector
    from hadith_detector import Detection, DetectorConfig, HadithDetector, _marisa
    from hadith_detector._resources import INDEX_VERSION

    assert INDEX_VERSION == 2
    assert version("marisa-trie") == "1.4.1"
    assert set(requires("hadith-detector")) == {"marisa-trie==1.4.1", "rapidfuzz<4,>=3.14.6"}
    assert "site-packages" in Path(hadith_detector.__file__).parts
    factory = _marisa.marisa_trie.RecordTrie
    calls = []

    def reader(fmt, *values, **options):
        assert fmt == "<I" and not values and not options
        calls.append(fmt)
        return factory(fmt)

    _marisa.marisa_trie.RecordTrie = reader
    detector = HadithDetector.from_directory(args.index_dir)
    assert calls == ["<I", "<I"]
    assert detector.index_dir == args.index_dir.resolve()
    assert detector.config == DetectorConfig()
    for source in detector._resources.records[:3]:
        record = detector.get_hadith(source["hadith_key"])
        assert record.to_dict() == source
        for errors, missing in ((0, 0), (1, 1)):
            results = detector.detect(source["text"], max_errors=errors, max_missing_words=missing)
            assert any(
                ref.record.hadith_key == record.hadith_key
                for result in results
                for ref in result.references
            )
            html = detector.annotate(source["text"], max_errors=errors, max_missing_words=missing)

            class Text(HTMLParser):
                def __init__(self):
                    super().__init__(convert_charrefs=True)
                    self.parts = []

                def handle_data(self, value):
                    self.parts.append(value)

            decoded = Text()
            decoded.feed(html)
            decoded.close()
            assert "".join(decoded.parts) == source["text"]
            assert 'class="hadith-match"' in html
            for result in results:
                assert Detection.from_dict(json.loads(json.dumps(result.to_dict()))) == result
                assert source["text"][result.start : result.end] == result.text
                for ref in result.references:
                    for occurrence in ref.occurrences:
                        assert ref.record.text[occurrence.start : occurrence.end] == occurrence.text
    assert len(calls) == 2
    source = detector._resources.records[0]
    assert (
        hadith_detector.get_hadith(source["hadith_key"], index_dir=args.index_dir).to_dict()
        == source
    )
    cached = hadith_detector.detect(
        source["text"],
        index_dir=args.index_dir,
        config=DetectorConfig(max_errors=1, max_missing_words=1),
        max_errors=0,
        max_missing_words=0,
    )
    assert cached == detector.detect(source["text"])
    assert hadith_detector.annotate(source["text"], index_dir=args.index_dir) == detector.annotate(
        source["text"]
    )
    assert len(calls) == 4
    hadith_detector.clear_cache()
    try:
        HadithDetector.from_directory(args.legacy_dir)
    except ValueError as exc:
        assert "rebuild offline" in str(exc)
    else:
        raise AssertionError("v1 resources were accepted")
    assert set(Path.cwd().iterdir()) == before
    report = {
        "python": platform.python_version(),
        "os": platform.platform(),
        "version": hadith_detector.__version__,
        "index_version": INDEX_VERSION,
        "offline": True,
        "annotation": True,
        "prebuilt_only": True,
        "v1_rejected": True,
        "package": hadith_detector.__file__,
        "dependencies": requires("hadith-detector"),
        "manifest_sha256": hashlib.sha256(
            (args.index_dir / "manifest.json").read_bytes()
        ).hexdigest(),
    }
    args.report.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
