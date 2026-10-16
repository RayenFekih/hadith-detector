"""Finalize an explicitly authorized technical review without running the detector."""

import argparse
import hashlib
import json
import platform
import unicodedata
from collections import Counter
from datetime import date
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from rapidfuzz.distance import Levenshtein

from hadith_detector import Detection
from hadith_detector._text import Token, tokenize
from tools.exact_benchmark.corpus import canonical, digest, sequence

from .dataset import load, read
from .pilot import exact_case, fuzzy_case, publish
from .pilot_review import PilotSession, assemble, metrics
from .pipeline import CONFIGURATIONS, DEFAULT, fingerprint

GROUPS = ("exact", "fuzzy", "natural", "commentary")


def reviewed_results(session):
    """No blank answer or unacknowledged screen is silently approved."""
    session.validate(session.progress)
    incomplete = [c["case_id"] for c in session.cards if not session.complete(c)]
    if incomplete:
        raise ValueError("Incomplete review inputs: " + ";".join(incomplete))
    groups = {}
    for group in GROUPS:
        answers = [
            session.progress["decisions"][identity]
            for identity, (case_id, _) in session.items.items()
            if session.by_case[case_id]["group"] == group
        ]
        correspondence = Counter(a["correspondence"] for a in answers)
        boundaries = Counter(a["boundaries"] for a in answers)
        groups[group] = {
            "inputs": sum(c["group"] == group for c in session.cases),
            "pairs": len(answers),
            "correspondence": {k: correspondence[k] for k in ("yes", "no", "uncertain")},
            "boundaries": {k: boundaries[k] for k in ("yes", "correct", "uncertain")},
            "uncertain_pairs": sum(
                a["correspondence"] == "uncertain" or a["boundaries"] == "uncertain"
                for a in answers
            ),
            "correspondence_errors": {
                "numerator": correspondence["no"],
                "denominator": correspondence["yes"] + correspondence["no"],
            },
            "boundary_issues": {
                "numerator": boundaries["correct"],
                "denominator": boundaries["yes"] + boundaries["correct"],
            },
        }
    answers = list(session.progress["decisions"].values())
    return {
        "complete_inputs": len(session.cards),
        "pairs": len(answers),
        "judgments": 2 * len(answers),
        "pending": 0,
        "correspondence_yes": sum(a["correspondence"] == "yes" for a in answers),
        "boundary_yes": sum(a["boundaries"] == "yes" for a in answers),
        "unresolved_pairs": sum(
            a["correspondence"] == "uncertain" or a["boundaries"] == "uncertain" for a in answers
        ),
        "zero_alert_acknowledgements": len(session.progress["acknowledged_cases"]),
        "groups": groups,
        "scope": "displayed_pairs_only_not_every_reference_or_quotation_intent",
    }


def prepared_sources(path):
    """Reuse checksum-pinned mapped tokens, without retokenizing the entire corpus."""
    manifest = read(path / "manifest.json")
    if manifest["versions"] != {"manifest": 1, "records": 1, "tokens": 1, "normalization": 1}:
        raise ValueError("Incompatible prepared source versions")
    for name in ("records.jsonl", "tokens.jsonl"):
        if digest(path / name) != manifest["artifacts"][name]:
            raise ValueError("Prepared source checksum mismatch: " + name)
    rows = [json.loads(line) for line in (path / "records.jsonl").open(encoding="utf-8")]
    records = {r["hadith_key"]: r for r in rows}
    if len(records) != len(rows):
        raise ValueError("Duplicate source identity")
    vocabulary, sequences = {}, {}
    with (path / "tokens.jsonl").open(encoding="utf-8") as stream:
        for rid, line in enumerate(stream):
            row = json.loads(line)
            key = row["hadith_key"]
            if rid >= len(rows) or key != rows[rid]["hadith_key"]:
                raise ValueError("Pinned record/token identity mismatch")
            sequences[key] = sequence(tuple(Token(**t) for t in row["tokens"]), vocabulary, True)
    if set(records) != set(sequences):
        raise ValueError("Incomplete source token records")
    return records, sequences, {v: k for k, v in vocabulary.items()}


@lru_cache(maxsize=100_000)
def word_distance(a, b):
    return Levenshtein.distance(a, b, weights=(1, 1, 1), processor=None)


