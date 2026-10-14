"""Compact resources and public exact results, independently checked by the oracle."""

import importlib.util
import json
import random
import socket
import struct
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from hadith_detector import HadithDetector
from hadith_detector._resources import HEADER, canonical, checksum
from hadith_detector._text import tokenize

# Repository modules stay outside the installed package and src/sys.path hacks.
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "tools", ROOT / "tools/__init__.py", submodule_search_locations=[str(ROOT / "tools")]
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["tools"] = module
spec.loader.exec_module(module)
builder = __import__("tools.build_index", fromlist=["build"])
corpus_module = __import__("tools.exact_benchmark.corpus", fromlist=["Corpus"])
oracle = __import__("tools.exact_benchmark.oracle", fromlist=["detect"])


def prepared(path: Path, texts: list[str]) -> tuple[Path, list[dict]]:
    path.mkdir()
    rows = []
    tokens = []
    for i, text in enumerate(texts, 1):
        row = {
            "hadith_key": f"fixture:{i}",
            "urn": 100 + i,
            "seq": i,
            "collection": "fixture",
            "language": "ar",
            "hadith_number": str(i),
            "number_sort": i,
            "book_number": 1,
            "in_book_number": i,
            "sunnah_url": None,
            "text": text,
            "grades": [],
            "n_grades": 0,
            "grade_summary": None,
            "is_muallaq": False,
            "extra": {"values": [1, None, "metadata"]},
        }
        rows.append(row)
        tokens.append(
            {"hadith_key": row["hadith_key"], "tokens": [asdict(t) for t in tokenize(text).tokens]}
        )
    (path / "records.jsonl").write_bytes(b"".join(canonical(r) for r in rows))
    (path / "tokens.jsonl").write_bytes(b"".join(canonical(r) for r in tokens))
    (path / "validation.json").write_bytes(canonical({"records": len(rows), "integrity": "passed"}))
    manifest = {
        "versions": {"manifest": 1, "records": 1, "tokens": 1, "normalization": 1},
        "artifacts": {
            n: checksum(path / n) for n in ("records.jsonl", "tokens.jsonl", "validation.json")
        },
    }
    (path / "manifest.json").write_bytes(canonical(manifest))
    return path, rows


def build_fixture(tmp_path: Path, texts: list[str]) -> tuple[Path, list[dict]]:
    source, rows = prepared(tmp_path / "prepared", texts)
    output = tmp_path / "index"
    # Only the builder's pinned-version check is replaced for synthetic tests on
    # other Pythons; real CLI builds continue to require Python 3.14.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(builder.sys, "version_info", (3, 14))
        builder.build(source, output)
    return output, rows


def project(results):
    return [
        {
            "start": r.start,
            "end": r.end,
            "text": r.text,
            "matched_words": r.matched_words,
            "references": [
                {
                    "hadith_key": ref.record.hadith_key,
                    "occurrences": [
                        {k: o.to_dict()[k] for k in ("start", "end", "text")}
                        for o in ref.occurrences
                    ],
                }
                for ref in r.references
            ],
        }
        for r in results
    ]


@pytest.fixture
def index(tmp_path: Path):
    return build_fixture(
        tmp_path,
        [
            "عن نافع عن ابن عمر ثم عن نافع عن ابن عمر",
            "عن نافع عن ابن عمر",
            "ﷺ",
            "ا ب ت ث ج ح",
            "ج ح خ د ذ",
            "عن نافع � عن ابن عمر",
            "",
        ],
    )


def test_runtime_matches_oracle_for_boundaries_and_minimums(index):
    output, rows = index
    detector = HadithDetector.from_directory(output)
    corpus = corpus_module.Corpus.synthetic([r["text"] for r in rows])
    cases = [
        ("عن نافع عن ابن عمر", 5),
        ("عن", 1),
        ("عن،نافع", 2),
        ("ﷺ", 1),
        ("الله عليه وسلم", 1),
        ("صلى الله عليه وسلم", 4),
        ("ا ب ت ث ج ح خ د ذ ر", 3),
        ("عن نافع END عن ابن عمر", 2),
        ("", 5),
    ]
    for text, minimum in cases:
        expected = oracle.detect(corpus, text, minimum)[0]
        assert project(detector.detect(text, min_match_words=minimum)) == expected
    assert [r.text for r in detector.detect("ا ب ت ث ج ح خ د ذ ر", min_match_words=3)] == [
        "ا ب ت ث ج ح",
        "خ د ذ",
    ]


def test_records_serialization_and_mutation_isolation(index):
    output, rows = index
    detector = HadithDetector.from_directory(output)
    record = detector.get_hadith("fixture:1")
    assert record.to_dict() == rows[0]
    record.additional_metadata["extra"]["values"].append("mutation")
    assert detector.get_hadith("fixture:1").to_dict() == rows[0]
    result = detector.detect("عن نافع عن ابن عمر")[0]
    assert len(result.references[0].occurrences) == 2
    serialized = result.to_dict()
    serialized["references"][0]["record"]["extra"]["values"].append("mutation")
    assert detector.detect("عن نافع عن ابن عمر")[0].references[0].record.to_dict() == rows[0]
    assert json.loads(json.dumps(result.to_dict(), ensure_ascii=False)) == result.to_dict()


