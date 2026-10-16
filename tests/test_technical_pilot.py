"""Small pilot preparation, technical decisions and notebook callbacks; no historical reruns."""

import copy
import html
import json
import os
from pathlib import Path

import pytest

from hadith_detector._text import tokenize
from tools.evaluation import pipeline
from tools.evaluation.pilot import EXACT_STRATA, exact_case, fuzzy_case, positive, select, verified
from tools.evaluation.pilot_review import PilotSession, assemble, metrics
from tools.exact_benchmark.corpus import canonical, digest

from .test_evaluation_preparation import prepared as prepared_fixture

prepared = prepared_fixture


def write_manifest(path, kind, **extra):
    (path / "manifest.json").write_bytes(
        canonical(
            {
                "version": 1,
                "kind": kind,
                **extra,
                "artifacts": {
                    p.name: digest(p) for p in path.iterdir() if p.name != "manifest.json"
                },
            }
        )
    )


@pytest.fixture
def technical(prepared, tmp_path):  # noqa: F811
    dataset, index, _, records = prepared
    old = tmp_path / "original-run"
    pipeline.run(dataset, index, old)
    text = " ".join(t.term for t in tokenize(records[0]["text"]).tokens[:5])
    exact = positive(
        "N0001",
        "exact",
        "quote_marked",
        text,
        records[0],
        list(range(5)),
        0,
        0,
        {"parent_id": "N0001"},
    )
    missed = {**copy.deepcopy(exact), "case_id": "M0001"}
    negative = {
        "case_id": "Nzero",
        "parent_id": "Nzero",
        "group": "natural",
        "subtype": "negative_candidate",
        "text": "<script>😀 زظزظ</script>",
        "target": None,
        "provenance": {"source": {"url": "fixture"}},
    }
    cases = [exact, missed, negative]
    inputs = tmp_path / "pilot-inputs"
    inputs.mkdir()
    (inputs / "cases.jsonl").write_bytes(b"".join(canonical(c) for c in cases))
    write_manifest(inputs, "technical_pilot_inputs")
    run = tmp_path / "pilot-run"
    run.mkdir()
    rows = [
        json.loads(line)
        for line in (old / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rows = [r for r in rows if r["case_id"] == "N0001"]
    for identity in ("M0001", "Nzero"):
        rows.extend(
            {"case_id": identity, "config": config, "detections": []}
            for config in pipeline.CONFIGURATIONS
        )
    (run / "evidence.jsonl").write_bytes(b"".join(canonical(r) for r in rows))
    review = assemble(cases, run / "evidence.jsonl")
    (run / "review.json").write_bytes(canonical(review))
    write_manifest(
        run, "technical_pilot_capture", inputs_manifest_sha256=digest(inputs / "manifest.json")
    )
    return PilotSession(inputs, run, tmp_path / "technical-progress.json")


def selection_inputs(records):
    record = records[0]
    tokens = tokenize(record["text"]).tokens
    text = record["text"][: tokens[7].end]
    cases = []
    for stratum in EXACT_STRATA:
        for number in range(6):
            cases.append(
                {
                    "case_id": f"{stratum}-{number}",
                    "group": "corpus_derived",
                    "stratum": stratum,
                    "text": text,
                    "source": {
                        "hadith_key": record["hadith_key"],
                        "text": record["text"],
                        "start": 0,
                        "end": len(text),
                    },
                }
            )
    for source in range(4):
        for number in range(5):
            cases.append(
                {
                    "case_id": f"natural-{source}-{number}",
                    "group": "natural_text",
                    "stratum": "general_arabic",
                    "text": f"Natural {source} {number}",
                    "source": {"url": f"https://example.org/{source}"},
                }
            )
    queries = []
    for category, count in (("edits", 7), ("omissions", 7), ("combined", 4)):
        for number in range(count):
            terms = [t.term for t in tokens[:8]]
            mutations = []
            if category != "edits":
                mutations.append({"kind": "omit", "current_word": 3, "term": terms.pop(3)})
            if category != "omissions":
                old = terms[0]
                terms[0] += "ز"
                mutations.append(
                    {"kind": "insert", "input_word": 0, "original": old, "mutated": terms[0]}
                )
            queries.append(
                {
                    "id": f"{category}-{number}",
                    "category": category,
                    "minimum": 5,
                    "errors": int(category != "omissions"),
                    "missing": int(category != "edits"),
                    "text": " ".join(terms),
                    "source_hint": record["hadith_key"],
                    "source_token_start": 0,
                    "mutations": mutations,
                }
            )
    return cases, queries


def test_input_only_deterministic_selection(prepared, monkeypatch):
    _, _, _, records = prepared
    cases, queries = selection_inputs(records)
    mapping = {r["hadith_key"]: r for r in records}

    def forbidden(*args, **kwargs):
        raise AssertionError("Selection must not initialize detection")

    import hadith_detector

    monkeypatch.setattr(hadith_detector, "HadithDetector", forbidden)
    chosen, manifest = select(cases, queries, mapping)
    repeated, second = select(list(reversed(cases)), list(reversed(queries)), mapping)
    assert chosen == repeated and manifest == second
    assert len(chosen) == 50 and manifest["selection_before_results"]
    assert [c["group"] for c in chosen].count("exact") == 20
    assert [c["group"] for c in chosen].count("fuzzy") == 15
    assert [c["group"] for c in chosen].count("natural") == 15
    assert [c["subtype"] for c in chosen].count("combined") == 3
    bad = copy.deepcopy(cases[0])
    bad["text"] = "bad extraction"
    with pytest.raises(ValueError, match="round trip"):
        exact_case(bad, mapping)
    bad_query = copy.deepcopy(queries[0])
    bad_query["mutations"][0]["original"] = "wrong"
    with pytest.raises(ValueError, match="original word"):
        fuzzy_case(bad_query, mapping)


def test_projection_deduplicates_and_keeps_every_occurrence(technical):
    review = technical.review
    assert review["workload"]["input_screens"] == 3
    assert review["workload"]["detected_unique_spans"] == 1
    assert review["workload"]["expected_target_checks"] == 1
    assert review["workload"]["total_judgments"] == 4
    assert review["workload"]["zero_alert_acknowledgements"] == 1
    item = review["cards"][0]["items"][0]
    assert len(item["configurations"]) == 5
    assert item["representative"]["record"]["hadith_key"] == "fixture:1"
    for evidence_id in item["evidence_ids"]:
        detection = technical.evidence(evidence_id)
        assert len(detection["references"]) == 2
        assert len(detection["references"][0]["occurrences"]) == 2
        assert detection["references"][0]["record"]["sunnah_url"] is None


def test_simple_decisions_atomic_resume_and_uncertainty(technical, monkeypatch):
    identity = next(iter(technical.items))
    technical.update(identity, correspondence="yes", boundaries="correct")
    assert not technical.complete(
        technical.cards[0]
    )  # Pending boundary correction is a saved draft.
    restored = PilotSession(technical.inputs, technical.run_dir, technical.progress_path)
    assert restored.progress == technical.progress
    technical.update(identity, input_start=1, input_end=technical.items[identity][1]["end"])
    assert technical.complete(technical.cards[0])
    technical.update(identity, correspondence="no", notes="Wrong correspondence")
    technical.update(identity, correspondence="uncertain", notes="Needs review")
    saved = technical.progress_path.read_bytes()
    before = copy.deepcopy(technical.progress)

    def interrupted(*args):
        raise OSError("interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", interrupted)
        with pytest.raises(OSError, match="interrupted"):
            technical.update(identity, notes="Must not persist")
    assert technical.progress_path.read_bytes() == saved
    assert technical.progress == before
    assert not list(technical.progress_path.parent.glob(".pilot-progress-*.tmp"))
    technical.acknowledge("Nzero")
    restored = PilotSession(technical.inputs, technical.run_dir, technical.progress_path)
    assert restored.progress == technical.progress
    assert restored.current == 1  # Resume the missed target, not the already reviewed input.
    assert technical.validate(technical.progress)["human_review_approved"] is False


def test_malformed_progress_and_stale_writer_rejected(technical):
    identity = next(iter(technical.items))
    for change in [
        dict(correspondence="accept"),
        dict(boundaries="no"),
        dict(boundaries="correct", input_start=True, input_end=3),
        dict(boundaries="correct", source_start=-1, source_end=3),
        dict(input_start=0, input_end=3),
        dict(unexpected="value"),
    ]:
        with pytest.raises(ValueError):
            technical.update(identity, **change)
    technical.save(technical.progress)
    stale = PilotSession(technical.inputs, technical.run_dir, technical.progress_path)
    technical.update(identity, notes="New edit")
    with pytest.raises(ValueError, match="externally"):
        stale.update(identity, notes="Stale edit")
    with pytest.raises(ValueError, match="separate"):
        PilotSession(
            technical.inputs, technical.run_dir, technical.inputs.parent / "phase6-reviewed.csv"
        )
    bad = copy.deepcopy(technical.progress)
    bad["kind"] = "intent_review"
    with pytest.raises(ValueError, match="format"):
        technical.validate(bad)


def test_metrics_eligibility_missing_targets_and_withheld_scores(technical):
    result = metrics(technical)
    default = result["configurations"][pipeline.DEFAULT]
    assert default["all_positive_recovery"] == {"count": 1, "denominator": 2}
    assert default["positives"]["exact"]["construction_eligible"] == 2
    assert result["configurations"]["m7-e0-o0"]["positives"]["exact"]["construction_eligible"] == 0
    assert default["natural"]["detections"] == 0
    assert result["human_review_approved"] is False
    assert result["precision_recall"] == "not_estimated"
    assert result["reviewed_error_scores"] == "withheld_until_maintainer_review"


def test_html_slicing_overlaps_and_shared_symbol_omissions():
    pytest.importorskip("ipywidgets")
    from tools.evaluation.pilot_widgets import marked, source_passage

    text = "😀 قَالَ <script>x</script> ﷺ"
    a, b = text.index("ق"), text.index(" <")
    rendered = marked(text, [(a, b), (a, b - 1)])
    assert "&lt;script&gt;" in rendered and "<script>" not in rendered
    assert "😀" in rendered and 'dir="rtl"' in rendered
    symbol = len(text) - 1
    item = {
        "representative": {
            "record": {"text": text},
            "occurrence": {
                "start": a,
                "end": len(text),
                "omitted_source_tokens": [
                    {"start": symbol, "end": len(text), "text": "ﷺ"},
                    {"start": symbol, "end": len(text), "text": "ﷺ"},
                ],
            },
        }
    }
    source = source_passage(item)
    assert source.count("ﷺ") == 1 and "#ffd4db" in source
    assert "<script>" not in source
    assert html.escape(text[a:symbol]) in source
    color_text = "قال #ffe28a"
    literal = {
        "representative": {
            "record": {"text": color_text},
            "occurrence": {
                "start": 0,
                "end": len(color_text),
                "omitted_source_tokens": [],
            },
        }
    }
    assert "قال #ffe28a" in source_passage(literal)


def test_widgets_autosave_all_choices_and_single_input_screen(technical):
    pytest.importorskip("ipywidgets")
    from tools.evaluation.pilot_widgets import PilotWidget

    ui = PilotWidget(technical)
    assert len(ui.forms) == 1
    identity = next(iter(ui.forms))
    form = ui.forms[identity]
    assert form["correspondence"].value is None and form["boundaries"].value is None
    for value in ("yes", "no", "uncertain"):
        form["correspondence"].value = value
        assert (
            json.loads(technical.progress_path.read_text(encoding="utf-8"))["decisions"][identity][
                "correspondence"
            ]
            == value
        )
    form["boundaries"].value = "correct"
    assert form["correction"].layout.display == ""
    assert not technical.complete(technical.cards[0])
    form["fields"]["input_start"].value = 1
    assert technical.complete(technical.cards[0])
    for value in ("uncertain", "yes"):
        form["boundaries"].value = value
        assert technical.progress["decisions"][identity]["boundaries"] == value
        assert technical.progress["decisions"][identity]["input_start"] is None
    form["notes"].value = "Optional test note"
    ui.save_next()
    assert technical.current == 1
    assert len(ui.forms) == 1
    missed = next(iter(ui.forms.values()))
    missed["correspondence"].value = "yes"
    missed["boundaries"].value = "yes"
    ui.save_next()
    assert technical.current == 2 and not ui.forms
    ui.save_next()
    assert technical.current is None
    assert "Nzero" in technical.progress["acknowledged_cases"]
    ui.filter.value = "all"
    assert technical.current == 0
    assert technical.progress["decisions"][identity]["notes"] == "Optional test note"
    restored = PilotSession(technical.inputs, technical.run_dir, technical.progress_path)
    assert restored.current is None


def test_artifact_integrity_and_two_cell_notebook(technical):
    nb = json.loads(Path("notebooks/phase6_review.ipynb").read_text(encoding="utf-8"))
    cells = [c for c in nb["cells"] if c["cell_type"] == "code"]
    # Executing the review legitimately adds outputs; never erase reviewer state for a test.
    assert len(cells) == 2
    assert "phase6-pilot-55-progress.json" in "".join(cells[0]["source"])
    path = technical.inputs / "cases.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        verified(technical.inputs, "technical_pilot_inputs")


def test_55_profile_keeps_all_commentary_independently_of_labels(prepared):  # noqa: F811
    _, _, _, records = prepared
    cases, queries = selection_inputs(records)
    for number in range(20):
        cases.append(
            {
                "case_id": f"comment-{number}",
                "group": "natural_text",
                "stratum": "quotation_rich",
                "text": f"Frozen commentary {number}",
                "proposed_case_label": "uncertain" if number % 2 else "quotation_free",
                "source": {"url": "https://example.org/commentary"},
            }
        )
    mapping = {r["hadith_key"]: r for r in records}
    old, _ = select(cases, queries, mapping)
    new, manifest = select(cases, queries, mapping, profile="55")
    repeat, repeated_manifest = select(cases[::-1], queries[::-1], mapping, profile="55")
    assert new == repeat and manifest == repeated_manifest
    assert len(new) == 55
    assert {
        g: sum(c["group"] == g for c in new) for g in ("exact", "fuzzy", "natural", "commentary")
    } == {
        "exact": 10,
        "fuzzy": 10,
        "natural": 15,
        "commentary": 20,
    }
    assert {c["case_id"] for c in new if c["group"] != "commentary"} <= {c["case_id"] for c in old}
    assert {c["case_id"] for c in new if c["group"] == "commentary"} == {
        f"comment-{n}" for n in range(20)
    }
    assert sum(c["subtype"] == "combined" for c in new) == 2


def migration_destination(old, tmp_path, *, changed_display=False, changed_support=False):
    cases = [c for c in old.cases if c["case_id"] != "M0001"]
    inputs = tmp_path / "new-inputs"
    inputs.mkdir()
    (inputs / "cases.jsonl").write_bytes(b"".join(canonical(c) for c in cases))
    write_manifest(inputs, "technical_pilot_inputs")
    run = tmp_path / "new-capture"
    run.mkdir()
    rows = [
        json.loads(line)
        for line in (old.run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rows = [r for r in rows if r["case_id"] != "M0001"]
    if changed_support:
        for row in rows:
            for detection in row["detections"]:
                detection["references"][1]["record"]["sunnah_url"] = "https://example.org/changed"
    (run / "evidence.jsonl").write_bytes(b"".join(canonical(r) for r in rows))
    review = assemble(cases, run / "evidence.jsonl")
    if changed_display:
        item = review["cards"][0]["items"][0]
        original = old.evidence(item["evidence_ids"][0])
        item["representative"]["occurrence"] = original["references"][0]["occurrences"][1]
    (run / "review.json").write_bytes(canonical(review))
    write_manifest(
        run, "technical_pilot_capture", inputs_manifest_sha256=digest(inputs / "manifest.json")
    )
    return PilotSession(inputs, run, tmp_path / "new-progress.json")


def test_migration_preserves_answers_and_requires_exclusion_approval(technical, tmp_path):
    from tools.evaluation.pilot_migration import activate, propose

    first = technical.cards[0]["items"][0]["item_id"]
    missed = technical.cards[1]["items"][0]["item_id"]
    technical.update(first, correspondence="uncertain", boundaries="yes", notes="Keep verbatim")
    technical.update(
        missed, correspondence="no", boundaries="uncertain", notes="Retain excluded judgment"
    )
    technical.acknowledge("Nzero")
    before = technical.progress_path.read_bytes()
    new = migration_destination(technical, tmp_path)
    output = tmp_path / "migration"
    report = propose(technical, new, output)
    assert report["migrated_items"] == [first]
    assert report["unmigrated"][0]["answer"] == technical.progress["decisions"][missed]
    assert report["migrated_zero_alert_acknowledgements"] == ["Nzero"]
    assert (output / "original-progress.json").read_bytes() == before
    assert not new.progress_path.exists()
    with pytest.raises(ValueError, match="explicit approval"):
        activate(output, technical.progress_path, new)
    activate(output, technical.progress_path, new, approve_unmigrated=True)
    assert new.progress["decisions"][first] == technical.progress["decisions"][first]
    assert technical.progress_path.read_bytes() == before
    with pytest.raises(FileExistsError):
        activate(output, technical.progress_path, new, approve_unmigrated=True)


@pytest.mark.parametrize("mode", ["display", "support"])
def test_migration_checks_more_than_matching_input_offsets(technical, tmp_path, mode):
    from tools.evaluation.pilot_migration import propose

    first = technical.cards[0]["items"][0]["item_id"]
    technical.update(first, correspondence="yes", boundaries="yes")
    new = migration_destination(
        technical, tmp_path, changed_display=mode == "display", changed_support=mode == "support"
    )
    report = propose(technical, new, tmp_path / "migration")
    assert report["migrated_items"] == []
    assert report["unmigrated"][0]["item_id"] == first
    assert (
        report["unmigrated"][0]["reason"] == "input_display_or_complete_supporting_evidence_changed"
    )


def test_migration_rejects_concurrent_old_review_edits(technical, tmp_path):
    from tools.evaluation.pilot_migration import activate, propose

    first = technical.cards[0]["items"][0]["item_id"]
    technical.update(first, correspondence="yes", boundaries="yes")
    new = migration_destination(technical, tmp_path)
    output = tmp_path / "migration"
    propose(technical, new, output)
    technical.update(first, notes="A later real edit")
    with pytest.raises(ValueError, match="changed"):
        activate(output, technical.progress_path, new)
    assert not new.progress_path.exists()


def test_metrics_keep_four_groups_separate(technical):
    # Add a commentary fixture without inferring quotation intent or expected recall.
    cases = [*technical.cases, {**technical.cases[-1], "case_id": "C0001", "group": "commentary"}]
    rows = [
        json.loads(line)
        for line in (technical.run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    rows.extend(
        {"case_id": "C0001", "config": config, "detections": []}
        for config in pipeline.CONFIGURATIONS
    )
    (technical.run_dir / "evidence.jsonl").write_bytes(b"".join(canonical(r) for r in rows))
    technical.cases = cases
    result = metrics(technical)
    groups = result["configurations"][pipeline.DEFAULT]["groups"]
    assert set(groups) == {"exact", "fuzzy", "natural", "commentary"}
    assert groups["natural"]["inputs"] == 1
    assert groups["commentary"]["inputs"] == 1
    assert groups["commentary"]["descriptive_alerts"]["paragraphs"] == 1
    assert "controlled_recovery" not in groups["commentary"]
    assert result["reviewed_error_scores"] == "withheld_until_maintainer_review"