def validate_detection(case, config, detection, records, sequences, words):
    """Validate given traces and original slices; do not retrieve or search alignments."""
    Detection.from_dict(detection)
    minimum, errors, missing = CONFIGURATIONS[config]
    text = case["text"]
    query = tokenize(text).tokens
    a, b = detection["start"], detection["end"]
    if not 0 <= a < b <= len(text) or text[a:b] != detection["text"]:
        raise ValueError("Detection input offset/slice mismatch")
    if detection["matched_words"] < minimum or not detection["references"]:
        raise ValueError("Missing reference or below-minimum detection")
    costs, identities, occurrence_count, word_count = [], set(), 0, 0
    for reference in detection["references"]:
        record = reference["record"]
        key = record["hadith_key"]
        if key in identities or key not in records or record != records[key]:
            raise ValueError("Reference identity or original source metadata mismatch")
        identities.add(key)
        source = sequences[key]
        previous_span = None
        if not reference["occurrences"]:
            raise ValueError("Reference has no supporting occurrence")
        for occurrence in reference["occurrences"]:
            sa, sb = occurrence["start"], occurrence["end"]
            span = sa, sb
            if previous_span is not None and span <= previous_span:
                raise ValueError("Duplicated or unordered source occurrence")
            previous_span = span
            if (
                not 0 <= sa < sb <= len(record["text"])
                or record["text"][sa:sb] != occurrence["text"]
            ):
                raise ValueError("Original source offset/slice mismatch")
            trace = occurrence["alignment"]
            if len(trace) != detection["matched_words"] or not trace:
                raise ValueError("Incomplete aligned-word trace")
            qi = [w["input_token"] for w in trace]
            si = [w["source_token"] for w in trace]
            if qi != list(range(qi[0], qi[-1] + 1)) or si != sorted(set(si)):
                raise ValueError("Input skips or source order violation")
            if not 0 <= qi[0] <= qi[-1] < len(query) or not 0 <= si[0] <= si[-1] < len(source):
                raise ValueError("Trace token outside original text")
            if (query[qi[0]].start, query[qi[-1]].end) != (a, b) or (
                int(source.starts[si[0]]),
                int(source.ends[si[-1]]),
            ) != span:
                raise ValueError("Trace endpoints disagree with original spans")
            if query[qi[0]].segment != query[qi[-1]].segment or not source.window(
                si[0], si[-1] - si[0] + 1
            ):
                raise ValueError("Trace crosses matching barrier")
            from .pilot import boundary

            if (
                not boundary(query, qi[0])
                or not boundary(query, qi[-1] + 1)
                or not source.boundary(si[0])
                or not source.boundary(si[-1] + 1)
            ):
                raise ValueError("Partial symbol endpoint")
            for word in trace:
                q, s = query[word["input_token"]], word["source_token"]
                if (word["input_start"], word["input_end"]) != (q.start, q.end) or (
                    word["source_start"],
                    word["source_end"],
                ) != (int(source.starts[s]), int(source.ends[s])):
                    raise ValueError("Aligned word offset mismatch")
                if word_distance(q.term, words[int(source.terms[s])]) != word["errors"]:
                    raise ValueError("Recorded character edit cost mismatch")
            omitted = occurrence["omitted_source_tokens"]
            expected = sorted(set(range(si[0], si[-1] + 1)) - set(si))
            if [o["source_token"] for o in omitted] != expected:
                raise ValueError("Omitted source words do not agree with alignment")
            for item in omitted:
                s = item["source_token"]
                start, end = int(source.starts[s]), int(source.ends[s])
                if (item["start"], item["end"], item["text"], item["term"]) != (
                    start,
                    end,
                    record["text"][start:end],
                    words[int(source.terms[s])],
                ):
                    raise ValueError("Omitted original word slice mismatch")
            cost = sum(w["errors"] for w in trace), len(omitted)
            if (
                cost != (occurrence["errors"], occurrence["missing_words"])
                or cost[0] > errors
                or cost[1] > missing
            ):
                raise ValueError("Trace costs or configured budgets disagree")
            costs.append(cost)
            occurrence_count += 1
            word_count += len(trace)
    if min(costs) != (detection["errors"], detection["missing_words"]):
        raise ValueError("Best supporting passage cost mismatch")
    return {
        "references": len(identities),
        "occurrences": occurrence_count,
        "aligned_words": word_count,
    }


