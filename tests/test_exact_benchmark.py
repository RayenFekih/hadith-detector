"""Manual contracts plus a tiny brute-force reference for benchmark correctness."""

import importlib.util
import json
import random
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from hadith_detector._text import tokenize

PACKAGE = Path(__file__).resolve().parents[1] / "tools/exact_benchmark"
spec = importlib.util.spec_from_file_location(
    "_benchmark_tools", PACKAGE / "__init__.py", submodule_search_locations=[str(PACKAGE)]
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
corpus_module = __import__("_benchmark_tools.corpus", fromlist=["Corpus"])
index_module = __import__("_benchmark_tools.indexes", fromlist=["Index"])
oracle = __import__("_benchmark_tools.oracle", fromlist=["detect"])
queries_module = __import__("_benchmark_tools.queries", fromlist=["generate"])
Corpus, Index = corpus_module.Corpus, index_module.Index


def all_results(corpus, text, minimum=5):
    expected = oracle.detect(corpus, text, minimum)[0]
    for candidate in index_module.CANDIDATES:
        assert Index(corpus, candidate).detect(text, minimum)[0] == expected, candidate
    return expected


def test_full_reference_completeness_and_repeated_occurrences():
    phrase = "عن نافع عن ابن عمر"
    corpus = Corpus.synthetic([phrase + " ثم " + phrase, phrase, "عن نافع عن ابن"])
    text = "😀 " + phrase + "."
    result = all_results(corpus, text)
    assert [(r["start"], r["end"], r["matched_words"]) for r in result] == [(2, 20, 5)]
    refs = result[0]["references"]
    assert [r["hadith_key"] for r in refs] == ["fixture:1", "fixture:2"]
    assert [(r["start"], r["end"]) for r in refs[0]["occurrences"]] == [(0, 18), (22, 40)]
    assert all(o["text"] == phrase for ref in refs for o in ref["occurrences"])


def test_longest_match_does_not_attach_shorter_partial_references():
    corpus = Corpus.synthetic(["عن نافع عن ابن عمر قال", "عن نافع عن ابن عمر"])
    result = all_results(corpus, "عن نافع عن ابن عمر قال")
    assert result[0]["matched_words"] == 6
    assert [r["hadith_key"] for r in result[0]["references"]] == ["fixture:1"]


def test_recover_support_from_a_suppressed_larger_alignment():
    corpus = Corpus.synthetic(["ا ب ت ث ج ح", "ج ح خ د ذ", "خ د ذ"])
    result = all_results(corpus, "ا ب ت ث ج ح خ د ذ ر", 3)
    assert [r["text"] for r in result] == ["ا ب ت ث ج ح", "خ د ذ"]
    assert [r["hadith_key"] for r in result[1]["references"]] == ["fixture:2", "fixture:3"]
    assert result[1]["references"][0]["occurrences"] == [{"start": 4, "end": 9, "text": "خ د ذ"}]


def test_no_cross_record_fabrication():
    corpus = Corpus.synthetic(["عن نافع عن", "عن ابن عمر"])
    assert all_results(corpus, "عن نافع عن ابن عمر") == []


def test_supported_nonoverlapping_tail_is_not_lost():
    corpus = Corpus.synthetic(["ا ب ت ث ج ح", "ج ح خ د ذ"])
    result = all_results(corpus, "ا ب ت ث ج ح خ د ذ ر", 3)
    assert [r["text"] for r in result] == ["ا ب ت ث ج ح", "خ د ذ"]
    assert result[1]["references"] == [
        {"hadith_key": "fixture:2", "occurrences": [{"start": 4, "end": 9, "text": "خ د ذ"}]}
    ]


def test_source_and_input_barriers_and_adjacent_passages():
    corpus = Corpus.synthetic(["عن نافع � عن ابن عمر"])
    assert all_results(corpus, "عن نافع عن ابن عمر") == []
    result = all_results(corpus, "عن نافع END عن ابن عمر", 2)
    assert [r["text"] for r in result] == ["عن نافع", "عن ابن عمر"]


def test_symbol_expansions_cannot_be_partially_consumed():
    assert all_results(Corpus.synthetic(["الله عليه وسلم"]), "ﷺ", 1) == []
    assert all_results(Corpus.synthetic(["ﷺ"]), "الله عليه وسلم", 1) == []
    result = all_results(Corpus.synthetic(["صلى الله عليه وسلم"]), "ﷺ", 1)
    assert result[0]["text"] == "ﷺ" and result[0]["matched_words"] == 4
    assert result[0]["references"][0]["occurrences"][0]["text"] == "صلى الله عليه وسلم"


@pytest.mark.parametrize("minimum", [0, -1, True, 1.5, "5", None])
def test_invalid_minimum(minimum):
    corpus = Corpus.synthetic(["عن نافع"])
    with pytest.raises(ValueError):
        oracle.detect(corpus, "عن", minimum)
    for candidate in index_module.CANDIDATES:
        with pytest.raises(ValueError):
            Index(corpus, candidate).detect("عن", minimum)


def test_empty_input_normalization_and_unigram_fallback():
    corpus = Corpus.synthetic(["عَنْ نَافِعٍ", "عن نافع"])
    assert all_results(corpus, "") == []
    result = all_results(corpus, "عن،نافع", 1)
    assert len(result) == 1 and len(result[0]["references"]) == 2
    assert result[0]["references"][0]["occurrences"][0]["text"] == "عَنْ نَافِعٍ"


def test_no_reference_or_occurrence_caps():
    corpus = Corpus.synthetic(["عن عن عن عن"] * 100)
    result = all_results(corpus, "عن", 1)
    assert len(result[0]["references"]) == 100
    assert sum(len(r["occurrences"]) for r in result[0]["references"]) == 400


@pytest.mark.parametrize("candidate", list(index_module.CANDIDATES))
def test_deterministic_serialization_roundtrip_and_corruption(tmp_path: Path, candidate):
    corpus = Corpus.synthetic(["عن نافع عن ابن عمر", "عن عن عن عن", "ﷺ"])
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    index = Index(corpus, candidate)
    index.save(first)
    Index(corpus, candidate).save(second)
    assert first.read_bytes() == second.read_bytes()
    loaded = Index.load(corpus, first)
    for text, minimum in [("عن", 1), ("عن نافع عن ابن عمر", 5), ("ﷺ", 1)]:
        assert loaded.detect(text, minimum) == index.detect(text, minimum)
    rows = [json.loads(line) for line in first.read_text(encoding="utf-8").splitlines()]
    rows[1]["positions"][0][1] = 9999
    first.write_bytes(b"".join(corpus_module.canonical(r) for r in rows))
    with pytest.raises(ValueError, match="posting"):
        Index.load(corpus, first)


def brute_force(corpus, text, minimum):
    query = corpus.query(text)
    matches = {}
    for a in range(len(query)):
        for b in range(a + minimum, len(query) + 1):
            if not (query.window(a, b - a) and query.boundary(a) and query.boundary(b)):
                continue
            refs = {}
            for rid, source in enumerate(corpus.sequences):
                spans = []
                for start in range(len(source) - (b - a) + 1):
                    end = start + b - a
                    if (
                        source.window(start, b - a)
                        and source.boundary(start)
                        and source.boundary(end)
                        and source.terms[start:end] == query.terms[a:b]
                    ):
                        left, right = source.starts[start], source.ends[end - 1]
                        spans.append(
                            {
                                "start": left,
                                "end": right,
                                "text": corpus.records[rid]["text"][left:right],
                            }
                        )
                if spans:
                    refs[rid] = spans
            if refs:
                matches[a, b] = refs
    ranked = sorted(
        matches,
        key=lambda p: (
            -(p[1] - p[0]),
            -(query.ends[p[1] - 1] - query.starts[p[0]]),
            query.starts[p[0]],
            p,
        ),
    )
    selected = []
    for a, b in ranked:
        if all(b <= start or a >= end for start, end in selected):
            selected.append((a, b))
    return [
        {
            "start": query.starts[a],
            "end": query.ends[b - 1],
            "text": text[query.starts[a] : query.ends[b - 1]],
            "matched_words": b - a,
            "references": [
                {"hadith_key": corpus.records[rid]["hadith_key"], "occurrences": spans}
                for rid, spans in sorted(matches[a, b].items())
            ],
        }
        for a, b in sorted(selected)
    ]


def test_random_small_cases_against_direct_substring_enumeration():
    rng = random.Random(42)
    alphabet = ["عن", "ابن", "عمر", "قال", "ﷺ", "�"]
    for _ in range(100):
        corpus = Corpus.synthetic(
            [" ".join(rng.choices(alphabet, k=rng.randint(3, 9))) for _ in range(4)]
        )
        text = " ".join(rng.choices(alphabet, k=rng.randint(2, 9)))
        minimum = rng.randint(1, 5)
        assert all_results(corpus, text, minimum) == brute_force(corpus, text, minimum)


def test_verified_corpus_loader_rejects_tampering(tmp_path: Path):
    corpus = Corpus.synthetic(["عن نافع عن ابن عمر"])
    records = corpus.records
    token_rows = [
        {
            "hadith_key": records[0]["hadith_key"],
            "tokens": [asdict(t) for t in tokenize(records[0]["text"]).tokens],
        }
    ]
    (tmp_path / "records.jsonl").write_bytes(b"".join(corpus_module.canonical(r) for r in records))
    (tmp_path / "tokens.jsonl").write_bytes(
        b"".join(corpus_module.canonical(r) for r in token_rows)
    )
    (tmp_path / "validation.json").write_bytes(b"{}\n")
    manifest = {
        "versions": {"manifest": 1, "normalization": 1, "records": 1, "tokens": 1},
        "artifacts": {
            name: corpus_module.digest(tmp_path / name)
            for name in ("records.jsonl", "tokens.jsonl", "validation.json")
        },
    }
    (tmp_path / "manifest.json").write_bytes(corpus_module.canonical(manifest))
    assert corpus_module.load_corpus(tmp_path).records == records
    (tmp_path / "records.jsonl").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        corpus_module.load_corpus(tmp_path)


def test_query_generation_is_deterministic_and_source_linked():
    corpus = Corpus.synthetic([" ".join(["عن", "ابن", "عمر", "قال", "الله"] * 8)])
    first = queries_module.generate(corpus, per_category=2)
    second = queries_module.generate(corpus, per_category=2)
    assert first == second
    assert len(first["queries"]) == 24
    assert {q["category"] for q in first["queries"]} == set(queries_module.CATEGORIES) | {
        "large-1024",
        "large-4096",
    }
    assert all(
        not oracle.detect(corpus, q["text"], q["minimum"])[0]
        for q in first["queries"]
        if q["category"] == "negative"
    )


@pytest.mark.benchmark
def test_isolated_worker_pipeline_smoke(tmp_path: Path):
    pytest.importorskip("psutil", reason="Install the benchmark dependency group")
    source = tmp_path / "corpus"
    source.mkdir()
    corpus = Corpus.synthetic([" ".join(["عن", "ابن", "عمر", "قال", "الله"] * 8)])
    for name, rows in (
        ("records.jsonl", corpus.records),
        (
            "tokens.jsonl",
            [
                {
                    "hadith_key": corpus.records[0]["hadith_key"],
                    "tokens": [asdict(t) for t in tokenize(corpus.records[0]["text"]).tokens],
                }
            ],
        ),
    ):
        (source / name).write_bytes(b"".join(corpus_module.canonical(row) for row in rows))
    (source / "validation.json").write_bytes(b"{}\n")
    manifest = {
        "versions": {"manifest": 1, "normalization": 1, "records": 1, "tokens": 1},
        "artifacts": {
            name: corpus_module.digest(source / name)
            for name in ("records.jsonl", "tokens.jsonl", "validation.json")
        },
    }
    (source / "manifest.json").write_bytes(corpus_module.canonical(manifest))
    output = tmp_path / "experiment"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.exact_benchmark",
            "run",
            "--corpus-dir",
            str(source),
            "--output-dir",
            str(output),
            "--per-category",
            "1",
        ],
        cwd=PACKAGE.parents[1],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["candidates"]) == 5
    assert all(c["agreement"] and len(c["timings"]) == 16 for c in summary["candidates"])
    assert all(
        c["deterministic_rebuild"] for c in summary["candidates"] if c["candidate"] != "oracle"
    )
    assert all(c["peak_rss_bytes"] > 0 for c in summary["candidates"])
