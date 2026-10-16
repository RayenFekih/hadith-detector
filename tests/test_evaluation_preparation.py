"""Focused quality-preparation checks; no historical benchmark reruns."""

import csv
import hashlib
import json
import socket

import pytest

from hadith_detector import HadithDetector
from tools.evaluation import acquire, dataset, pipeline, review
from tools.exact_benchmark.corpus import canonical, digest

from .test_detector import build_fixture


def natural(text, identity="N0001", label="quotation_free"):
    return {
        "case_id": identity,
        "group": "natural_text",
        "stratum": "general_arabic",
        "text": text,
        "proposed_case_label": label,
        "proposals": [],
        "source": {
            "url": "https://example.org/?oldid=1",
            "revision": 1,
            "start": 0,
            "end": len(text),
            "text": text,
        },
    }


@pytest.fixture
def prepared(tmp_path):
    text = "عن نافع عن ابن عمر"
    index, original = build_fixture(tmp_path, [f"{text} ثم {text}", text])
    cases = [natural(text), natural("=1+1\r\n😀 " + text, "N0002", "contains_quotation")]
    cases[1]["proposals"] = [
        {
            "start": 0,
            "end": len(cases[1]["text"]),
            "label": "uncertain",
            "flags": "fixture",
            "note": "Input first",
        }
    ]
    folder = tmp_path / "dataset"
    folder.mkdir()
    (folder / "cases.jsonl").write_bytes(b"".join(canonical(c) for c in cases))
    (folder / "manifest.json").write_bytes(
        canonical(
            {
                "cases_sha256": digest(folder / "cases.jsonl"),
                "gold_approved": False,
            }
        )
    )
    return folder, index, cases, original


def test_evidence_replay_and_single_review_csv(prepared, tmp_path, monkeypatch):
    folder, index, cases, original = prepared

    def no_network(*args, **kwargs):
        raise AssertionError("Offline evaluation attempted network access")

    monkeypatch.setattr(socket, "socket", no_network)
    output = tmp_path / "run"
    summary = pipeline.run(folder, index, output)
    assert not summary["gold_approved"]
    assert summary["groups"]["corpus_derived"][pipeline.DEFAULT]["all_detections"] == 0
    default = summary["groups"]["natural_text"][pipeline.DEFAULT]
    assert default["affected_paragraphs"] == ["N0001"]
    assert default["candidate_unwanted_detections"] == 1
    assert default["delta_unwanted_detections_vs_default"] == 0
    rows = review.decode_csv((output / "review.csv").read_bytes())
    assert all(row["decision"] == "" for row in rows)
    span = next(r for r in rows if r["case_id"] == "N0001" and r["row_kind"] == "span")
    assert span["supporting_references"] == "fixture:1;fixture:2"
    assert len(span["configurations"].split(";")) == 5  # Seven words cannot fit this input.
    assert span["proposed_intent"] == "not_intended_quotation"
    assert span["corpus_support"] == "detector_supported"
    assert len([r for r in rows if r["case_id"] == "N0001" and r["row_kind"] == "span"]) == 1
    evidence = [
        json.loads(line)
        for line in (output / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(evidence) == len(cases) * 6
    result = next(
        r for r in evidence if r["case_id"] == "N0001" and r["config"] == pipeline.DEFAULT
    )
    ref = result["detections"][0]["references"][0]
    assert ref["record"] == original[0]
    assert len(ref["occurrences"]) == 2
    assert ref["record"]["sunnah_url"] is None
    assert (output / "review.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert pipeline.check_review(folder, output, output / "review.csv")["gold_approved"] is False
    assert pipeline.replay(folder, output, tmp_path / "replayed") == {
        "reproduced": True,
        "detector_calls": 0,
    }
    for name in ("review.csv", "candidate-alerts.jsonl", "preparation-summary.json"):
        assert (output / name).read_bytes() == (tmp_path / "replayed" / name).read_bytes()
    with pytest.raises(FileExistsError):
        pipeline.run(folder, index, output)


def test_review_corrections_and_missing_quotation(prepared, tmp_path):
    folder, index, cases, _ = prepared
    output = tmp_path / "run"
    pipeline.run(folder, index, output)
    rows = review.decode_csv((output / "review.csv").read_bytes())
    case = next(r for r in rows if r["proposal_id"] == "N0001:case")
    case.update(decision="correct", corrected_case_label="contains_quotation")
    extra = review.base_row(cases[0], "span", "manual:N0001:1")
    extra.update(
        decision="correct",
        corrected_start="0",
        corrected_end="2",
        corrected_intent="intended_quotation",
        corrected_references="fixture:1",
    )
    rows.append(extra)
    edited = tmp_path / "reviewed.csv"
    edited.write_bytes(review.encode_csv(rows))
    checked = pipeline.check_review(folder, output, edited)
    assert checked["decisions"]["correct"] == 2 and not checked["gold_approved"]
    resolved = review.resolve_drafts(rows)
    assert not resolved["gold_approved"]
    item = resolved["proposals"][-1]
    assert (item["start"], item["end"]) == (0, 2)
    assert item["references_complete"] is False
    extra["corrected_end"] = "999999"
    edited.write_bytes(review.encode_csv(rows))
    with pytest.raises(ValueError):
        pipeline.check_review(folder, output, edited)


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(decision="approved"),
        lambda r: r.update(input_text="edited input"),
        lambda r: r.update(corrected_references="fabricated:999"),
        lambda r: r.update(configurations="m99-e0-o0"),
        lambda r: r.update(corrected_start="0"),
    ],
)
def test_invalid_review_values(change):
    cases = [natural("نص للمراجعة")]
    row = review.base_row(cases[0], "case", "N0001:case")
    change(row)
    with pytest.raises(ValueError):
        review.validate_review([row], cases, {}, pipeline.CONFIGURATIONS)


def test_uncertainty_and_csv_escape_are_not_silent_labels():
    case = natural(' \t=HYPERLINK("bad")\r\nنص عربي', label="uncertain")
    row = review.base_row(case, "case", "N0001:case")
    payload = review.encode_csv([row])
    assert "csv_escaped_fields" in payload.decode("utf-8-sig")
    assert review.decode_csv(payload) == [row]
    row["decision"] = "uncertain"
    assert review.validate_review([row], [case], {}, pipeline.CONFIGURATIONS)["decisions"] == {
        "uncertain": 1
    }
    resolved = review.resolve_drafts([row])
    assert "classification" not in resolved["proposals"][0]


def test_failed_run_leaves_no_accepted_output(prepared, tmp_path, monkeypatch):
    folder, index, _, _ = prepared

    def fail(*args, **kwargs):
        raise RuntimeError("interrupted capture")

    monkeypatch.setattr(HadithDetector, "detect", fail)
    output = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="interrupted"):
        pipeline.run(folder, index, output)
    assert not output.exists()
    assert not list(tmp_path.glob(".evaluation-*"))