def validate_parents(session, dataset, fuzzy_dir, index, prepared, selection_lock):
    parents = session.input_manifest["parents"]
    if (
        digest(dataset / "manifest.json") != parents["dataset_manifest"]
        or digest(fuzzy_dir / "queries.json") != parents["fuzzy_queries"]
        or digest(index / "manifest.json") != parents["index_manifest"]
    ):
        raise ValueError("Frozen evaluation parent fingerprint differs")
    index_manifest = read(index / "manifest.json")
    if (
        digest(prepared / "manifest.json") != index_manifest["prepared_manifest_sha256"]
        or digest(index / "records.jsonl") != parents["source_records"]
    ):
        raise ValueError("Pinned corpus/source fingerprint differs")
    lock = read(selection_lock)
    if (
        lock["composition"] != "55"
        or lock["selection_manifest_sha256"] != session.identity["inputs_manifest_sha256"]
        or lock["cases_sha256"] != digest(session.inputs / "cases.jsonl")
        or lock["selection_sha256"] != digest(session.inputs / "selection.json")
    ):
        raise ValueError("Committed selection lock differs from frozen inputs")
    if [c["case_id"] for c in lock["cases"]] != [c["case_id"] for c in session.cases]:
        raise ValueError("Selected identities changed")
    expected_groups = {"exact": 10, "fuzzy": 10, "natural": 15, "commentary": 20}
    if Counter(c["group"] for c in session.cases) != expected_groups:
        raise ValueError("Final pilot composition is not 10/10/15/20")
    original, _ = load(dataset)
    original = {c["case_id"]: c for c in original}
    queries = {q["id"]: q for q in read(fuzzy_dir / "queries.json")["queries"]}
    records, sequences, words = prepared_sources(prepared)
    for case, frozen in zip(session.cases, lock["cases"], strict=True):
        if hashlib.sha256(case["text"].encode()).hexdigest() != frozen["input_sha256"]:
            raise ValueError("Frozen input text differs from selection")
        if case["group"] == "exact":
            if exact_case(original[case["parent_id"]], records) != case:
                raise ValueError("Exact source target differs from input-only construction")
        elif case["group"] == "fuzzy":
            if fuzzy_case(queries[case["parent_id"]], records) != case:
                raise ValueError("Fuzzy target differs from frozen mutation construction")
        else:
            source = original[case["parent_id"]]
            if (
                case["text"] != source["text"]
                or case["provenance"]["source"] != source["source"]
                or case["target"] is not None
            ):
                raise ValueError("Original prose or commentary changed")
    return records, sequences, words


