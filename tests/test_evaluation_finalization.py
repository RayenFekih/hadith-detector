"""Final scores require complete, explicitly authorized review and intact saved evidence."""

import copy

import pytest

from tools.evaluation.finalize import (
    final_result,
    prepared_sources,
    reviewed_results,
    validate_detection,
)
from tools.evaluation.pipeline import DEFAULT

from .test_evaluation_preparation import prepared as prepared_fixture
from .test_technical_pilot import technical as technical_fixture

technical = technical_fixture
prepared = prepared_fixture


def complete(session):
    for identity in session.items:
        session.update(identity, correspondence="yes", boundaries="yes")
    for card in session.cards:
        if not card["items"]:
            session.acknowledge(card["case_id"])


def test_missing_answer_or_acknowledgement_is_never_approved(technical):  # noqa: F811
    with pytest.raises(ValueError, match="Incomplete"):
        reviewed_results(technical)
    for identity in technical.items:
        technical.update(identity, correspondence="yes", boundaries="yes")
    with pytest.raises(ValueError, match="Nzero"):
        reviewed_results(technical)
    technical.acknowledge("Nzero")
    identity = next(iter(technical.items))
    technical.update(identity, boundaries="")
    with pytest.raises(ValueError, match="Incomplete"):
        reviewed_results(technical)


def test_yes_counts_and_explicit_authorization(technical):  # noqa: F811
    complete(technical)
    before = technical.progress_path.read_bytes()
    result = reviewed_results(technical)
    assert result["judgments"] == 4
    assert result["correspondence_yes"] == result["boundary_yes"] == 2
    assert result["zero_alert_acknowledgements"] == 1
    with pytest.raises(ValueError, match="authorization"):
        final_result(technical, {}, approve_review=False, review_date="2026-10-16")
    final = final_result(technical, {}, approve_review=True, review_date="2026-10-16")
    assert final["human_review_approved"] is True
    assert final["approval_scope"] == "technical_correspondence_and_boundaries_only"
    assert final["reviewed_error_scores"]["pending"] == 0
    assert final["precision_recall"] == "not_estimated"
    assert technical.progress_path.read_bytes() == before


def test_uncertain_is_retained_and_excluded_from_decisive_denominator(technical):  # noqa: F811
    complete(technical)
    first = next(iter(technical.items))
    technical.update(first, correspondence="uncertain", boundaries="uncertain")
    review = reviewed_results(technical)
    assert review["unresolved_pairs"] == 1
    exact = review["groups"]["exact"]
    assert exact["pairs"] == 2 and exact["uncertain_pairs"] == 1
    assert exact["correspondence_errors"] == {"numerator": 0, "denominator": 1}
    assert exact["boundary_issues"] == {"numerator": 0, "denominator": 1}


def test_no_and_correct_are_not_counted_as_yes(technical):  # noqa: F811
    complete(technical)
    identity = next(iter(technical.items))
    item = technical.items[identity][1]
    technical.update(
        identity,
        correspondence="no",
        boundaries="correct",
        input_start=item["start"] + 1,
        input_end=item["end"],
    )
    review = reviewed_results(technical)
    assert review["correspondence_yes"] == review["boundary_yes"] == 1
    assert review["groups"]["exact"]["correspondence_errors"] == {"numerator": 1, "denominator": 2}
    assert review["groups"]["exact"]["boundary_issues"] == {"numerator": 1, "denominator": 2}


def test_pinned_source_offsets_and_recorded_character_costs(technical):  # noqa: F811
    records, sequences, words = prepared_sources(technical.inputs.parent / "prepared")
    item = technical.cards[0]["items"][0]
    identity = next(e for e in item["evidence_ids"] if DEFAULT in e)
    detection = technical.evidence(identity)
    case = technical.cases[0]
    assert (
        validate_detection(case, DEFAULT, detection, records, sequences, words)["occurrences"] == 3
    )
    bad = copy.deepcopy(detection)
    bad["references"][1]["record"]["sunnah_url"] = "https://example.org/changed"
    with pytest.raises(ValueError, match="metadata"):
        validate_detection(case, DEFAULT, bad, records, sequences, words)
    bad = copy.deepcopy(detection)
    bad["references"][0]["occurrences"][0]["alignment"][0]["source_start"] += 1
    with pytest.raises(ValueError):
        validate_detection(case, DEFAULT, bad, records, sequences, words)
    bad = copy.deepcopy(detection)
    bad["errors"] = 1
    for ref in bad["references"]:
        for occurrence in ref["occurrences"]:
            occurrence["errors"] = 1
            occurrence["alignment"][0]["errors"] = 1
    with pytest.raises(ValueError, match="edit cost"):
        validate_detection(case, "m5-e1-o0", bad, records, sequences, words)
