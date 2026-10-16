"""Review UI contracts, using the existing synthetic evaluation fixture."""

import copy
import html
import json
import os

import pytest

from tools.evaluation import pipeline
from tools.evaluation.review import EDITABLE, decode_csv
from tools.evaluation.review_notebook import EvidenceBrowser, ReviewSession, highlighted

from .test_evaluation_preparation import prepared as prepared_fixture

prepared = prepared_fixture


@pytest.fixture
def session(prepared, tmp_path):  # noqa: F811
    dataset, index, _, _ = prepared
    run = tmp_path / "run"
    pipeline.run(dataset, index, run)
    return ReviewSession(dataset, run, tmp_path / "reviewed.csv")


def test_decisions_resume_and_originals_unchanged(session):
    original_bytes = (session.run_dir / "review.csv").read_bytes()
    identities = [r["proposal_id"] for r in session.rows]
    for identity, decision in zip(
        identities, ["accept", "correct", "reject", "uncertain"], strict=False
    ):
        session.jump(identity)
        correction = {}
        if decision == "correct":
            correction = dict(
                corrected_intent="intended_quotation",
                corrected_start="0",
                corrected_end="3",
                corrected_references="fixture:1",
            )
        session.update(decision=decision, reviewer_notes="Human note", **correction)
    restored = ReviewSession(session.dataset_dir, session.run_dir, session.progress_path)
    assert restored.rows == session.rows
    assert restored.progress == (4, len(session.rows))
    assert restored.current == next(
        (r["proposal_id"] for r in restored.rows if not r["decision"]),
        restored.rows[0]["proposal_id"],
    )
    assert (session.run_dir / "review.csv").read_bytes() == original_bytes
    for row, baseline in zip(session.rows, session.original, strict=True):
        assert all(row[k] == baseline[k] for k in row if k not in EDITABLE)
    result = pipeline.check_review(session.dataset_dir, session.run_dir, session.progress_path)
    assert result["gold_approved"] is False


def test_filters_navigation_manual_and_check_review(session):
    session.move(kind="span")
    assert session.row["row_kind"] == "span"
    session.jump("N0002")
    assert session.row["case_id"] == "N0002"
    row = session.add_span("N0002", 0, 3, "intended_quotation", "fixture:1", "missed")
    assert row["proposal_id"].startswith("manual:N0002:")
    assert row["corrected_start"] == "0"
    assert row["input_text"][:3] == "=1+"
    assert session.visible(status="correct") == [row]
    assert len(session.visible(status="all")) == len(session.original) + 1
    restored = ReviewSession(session.dataset_dir, session.run_dir, session.progress_path)
    assert restored.rows[-1] == row
    assert pipeline.check_review(session.dataset_dir, session.run_dir, session.progress_path)[
        "rows"
    ] == len(session.rows)
    with pytest.raises(ValueError, match="Unknown case"):
        session.jump("nonexistent")


def test_atomic_failure_and_external_edits(session, monkeypatch):
    session.save()
    saved = session.progress_path.read_bytes()
    rows = copy.deepcopy(session.rows)

    def interrupted(*args):
        raise OSError("interrupted replacement")

    with monkeypatch.context() as context:
        context.setattr(os, "replace", interrupted)
        with pytest.raises(OSError):
            session.update(decision="accept")
    assert session.progress_path.read_bytes() == saved
    assert session.rows == rows
    assert not list(session.progress_path.parent.glob(".phase6-*.tmp"))
    session.progress_path.write_bytes(saved + b"\r\n")
    with pytest.raises(ValueError, match="changed externally"):
        session.save()


def test_validation_and_original_path_protection(session):
    with pytest.raises(ValueError, match="overwrite"):
        ReviewSession(session.dataset_dir, session.run_dir, session.run_dir / "review.csv")
    with pytest.raises(ValueError, match="Immutable"):
        bad = copy.deepcopy(session.rows)
        bad[0]["source_url"] = "changed"
        session.save(bad)
    with pytest.raises(ValueError, match="Unknown reference"):
        session.add_span("N0001", 0, 2, "uncertain", "unknown")
    with pytest.raises(ValueError, match="correction"):
        session.update(decision="correct")
    assert not session.progress_path.exists()


def test_arabic_highlights_and_safe_html():
    text = '😀 قَالَ <script>alert("x")</script>\r\n و\u200f'
    a, b = text.index("ق"), text.index(" <")
    output = highlighted(text, a, b)
    assert f'color:#171717">{html.escape(text[a:b])}</mark>' in output
    assert "<script>" not in output and "&lt;script&gt;" in output
    assert text[a:b] == "قَالَ"
    assert "\r\n" in output and 'dir="rtl"' in output and "😀" in output
    with pytest.raises(ValueError):
        highlighted(text, 0, len(text) + 1)


def test_lazy_complete_evidence(session):
    browser = EvidenceBrowser(session)
    assert not browser.cache
    match = browser.get("N0001", "m5-e0-o0")[0]
    assert len(match["references"]) == 2
    assert len(match["references"][0]["occurrences"]) == 2
    for config in pipeline.CONFIGURATIONS:
        browser.get("N0001", config)
    assert len(browser.cache) == 2