def test_manifest_and_protected_review_columns(prepared, tmp_path):
    folder, index, _, _ = prepared
    output = tmp_path / "run"
    pipeline.run(folder, index, output)
    rows = review.decode_csv((output / "review.csv").read_bytes())
    rows[0]["proposed_case_label"] = "contains_quotation"
    edited = tmp_path / "edited.csv"
    edited.write_bytes(review.encode_csv(rows))
    with pytest.raises(ValueError, match="proposal changed"):
        pipeline.check_review(folder, output, edited)
    (output / "candidate-alerts.jsonl").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        pipeline.verify_run(output)


def test_frozen_case_checksum(prepared):
    folder, _, _, _ = prepared
    with (folder / "cases.jsonl").open("ab") as stream:
        stream.write(b" ")
    with pytest.raises(ValueError, match="checksum"):
        dataset.load(folder)


def test_large_reference_sets_are_preserved_outside_csv_cells(tmp_path):
    from types import SimpleNamespace

    case = natural("نص عربي للمراجعة")
    keys = {f"fixture:{i}": i for i in range(120)}
    match = SimpleNamespace(
        start=0,
        end=len(case["text"]),
        errors=0,
        missing_words=0,
        references=[SimpleNamespace(record=SimpleNamespace(hadith_key=key)) for key in keys],
    )
    pipeline.publish_review(
        [case], lambda c: {k: [match] for k in pipeline.CONFIGURATIONS}, keys, tmp_path
    )
    rows = review.decode_csv((tmp_path / "review.csv").read_bytes())
    span = next(row for row in rows if row["row_kind"] == "span")
    assert span["supporting_reference_count"] == "120"
    assert len(span["supporting_references"].split(";")) == 50
    union = json.loads((tmp_path / "reference-unions.jsonl").read_text())
    assert union["supporting_references"] == list(keys)
    assert union["reference_union_id"] == span["reference_union_id"]