def test_loader_and_calls_do_not_tokenize_source_or_write(index, monkeypatch):
    output, _ = index
    import hadith_detector._text as normalization
    import hadith_detector.detector as runtime

    before = {p.name: checksum(p) for p in output.iterdir()}

    def fail(*args, **kwargs):
        raise AssertionError("Unexpected source normalization, resource reload or network access")

    monkeypatch.setattr(socket, "socket", fail)
    monkeypatch.setattr(normalization, "tokenize", fail)
    detector = HadithDetector.from_directory(output)
    monkeypatch.setattr(runtime.Resources, "load", fail)
    for _ in range(3):
        assert detector.detect("عن نافع عن ابن عمر")
        assert detector.get_hadith("fixture:1")
    assert {p.name: checksum(p) for p in output.iterdir()} == before


@pytest.mark.parametrize("minimum", [0, -1, True, 1.5, "5"])
def test_invalid_minimum(index, minimum):
    detector = HadithDetector.from_directory(index[0])
    with pytest.raises(ValueError, match="positive integer"):
        detector.detect("", min_match_words=minimum)


def test_invalid_input_and_unknown_identity(index):
    detector = HadithDetector.from_directory(index[0])
    with pytest.raises(TypeError):
        detector.detect(None)
    with pytest.raises(TypeError):
        detector.get_hadith(None)
    with pytest.raises(KeyError):
        detector.get_hadith("fixture:missing")


def test_missing_resources(index, tmp_path):
    with pytest.raises(FileNotFoundError):
        HadithDetector.from_directory(tmp_path / "missing")
    (index[0] / "tokens.bin").unlink()
    with pytest.raises(FileNotFoundError):
        HadithDetector.from_directory(index[0])


def rehash(output: Path, filename: str):
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["artifacts"][filename] = checksum(output / filename)
    (output / "manifest.json").write_bytes(canonical(manifest))


@pytest.mark.parametrize(
    "damage",
    ["checksum", "header", "length", "span", "postings", "directory", "version", "vocabulary"],
)
def test_malformed_resources_rejected(index, damage):
    output = index[0]
    if damage == "version":
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        manifest["versions"]["index"] = 999
        (output / "manifest.json").write_bytes(canonical(manifest))
    elif damage == "vocabulary":
        import marisa_trie

        marisa_trie.RecordTrie("<I", [("عن", (0,)), ("عن", (1,))]).save(
            str(output / "vocabulary.marisa")
        )
        rehash(output, "vocabulary.marisa")
    else:
        filename = {"postings": "unigram-postings.bin", "directory": "unigram-offsets.bin"}.get(
            damage, "tokens.bin"
        )
        data = bytearray((output / filename).read_bytes())
        if damage in ("checksum", "header"):
            data[0] ^= 255
        elif damage == "length":
            data.pop()
        elif damage == "span":
            struct.pack_into("<I", data, HEADER.size + 8, 999999)
        elif damage == "directory":
            struct.pack_into("<Q", data, HEADER.size, 999999)
        else:
            struct.pack_into("<Q", data, HEADER.size, (999999 << 32))
        (output / filename).write_bytes(data)
        if damage != "checksum":
            rehash(output, filename)
    with pytest.raises(ValueError):
        HadithDetector.from_directory(output)


def test_deterministic_rebuild_and_independent_instances(index, tmp_path):
    source = tmp_path / "prepared"
    second = tmp_path / "second"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(builder.sys, "version_info", (3, 14))
        builder.build(source, second)
    for path in index[0].iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    a, b = HadithDetector.from_directory(index[0]), HadithDetector.from_directory(second)
    a.get_hadith("fixture:1").grades.append({"grader": "changed", "grade": "changed"})
    assert a.detect("عن نافع عن ابن عمر") == b.detect("عن نافع عن ابن عمر")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(builder.sys, "version_info", (3, 14))
        with pytest.raises(ValueError, match="already exists"):
            builder.build(source, second)


def test_no_caps_and_empty_corpus_tokens(tmp_path):
    output, _ = build_fixture(tmp_path, ["عن عن عن عن"] * 100 + [""])
    result = HadithDetector.from_directory(output).detect("عن", min_match_words=1)
    assert len(result[0].references) == 100
    assert sum(len(ref.occurrences) for ref in result[0].references) == 400


def test_small_randomized_production_results_against_oracle(tmp_path):
    rng = random.Random(42)
    alphabet = ["عن", "ابن", "عمر", "قال", "ﷺ", "�"]
    texts = [" ".join(rng.choices(alphabet, k=rng.randint(3, 9))) for _ in range(12)]
    output, _ = build_fixture(tmp_path, texts)
    detector = HadithDetector.from_directory(output)
    corpus = corpus_module.Corpus.synthetic(texts)
    for _ in range(100):
        text = " ".join(rng.choices(alphabet, k=rng.randint(2, 9)))
        minimum = rng.randint(1, 5)
        assert (
            project(detector.detect(text, min_match_words=minimum))
            == oracle.detect(corpus, text, minimum)[0]
        )


def test_failed_build_leaves_no_accepted_directory(tmp_path, monkeypatch):
    source, _ = prepared(tmp_path / "prepared", ["عن نافع عن ابن عمر"])

    def fail(*args, **kwargs):
        raise ValueError("simulated resource failure")

    monkeypatch.setattr(builder.Resources, "load", fail)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(builder.sys, "version_info", (3, 14))
        with pytest.raises(ValueError, match="simulated"):
            builder.build(source, tmp_path / "index")
    assert not (tmp_path / "index").exists()
    assert not list(tmp_path.glob(".index-build-*"))