def inspect_evidence(session, records, sequences, words):
    counts = Counter()
    source_keys = set()
    diagnostics = {
        name: {
            "no_detections": [],
            "partial_input_only": [],
            "full_input_other_origin": [],
            "full_input_supported": [],
        }
        for name in CONFIGURATIONS
    }
    max_references = {"count": 0}
    with (session.run_dir / "evidence.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            case, config = session.by_case[row["case_id"]], row["config"]
            counts["case_configuration_outputs"] += 1
            previous = 0
            for detection in row["detections"]:
                if detection["start"] < previous:
                    raise ValueError("Selected detections overlap or are unordered")
                previous = detection["end"]
                stats = validate_detection(case, config, detection, records, sequences, words)
                counts.update(stats)
                counts["detections"] += 1
                source_keys.update(r["record"]["hadith_key"] for r in detection["references"])
                if len(detection["references"]) > max_references["count"]:
                    max_references = {
                        "count": len(detection["references"]),
                        "case_id": case["case_id"],
                        "config": config,
                        "start": detection["start"],
                        "end": detection["end"],
                    }
            target = case["target"]
            if target:
                full = [
                    d
                    for d in row["detections"]
                    if d["start"] <= target["input_start"] and d["end"] >= target["input_end"]
                ]
                status = diagnostics[config]
                if not row["detections"]:
                    status["no_detections"].append(case["case_id"])
                elif not full:
                    status["partial_input_only"].append(case["case_id"])
                else:
                    status["full_input_supported"].append(case["case_id"])
                    if not any(
                        r["record"]["hadith_key"] == target["record"]["hadith_key"]
                        for d in full
                        for r in d["references"]
                    ):
                        status["full_input_other_origin"].append(case["case_id"])
    for status in diagnostics.values():
        for identities in status.values():
            identities.sort()
    return {
        "counts": dict(counts),
        "distinct_source_identities": len(source_keys),
        "diagnostics": diagnostics,
        "maximum_references_per_detection": max_references,
        "scope": "saved_trace_integrity_not_new_candidate_search_or_oracle_evaluation",
    }


def final_result(session, inspected, *, approve_review, review_date):
    if not approve_review:
        raise ValueError("Explicit authorization to finalize reviewed results is required")
    date.fromisoformat(review_date)
    review = reviewed_results(session)
    result = metrics(session)
    if session.disk_hash() != session.saved_hash:
        raise ValueError("Human annotations changed during finalization")
    result.update(
        {
            "status": "finalized_technical_pilot",
            "review_date": review_date,
            "human_review_approved": True,
            "approval_scope": "technical_correspondence_and_boundaries_only",
            "reviewed_error_scores": review,
            "trace_validation": inspected,
            "below_seven_word_exact_inputs": [
                {"case_id": c["case_id"], "words": c["target"]["matched_words"]}
                for c in session.cases
                if c["group"] == "exact" and c["target"]["matched_words"] < 7
            ],
            "no_new_detector_calls": True,
            "historical_benchmarks_rerun": False,
        }
    )
    result["eligible_target_failures"] = {
        config: sorted(
            {
                identity
                for group in row["positives"].values()
                for identity in group["construction_eligible_ids"]
            }
            - set(row["recovered_positive_ids"])
        )
        for config, row in result["configurations"].items()
    }
    return result


def fraction(n, d):
    return f"{n}/{d}"


def render_report(result):
    review = result["reviewed_error_scores"]
    failures = sum(len(v) for v in result["eligible_target_failures"].values())
    issues = sum(
        g["correspondence_errors"]["numerator"] + g["boundary_issues"]["numerator"]
        for g in review["groups"].values()
    )
    lines = [
        "# Phase 6 evaluation results",
        "",
        f"Review date: {result['review_date']}. Final technical review; Phase 7 is not started.",
        "",
        f"All {review['judgments']} required judgments are present: "
        f"correspondence **{review['correspondence_yes']}/{review['pairs']} Yes**, "
        f"boundaries **{review['boundary_yes']}/{review['pairs']} Yes**. "
        f"All {review['zero_alert_acknowledgements']}/13 zero-alert screens are acknowledged.",
        "",
        "## Human review — displayed input/source pairs",
        "",
        "| Group | Inputs | Correspondence Yes | Boundaries Yes | Uncertain pairs |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for group, data in review["groups"].items():
        uncertain = data["uncertain_pairs"]
        lines.append(
            f"| {group} | {data['inputs']} | "
            f"{fraction(data['correspondence']['yes'], data['pairs'])} | "
            f"{fraction(data['boundaries']['yes'], data['pairs'])} | {uncertain} |"
        )
    lines += [
        f"| **Total** | 55 | {review['correspondence_yes']}/{review['pairs']} | "
        f"{review['boundary_yes']}/{review['pairs']} | {review['unresolved_pairs']} |",
        "",
        "Reported correspondence mismatches: "
        f"{sum(g['correspondence_errors']['numerator'] for g in review['groups'].values())}"
        f"/{review['pairs']}; boundary corrections: "
        f"{sum(g['boundary_issues']['numerator'] for g in review['groups'].values())}"
        f"/{review['pairs']}. "
        f"Missing judgments: {review['pending']}/{review['judgments']}.",
        "",
        "These are 191 deduplicated spans reviewed once across settings, "
        "with one displayed supporting source occurrence per span. "
        "They are not 191 independently sampled documents, an audit of "
        "every reference, or quotation-intent labels.",
        "",
        "## Automated controlled-target recovery and descriptive alerts",
        "",
        "Configuration tuples are (minimum words, character edits, source "
        "omissions). Fractions below use **all selected inputs**; "
        "eligibility is explained afterward.",
        "",
        "| Settings | Exact | Edits | Omissions | Combined | Full targets |"
        " Recovered target boundaries | General prose: paragraphs / alerts | "
        "Commentary: paragraphs / "
        "detections |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for name in CONFIGURATIONS:
        row = result["configurations"][name]
        p = row["positives"]
        values = [
            fraction(p[g]["full_origin_recovered"], p[g]["total"])
            for g in ("exact", "fuzzy:edits", "fuzzy:omissions", "fuzzy:combined")
        ]
        natural, commentary = row["natural"], row["commentary"]
        label = str(tuple(CONFIGURATIONS[name])) + (" **default**" if name == DEFAULT else "")
        lines.append(
            f"| {label} | {' | '.join(values)} | "
            f"{fraction(row['all_positive_recovery']['count'], 20)} | "
            f"{sum(g['exact_boundary_agreement'] for g in p.values())}/"
            f"{row['all_positive_recovery']['count']} | "
            f"{len(natural['affected_ids'])}/15 / {natural['detections']} | "
            f"{len(commentary['affected_ids'])}/20 / {commentary['detections']} |"
        )
    lines += [
        "",
        "Full recovery requires the complete frozen input target and its "
        "originating source identity/occurrence; a matching fragment is not"
        " success. "
        "Human boundary acceptance of a returned fragment is distinct from "
        "recovery of the complete constructed quotation.",
        "",
        "### Eligibility, incomplete recovery and differences from defaults",
        "",
    ]
    for name in CONFIGURATIONS:
        row = result["configurations"][name]
        eligible = sum(g["construction_eligible"] for g in row["positives"].values())
        recovered = sum(g["eligible_full_origin_recovered"] for g in row["positives"].values())
        diag = result["trace_validation"]["diagnostics"][name]
        diff = row["versus_default"]
        lines.append(
            f"- `{tuple(CONFIGURATIONS[name])}`: eligible recovery **{recovered}/{eligible}**; "
            f"{len(diag['partial_input_only'])}/20 inputs have only partial matches and "
            f"{len(diag['no_detections'])}/20 have no detections. "
            f"Full-target gains/losses: +{len(diff['gained_full_targets'])}"
            f"/−{len(diff['lost_full_targets'])}; "
            f"added/removed input spans: +{len(diff['added_spans'])}/−{len(diff['removed_spans'])}."
        )
    lines += [
        "",
        "The seven-word setting excludes `S0009` and `S0060`, each with five normalized words. "
        "Fuzzy targets are outside zero-error/zero-omission budgets by "
        "construction. These are expected limitations, not concealed "
        "eligible-case failures. "
        "The default returns fragments on six fuzzy inputs and nothing on "
        "four. `(5,1,1)` fully recovers all 20 positives with exact target "
        "boundaries. "
        f"Eligible full-target failures: {failures}; unresolved human-reviewed "
        f"pairs: {review['unresolved_pairs']}/{review['pairs']}. "
        "Detailed missing/partial IDs and paired "
        "common-eligibility comparisons are in the machine-readable "
        "results.",
        "",
        "General-prose alerts occur only at the three-word minimum, on two "
        "paragraphs. Religious-commentary detections are descriptive "
        "textual support: "
        "neither their presence nor human acceptance establishes intended "
        "quotation, authentication or false-positive status. "
        "Different spans added/removed across settings include boundary "
        "replacements, not just new quotations. Defaults remain unchanged.",
        "",
        "The two general-prose alerts at `(3,0,0)` are `N0040[705:716]`: "
        "**هو عبد الله**, supported by `bukhari:563`, `muslim:804`, `muslim:3366`; "
        "and `N0032[857:868]`: **كاد أن يكون**, supported by `bukhari:4757`. "
        "Both were accepted as textual correspondences. They are incidental alerts, "
        "not independently established quotation-intent false positives.",
        "",
        "Common wording can have very broad support: `N0017[496:514]`, "
        "**صلى الله عليه وسلم**, has 13,037 supporting identities at `(3,0,0)`. "
        "This is not unique attribution; references were not truncated.",
        "",
        "## Validation, provenance and existing evidence",
        "",
        "Frozen input/capture hashes, review snapshot, scoring-code "
        "fingerprints and result checksums are retained in the final "
        "artifact manifest. "
        "Selection used input-only hash ranking and included all 20 "
        "commentary paragraphs. Existing six-answer migration and excluded "
        "S0002 judgments remain archived, unchanged; excluded judgments are"
        " not scored here.",
        "",
        "The review projection was reproduced from checksummed saved "
        "outputs. Every returned reference was checked against the pinned "
        "original corpus, "
        "and all input/source offsets, mapped word traces, barriers, "
        "whole-symbol endpoints, omissions and recorded character costs "
        "were checked. "
        "These checks validate supplied evidence; they do not search for "
        "missing candidates or rerun an independent exhaustive oracle.",
        "",
        "Evidence validation covered 330 case/configuration outputs, 512 detections, "
        "66,586 reference entries and 83,206 source occurrences. This automated "
        "integrity coverage is separate from the 191 displayed pairs reviewed by a human.",
        "",
        "Independent oracle agreement, latency, memory, packaging and "
        "compatibility results are reused from "
        "[Phase 3B](phase3b-validation.md), [Phase 4B](phase4b-validation.md), "
        "[MARISA production](marisa-production.md) and [Phase 5B](phase5b-validation.md). "
        "Phase 5B records 168 exact, 168 fuzzy and 39 representative oracle"
        " cases plus Python 3.11–3.14 Windows/Linux checks. "
        "Those are automated historical evaluations, separate from this "
        "maintainer's 191-pair review; none were rerun for Phase 6 "
        "finalization.",
        "",
        "## Limitations and initial-release assessment",
        "",
        "This is a small, reused convenience sample: 10 exact, 10 "
        "controlled fuzzy (4/4/2), 15 general prose and 20 related "
        "religious-commentary paragraphs. "
        "One maintainer reviewed representative source passages. Controlled"
        " examples are artificial; natural-text gold quotation spans and "
        "independently verified intent labels do not exist. "
        "There is no deployment-wide precision/recall estimate, "
        "false-positive rate, per-reference human completeness claim or "
        "Hadith authenticity claim. "
        "No new performance claim or automatic configuration recommendation follows.",
        "",
        (
            "**Assessment:** sufficient technical evaluation for an initial "
            "release within the documented exact/fuzzy textual-matching scope, "
            if not (failures or issues or review["unresolved_pairs"])
            else "**Assessment:** review reported failures, issues or uncertainty before release, "
        )
        + "combined with the previous oracle and compatibility evidence. "
        "Phase 7 still must package the approved corpus/index and "
        "attribution, "
        "verify the actual bundled wheel/sdist and offline installations, "
        "and complete release review. No Phase 7 work, commit, push or "
        "publication is authorized by this report.",
        "",
        "## Reproducing the evaluation",
        "",
        "With the preserved local frozen inputs, evidence and review decisions, run:",
        "",
        "```sh",
        "uv run python -m tools.evaluation.finalize --approve-reviewed-results "
        f"--review-date {result['review_date']} --output-dir data/phase6-evaluation-rebuild",
        "```",
        "",
        "Use a new output directory; existing outputs are never overwritten. "
        "The command validates saved traces and scores saved results without detector calls. "
        "The output includes results.json, the review snapshot and a checksummed manifest. "
        "Determinism requires the same frozen inputs, annotations, code and recorded environment.",
        "",
    ]
    return "\n".join(lines)


def release_numbers(result):
    r = result["reviewed_error_scores"]
    return (
        "# Evaluation wording for a future README / PyPI description\n\n"
        "Prepared wording only; this does not publish a release.\n\n"
        "## README-sized text\n\n"
        f"A frozen 55-input technical pilot contained 10 exact excerpts, 10 controlled "
        f"modified excerpts (4 character-edit, 4 omission, 2 combined), 15 general Arabic "
        f"paragraphs and 20 religious-commentary paragraphs. A maintainer accepted textual "
        f"correspondence and boundaries for {r['correspondence_yes']}/{r['pairs']} displayed "
        f"input/source pairs, completing {r['judgments']} judgments. The default `(5,0,0)` "
        "recovered 10/10 exact targets; `(5,1,1)` recovered 4/4 edit, 4/4 omission and 2/2 "
        "combined targets. The default's zero fuzzy budgets did not fully recover those "
        "10 controlled modified targets. There were 0/15 general-prose paragraphs with "
        "default detections, and 58 default detections across 20/20 commentary paragraphs. "
        "Commentary detections are textual matches, not independently labelled intended "
        "quotations or false positives. These small, reused samples do not establish "
        "deployment-wide precision/recall or Hadith authenticity.\n\n"
        "## Short PyPI-sized text\n\n"
        "In a frozen 55-input technical pilot, a maintainer accepted textual correspondence "
        "and boundaries for 191/191 displayed source pairs. Defaults recovered 10/10 exact "
        "targets; enabling one character edit and one source-word omission recovered "
        "10/10 controlled modified targets. This limited pilot does not measure "
        "deployment-wide precision/recall, intended quotation or Hadith authenticity.\n"
    )


def finalize(
    session,
    *,
    dataset,
    fuzzy_dir,
    index,
    prepared,
    selection_lock,
    output,
    approve_review=False,
    review_date,
):
    if not approve_review:
        raise ValueError("Explicit authorization to finalize reviewed results is required")
    reviewed_results(session)
    records, sequences, words = validate_parents(
        session, dataset, fuzzy_dir, index, prepared, selection_lock
    )
    if (
        canonical(assemble(session.cases, session.run_dir / "evidence.jsonl"))
        != (session.run_dir / "review.json").read_bytes()
    ):
        raise ValueError("Displayed review projection differs from saved evidence")
    inspected = inspect_evidence(session, records, sequences, words)
    result = final_result(session, inspected, approve_review=True, review_date=review_date)
    review_snapshot = session.progress_path.read_bytes()
    if hashlib.sha256(review_snapshot).hexdigest() != session.saved_hash:
        raise ValueError("Annotations changed before final snapshot")
    with publish(output) as temporary:
        (temporary / "results.json").write_bytes(canonical(result))
        (temporary / "report.md").write_text(render_report(result), encoding="utf-8", newline="\n")
        (temporary / "release-evaluation.md").write_text(
            release_numbers(result), encoding="utf-8", newline="\n"
        )
        (temporary / "reviewed-progress.json").write_bytes(review_snapshot)
        (temporary / "manifest.json").write_bytes(
            canonical(
                {
                    "version": 1,
                    "kind": "final_technical_pilot_evaluation",
                    "review_date": review_date,
                    "inputs_manifest_sha256": session.identity["inputs_manifest_sha256"],
                    "capture_manifest_sha256": session.identity["capture_manifest_sha256"],
                    "review_sha256": session.saved_hash,
                    "selection_lock_sha256": digest(selection_lock),
                    "scoring_code": {
                        "finalize.py": digest(Path(__file__)),
                        "pilot_review.py": digest(Path(__file__).with_name("pilot_review.py")),
                    },
                    "code_and_lock": fingerprint(),
                    "environment": {
                        "python": platform.python_version(),
                        "unicode": unicodedata.unidata_version,
                        "rapidfuzz": version("rapidfuzz"),
                    },
                    "artifacts": {p.name: digest(p) for p in sorted(temporary.iterdir())},
                }
            )
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-dir", type=Path, default=Path("data/phase6-pilot-55-inputs"))
    parser.add_argument("--run-dir", type=Path, default=Path("data/phase6-pilot-55"))
    parser.add_argument("--progress", type=Path, default=Path("data/phase6-pilot-55-progress.json"))
    parser.add_argument("--dataset-dir", type=Path, default=Path("data/phase6-inputs"))
    parser.add_argument("--fuzzy-dir", type=Path, default=Path("data/phase4-final"))
    parser.add_argument("--index-dir", type=Path, default=Path("data/runtime-index-v2-a"))
    parser.add_argument("--prepared-dir", type=Path, default=Path("data/prepared-corpus"))
    parser.add_argument(
        "--selection-lock", type=Path, default=Path(__file__).with_name("pilot-selection.json")
    )
    parser.add_argument("--approve-reviewed-results", action="store_true")
    parser.add_argument("--review-date", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    session = PilotSession(args.inputs_dir, args.run_dir, args.progress)
    result = finalize(
        session,
        dataset=args.dataset_dir,
        fuzzy_dir=args.fuzzy_dir,
        index=args.index_dir,
        prepared=args.prepared_dir,
        selection_lock=args.selection_lock,
        output=args.output_dir,
        approve_review=args.approve_reviewed_results,
        review_date=args.review_date,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "reviewed_pairs": result["reviewed_error_scores"]["pairs"],
                "unresolved": result["reviewed_error_scores"]["unresolved_pairs"],
            }
        )
    )


if __name__ == "__main__":
    main()