def test_widgets_save_filter_jump_and_manual(session):
    pytest.importorskip("ipywidgets")
    from tools.evaluation.review_widgets import ReviewWidget

    ui = ReviewWidget(session)
    assert "0 /" in ui.heading.value
    ui.decision.value = "accept"
    ui.save_next()
    assert session.progress[0] == 1
    assert session.current != session.rows[0]["proposal_id"]
    ui.previous()
    assert ui.decision.value == "accept"
    ui.jump_id.value = "N0002"
    ui.jump()
    assert session.row["case_id"] == "N0002"
    ui.status.value = "pending"
    ui.kind.value = "span"
    assert session.row["row_kind"] == "span"
    ui.evidence_panel.selected_index = 0
    assert ui.ref_detail.value
    assert "Complete source narration" in ui.ref_detail.value
    ui.decision.value = "correct"
    ui.classification.value = "intended_quotation"
    ui.start.value, ui.end.value = "0", "3"
    ui.save_current()
    assert "2 /" in ui.heading.value
    ui.manual_start.value, ui.manual_end.value = 0, 2
    ui.manual_notes.value = "Missed quotation test"
    ui.add_manual()
    assert session.row["proposal_id"].startswith("manual:")
    assert "<mark " in ui.paragraph.value
    assert decode_csv(session.progress_path.read_bytes()) == session.rows
    assert (
        pipeline.check_review(session.dataset_dir, session.run_dir, session.progress_path)[
            "gold_approved"
        ]
        is False
    )


def test_research_notebook_keeps_legacy_interface():
    from pathlib import Path

    notebook = json.loads(
        Path("notebooks/phase6_research_review.ipynb").read_text(encoding="utf-8")
    )
    code = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert len(code) == 2
    assert "phase6-reviewed.csv" in "".join(code[0]["source"])
    assert "create_review_ui" in "".join(code[1]["source"])


def test_simple_review_layout_and_plain_language(session):
    pytest.importorskip("ipywidgets")
    from tools.evaluation.review_widgets import CLASSIFICATIONS, ReviewWidget

    ui = ReviewWidget(session)
    main = ui.widget.children
    assert main.index(ui.paragraph) < main.index(ui.description) < main.index(ui.question)
    assert main.index(ui.decision) < main.index(ui.save_next_button) < main.index(ui.advanced)
    assert main[main.index(ui.notes) + 1] is ui.save_next_button
    assert ui.question.value == "<h3>Is this proposed classification correct?</h3>"
    assert ui.decision.options == (
        ("Accept", "accept"),
        ("Correct", "correct"),
        ("Reject", "reject"),
        ("Uncertain", "uncertain"),
    )
    assert ui.decision.value is None  # Never preselect acceptance.
    assert "Whole-paragraph review" in ui.heading.value
    assert "No intended Hadith quotation" in ui.description.value
    assert "N0001" not in ui.heading.value
    assert "quotation_free" not in ui.description.value
    assert ui.advanced.selected_index is None
    assert ui.evidence_panel not in main and ui.config_details not in main
    assert ui.evidence_panel in ui.advanced.children[0].children
    assert ui.config_details in ui.advanced.children[0].children
    assert ui.navigation.selected_index is None
    assert ui.notes.layout.display == "none"
    assert "Three examples" in ui.help.children[0].value
    assert "Not intended" in ui.decision_help.value
    assert "unusable proposal" in ui.decision_help.value
    assert CLASSIFICATIONS.keys() >= {
        "intended_quotation",
        "not_intended_quotation",
        "quranic_wording",
        "uncertain",
        "contains_quotation",
        "quotation_free",
        "incidental_chain",
        "out_of_corpus",
    }

    session.move(kind="span")
    ui.render()
    assert "Highlighted-passage review" in ui.heading.value
    assert "<mark " in ui.paragraph.value
    assert "Not intended" in ui.description.value
    assert ui.boundary_details.selected_index is None
    ui.decision.value = "correct"
    assert ui.correction.layout.display == ""
    assert ui.notes.layout.display == ""
    assert ("Not intended", "not_intended_quotation") in ui.classification.options
    ui.classification.value = "not_intended_quotation"
    ui.save_current()
    assert session.row["decision"] == "correct"
    assert session.row["corrected_intent"] == "not_intended_quotation"
    assert session.row["proposed_intent"] == session.baseline[session.current]["proposed_intent"]
    assert (
        pipeline.check_review(session.dataset_dir, session.run_dir, session.progress_path)[
            "gold_approved"
        ]
        is False
    )


def test_advanced_details_reset_without_losing_saved_decisions(session):
    pytest.importorskip("ipywidgets")
    from tools.evaluation.review_widgets import ReviewWidget

    ui = ReviewWidget(session)
    ui.decision.value = "uncertain"
    assert ui.notes.layout.display == ""
    ui.notes.value = "Intent is unclear"
    ui.save_current()
    ui.advanced.selected_index = 0
    ui.config_details.selected_index = 0
    ui.save_next()
    assert ui.advanced.selected_index is None
    assert ui.config_details.selected_index is None
    restored = ReviewSession(session.dataset_dir, session.run_dir, session.progress_path)
    assert restored.rows[0]["decision"] == "uncertain"
    assert restored.rows[0]["reviewer_notes"] == "Intent is unclear"