def test_source_extraction_and_pinned_fetch(tmp_path, monkeypatch):
    text = "رسول الله " + "كلمة " * 25
    payload = {"parse": {"revid": 123, "text": f"<p>{text}<sup>[1]</sup><br>آخر &amp; نص</p>"}}
    parser = acquire.Paragraphs()
    parser.feed(payload["parse"]["text"])
    assert parser.items == [text + "\nآخر & نص"]
    calls = []

    def fetch(host, parameters):
        calls.append(parameters)
        assert parameters["oldid"] == 123
        return payload

    monkeypatch.setattr(acquire, "request", fetch)
    selection = tmp_path / "selection.json"
    selection.write_bytes(
        canonical(
            {
                "selection": "fixture",
                "sources": [
                    {
                        "host": "example.org",
                        "title": "fixture",
                        "stratum": "quotation_rich",
                        "count": 1,
                        "revision": 123,
                        "snapshot_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
                        "reuse": {},
                    }
                ],
            }
        )
    )
    frozen = acquire.fetch(selection, tmp_path / "sources")
    assert len(calls) == 1 and frozen["sources"][0]["revision"] == 123


def test_freeze_96_and_40_is_reproducible_without_detector(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy.csv"
    fields = [
        "sample_id",
        "query_text",
        "source_start",
        "source_end",
        "source_text",
        "gold_label",
        "expected_references",
        "reviewer_notes",
        "sample_stratum",
        "source_hadith_key",
        "sunnah_url",
    ]
    text = "رسول الله " + "كلمة " * 25
    with legacy.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for i in range(96):
            row = dict.fromkeys(fields, "")
            row.update(
                sample_id=f"S{i:04d}",
                query_text=text,
                source_start=0,
                source_end=len(text),
                source_text=text,
                sample_stratum="opening_window",
                source_hadith_key="fixture:1",
            )
            writer.writerow(row)
    sources = tmp_path / "sources"
    sources.mkdir()
    entries = []
    for i in range(8):
        payload = {"parse": {"text": f"<p>{text}</p>" * 5}}
        name = f"page{i}.json"
        (sources / name).write_bytes(canonical(payload))
        full = "\n\n".join([text] * 5)
        entries.append(
            {
                "stratum": "quotation_rich" if i < 4 else "general_arabic",
                "snapshot": name,
                "snapshot_sha256": digest(sources / name),
                "plain_text_sha256": hashlib.sha256(full.encode()).hexdigest(),
                "selected": [
                    {
                        "start": j * (len(text) + 2),
                        "end": j * (len(text) + 2) + len(text),
                        "paragraph": j,
                    }
                    for j in range(5)
                ],
                "url": "https://example.org",
                "revision": 1,
            }
        )
    (sources / "sources.lock.json").write_bytes(canonical({"sources": entries}))
    real_read = dataset.read

    def read(path):
        if path.name == "natural-drafts.json":
            return {
                "annotations": {
                    f"N{i:04d}": {
                        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "proposals": [],
                        "case_label": "uncertain",
                    }
                    for i in range(1, 21)
                }
            }
        return real_read(path)

    monkeypatch.setattr(dataset, "read", read)
    monkeypatch.setattr(
        HadithDetector, "__init__", lambda *a, **k: pytest.fail("Detector loaded during freeze")
    )
    for name in ("frozen-a", "frozen-b"):
        dataset.freeze(legacy, sources, tmp_path / name)
    assert (tmp_path / "frozen-a/cases.jsonl").read_bytes() == (
        tmp_path / "frozen-b/cases.jsonl"
    ).read_bytes()
    assert (tmp_path / "frozen-a/manifest.json").read_bytes() == (
        tmp_path / "frozen-b/manifest.json"
    ).read_bytes()
    cases, _ = dataset.load(tmp_path / "frozen-a")
    assert len(cases) == 136
    assert sum(c["proposed_case_label"] == "uncertain" for c in cases) == 116
    assert sum(c["proposed_case_label"] == "quotation_free" for c in cases) == 20
    with pytest.raises(FileExistsError):
        dataset.freeze(legacy, sources, tmp_path / "frozen-a")
