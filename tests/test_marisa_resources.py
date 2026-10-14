"""Production native-resource integrity and independent matching checks."""

import json

import pytest

marisa = pytest.importorskip("marisa_trie")

from hadith_detector._resources import (  # noqa: E402
    Resources,  # noqa: E402
    canonical,
    checksum,
)
from tools import build_index as build  # noqa: E402

from .test_detector import build_fixture, prepared  # noqa: E402


def fixture(tmp_path, monkeypatch, texts=None):
    source, _ = prepared(
        tmp_path / "prepared-v2", texts or ["عن نافع عن ابن عمر", "عن نافغ عن ابن عمر"]
    )
    with monkeypatch.context() as patch:
        patch.setattr(build.sys, "version_info", (3, 14))
        build.build(source, tmp_path / "v2")
    return tmp_path / "v2"


def reseal(root):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name in manifest["artifacts"]:
        manifest["artifacts"][name] = checksum(root / name)
    (root / "manifest.json").write_bytes(canonical(manifest))


def test_native_ids_and_payloads(tmp_path, monkeypatch):
    from tools.exact_benchmark.corpus import Corpus

    texts = ["?? ???? ?? ??? ???", "?? ???? ?? ??? ???", "?? ???? ?? ??? ???"]
    root = fixture(tmp_path, monkeypatch, texts)
    native = Resources.load(root)
    corpus = Corpus.synthetic(texts)
    assert dict(native.vocabulary.items()) == corpus.vocabulary
    grams = sorted(
        {
            tuple(source.terms[i : i + 3])
            for source in corpus.sequences
            for i in range(len(source) - 2)
            if source.window(i, 3)
        }
    )
    for block, key in enumerate(grams):
        assert native.trigrams.get(key) == block
    assert not (root / "vocabulary.json").exists()
    assert not (root / "trigram-keys.bin").exists()


@pytest.mark.parametrize("kind", ["word_id", "word_key", "gram_id", "gram_key", "gram_encoding"])
def test_native_corruption_with_valid_checksums(tmp_path, monkeypatch, kind):
    root = fixture(tmp_path, monkeypatch)
    name = "vocabulary.marisa" if kind.startswith("word") else "trigrams.marisa"
    path = root / name
    trie = marisa.RecordTrie("<I").load(str(path))
    pairs = list(trie.iteritems())
    if kind.endswith("id"):
        pairs[0] = (pairs[0][0], (len(pairs) + 1,))
    elif kind.endswith("key"):
        pairs[0] = (pairs[1][0], pairs[0][1])
    else:
        pairs[0] = ("z" * 24, pairs[0][1])
    marisa.RecordTrie("<I", pairs).save(str(path))
    reseal(root)
    with pytest.raises(ValueError):
        Resources.load(root)


def test_checksum_before_native_load(tmp_path, monkeypatch):
    root = fixture(tmp_path, monkeypatch)
    (root / "vocabulary.marisa").write_bytes(b"broken")
    with pytest.raises(ValueError, match="checksum"):
        Resources.load(root)


def test_truncated_native_file_with_valid_checksum(tmp_path, monkeypatch):
    root = fixture(tmp_path, monkeypatch)
    path = root / "trigrams.marisa"
    path.write_bytes(path.read_bytes()[:32])
    reseal(root)
    with pytest.raises(ValueError, match="native MARISA"):
        Resources.load(root)


def test_v1_rebuild_instruction(tmp_path):
    root, _ = build_fixture(tmp_path, ["عن نافع عن ابن عمر"])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["versions"]["index"] = 1
    (root / "manifest.json").write_bytes(canonical(manifest))
    with pytest.raises(ValueError, match="rebuild offline"):
        Resources.load(root)


def test_native_detection_matches_independent_oracle(tmp_path, monkeypatch):
    from hadith_detector import HadithDetector
    from tools.exact_benchmark.corpus import Corpus
    from tools.fuzzy_benchmark import oracle
    from tools.validate_fuzzy_runtime import project

    texts = ["عن نافع عن ابن عمر", "عن نافغ عن ابن عمر", "قال ﷺ عن نافع", "عن نافع عن ابن عمر"]
    root = fixture(tmp_path, monkeypatch, texts)
    candidate = HadithDetector.from_directory(root)
    for text in [*texts, "?? ???? ?? ???", "??? ??? ???? ???? ???? ?? ????", "?? ? ????"]:
        for errors, missing in [(0, 0), (1, 0), (0, 1), (1, 1), (3, 2)]:
            params = dict(min_match_words=1, max_errors=errors, max_missing_words=missing)
            expected, _ = oracle.detect(Corpus.synthetic(texts), text, 1, errors, missing)
            assert project(candidate.detect(text, **params)) == expected


def test_failed_build_leaves_no_output(tmp_path, monkeypatch):
    source, _ = prepared(tmp_path / "prepared-v2", ["عن نافع عن ابن عمر"])
    with monkeypatch.context() as patch:
        patch.setattr(build.sys, "version_info", (3, 14))
        patch.setattr(Resources, "load", lambda *args: (_ for _ in ()).throw(ValueError("reject")))
        with pytest.raises(ValueError, match="reject"):
            build.build(source, tmp_path / "v2")
    assert not (tmp_path / "v2").exists()
    assert not list(tmp_path.glob(".index-build-*"))


def test_initialization_loads_only_prebuilt_tries(tmp_path, monkeypatch):
    from hadith_detector import HadithDetector, _marisa

    root = fixture(tmp_path, monkeypatch)
    native = _marisa.marisa_trie.RecordTrie
    calls = []

    def empty_reader(fmt, *args, **kwargs):
        assert fmt == "<I" and not args and not kwargs
        calls.append(fmt)
        return native(fmt)

    monkeypatch.setattr(_marisa.marisa_trie, "RecordTrie", empty_reader)
    detector = HadithDetector.from_directory(root)
    assert len(calls) == 2
    detector.detect("عن نافع عن ابن عمر", max_errors=1)
    detector.detect("عن نافع عن ابن عمر")
    assert len(calls) == 2
