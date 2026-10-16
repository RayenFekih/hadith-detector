"""Capture complete detection evidence, deduplicate review spans and prepare alerts."""

import json
import platform
import shutil
import tempfile
import unicodedata
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

from tools.evaluation.dataset import load, read
from tools.evaluation.review import EDITABLE, decode_csv, encode_csv, rows_for_case, validate_review
from tools.exact_benchmark.corpus import canonical, digest

CONFIGURATIONS = {
    "m3-e0-o0": (3, 0, 0),
    "m5-e0-o0": (5, 0, 0),
    "m7-e0-o0": (7, 0, 0),
    "m5-e1-o0": (5, 1, 0),
    "m5-e0-o1": (5, 0, 1),
    "m5-e1-o1": (5, 1, 1),
}
DEFAULT = "m5-e0-o0"
ROOT = Path(__file__).resolve().parents[2]


def fingerprint():
    paths = [
        ROOT / "uv.lock",
        *sorted((ROOT / "src/hadith_detector").glob("*.py")),
        *sorted(Path(__file__).parent.glob("*.py")),
        *sorted(Path(__file__).parent.glob("*.json")),
    ]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def validate_results(case, results, records, keys):
    cursor = 0
    for result in results:
        if not cursor <= result.start < result.end <= len(case["text"]):
            raise ValueError("Invalid selected detection offsets")
        if case["text"][result.start : result.end] != result.text:
            raise ValueError("Detection substring mismatch")
        cursor = result.end
        for reference in result.references:
            source = records[keys[reference.record.hadith_key]]
            if source["text"] != reference.record.text:
                raise ValueError("Reference text changed")
            for occurrence in reference.occurrences:
                if source["text"][occurrence.start : occurrence.end] != occurrence.text:
                    raise ValueError("Occurrence substring mismatch")


def publish_review(cases, predictions, keys, output):
    rows = []
    alerts = []
    totals = defaultdict(Counter)
    affected = defaultdict(set)
    for case in cases:
        by_config = predictions(case)
        rows.extend(rows_for_case(case, by_config, keys))
        for config, results in by_config.items():
            totals[case["group"]][config] += len(results)
            if case["proposed_case_label"] == "quotation_free":
                for result in results:
                    affected[case["group"], config].add(case["case_id"])
                    alerts.append(
                        {
                            "status": "candidate_unwanted_alert_not_confirmed_false_positive",
                            "group": case["group"],
                            "case_id": case["case_id"],
                            "config": config,
                            "start": result.start,
                            "end": result.end,
                            "text": case["text"][result.start : result.end],
                            "supporting_references": [
                                r.record.hadith_key for r in result.references
                            ],
                        }
                    )
    unions = []
    by_id = {c["case_id"]: c for c in cases}
    for row in rows:
        if row["row_kind"] != "span":
            continue
        references = row["supporting_references"].split(";") if row["supporting_references"] else []
        unions.append(
            {"reference_union_id": row["proposal_id"], "supporting_references": references}
        )
        row["reference_union_id"] = row["proposal_id"]
        row["supporting_reference_count"] = str(len(references))
        preview = references[:50]
        known = by_id[row["case_id"]]["source"].get("hadith_key")
        if known in references and known not in preview:
            preview = [known, *preview[:49]]
        row["supporting_references"] = ";".join(preview)
        row["reference_preview_note"] = (
            f"Showing {len(preview)} of {len(references)} identities; "
            "complete union in reference-unions.jsonl"
            if len(preview) < len(references)
            else "All identities shown; occurrences in evidence.jsonl"
        )
    validate_review(rows, cases, keys, CONFIGURATIONS)
    payload = encode_csv(rows)
    restored = decode_csv(payload)
    if restored != rows:
        raise ValueError("CSV round trip changed a review value")
    (output / "review.csv").write_bytes(payload)
    (output / "reference-unions.jsonl").write_bytes(b"".join(canonical(u) for u in unions))
    (output / "candidate-alerts.jsonl").write_bytes(b"".join(canonical(a) for a in alerts))
    groups = {}
    for group in ("corpus_derived", "natural_text"):
        groups[group] = {}
        for config in CONFIGURATIONS:
            selected = [a for a in alerts if a["group"] == group and a["config"] == config]
            base = [a for a in alerts if a["group"] == group and a["config"] == DEFAULT]
            here = {(a["case_id"], a["start"], a["end"]) for a in selected}
            baseline = {(a["case_id"], a["start"], a["end"]) for a in base}
            groups[group][config] = {
                "all_detections": totals[group][config],
                "delta_detections_vs_default": totals[group][config] - totals[group][DEFAULT],
                "proposed_quotation_free_paragraphs": sum(
                    c["group"] == group and c["proposed_case_label"] == "quotation_free"
                    for c in cases
                ),
                "affected_paragraphs": sorted(affected[group, config]),
                "affected_paragraph_count": len(affected[group, config]),
                "candidate_unwanted_detections": len(selected),
                "delta_unwanted_detections_vs_default": len(selected) - len(base),
                "new_candidate_spans_vs_default": sorted(here - baseline),
                "removed_candidate_spans_vs_default": sorted(baseline - here),
            }
    summary = {
        "status": "unreviewed_preparation_counts_only",
        "gold_approved": False,
        "default_config": DEFAULT,
        "groups": groups,
        "review_rows": len(rows),
        "case_rows": len(cases),
        "span_rows": len(rows) - len(cases),
        "decisions": {"pending": len(rows)},
    }
    (output / "preparation-summary.json").write_bytes(canonical(summary))
    return summary


def run(dataset: Path, index: Path, output: Path):
    from hadith_detector import HadithDetector

    if output.exists():
        raise FileExistsError(output)
    cases, manifest = load(dataset)
    detector = HadithDetector(index)
    keys = detector._resources.keys
    for case in cases:
        if case["group"] == "corpus_derived":
            source = case["source"]
            if detector.get_hadith(source["hadith_key"]).text != source["text"]:
                raise ValueError("Legacy source differs from pinned runtime corpus")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".evaluation-", dir=output.parent)).resolve()
    try:
        with (temporary / "evidence.jsonl").open("wb") as evidence:

            def predictions(case):
                found = {}
                for name, (minimum, errors, missing) in CONFIGURATIONS.items():
                    results = detector.detect(
                        case["text"],
                        min_match_words=minimum,
                        max_errors=errors,
                        max_missing_words=missing,
                    )
                    validate_results(case, results, detector._resources.records, keys)
                    evidence.write(
                        canonical(
                            {
                                "case_id": case["case_id"],
                                "config": name,
                                "detections": [r.to_dict() for r in results],
                            }
                        )
                    )
                    found[name] = results
                print(f"Prepared {case['case_id']} ({case['group']})", flush=True)
                return found

            summary = publish_review(cases, predictions, keys, temporary)
        (temporary / "reference-ids.json").write_bytes(canonical(keys))
        artifacts = {p.name: digest(p) for p in sorted(temporary.iterdir())}
        record = {
            "version": 1,
            "status": "awaiting_human_review",
            "gold_approved": False,
            "dataset_manifest_sha256": digest(dataset / "manifest.json"),
            "dataset_cases_sha256": manifest["cases_sha256"],
            "index_manifest_sha256": digest(index / "manifest.json"),
            "configurations": CONFIGURATIONS,
            "default_config": DEFAULT,
            "code_and_lock": fingerprint(),
            "environment": {
                "python": platform.python_version(),
                "unicode": unicodedata.unidata_version,
                "rapidfuzz": version("rapidfuzz"),
                "marisa-trie": version("marisa-trie"),
            },
            "artifacts": artifacts,
            "comparison_is_not_quality_scoring": True,
        }
        (temporary / "manifest.json").write_bytes(canonical(record))
        temporary.rename(output)
        return summary
    finally:
        if temporary.exists():
            if temporary.parent != output.parent.resolve() or not temporary.name.startswith(
                ".evaluation-"
            ):
                raise ValueError("Unexpected staging path; refusing cleanup")
            shutil.rmtree(temporary)


def verify_run(path):
    manifest = read(path / "manifest.json")
    if manifest["configurations"] != {k: list(v) for k, v in CONFIGURATIONS.items()}:
        raise ValueError("Preparation configurations differ")
    if manifest["default_config"] != DEFAULT or manifest["gold_approved"] is not False:
        raise ValueError("Unexpected baseline or approval status")
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name or digest(path / name) != expected:
            raise ValueError(f"Preparation artifact checksum mismatch: {name}")
    return manifest


def replay(dataset: Path, run_dir: Path, output: Path, *, refresh_review=False):
    """Reproduce CSV/alerts/counts from saved results, without detecting again."""
    manifest = verify_run(run_dir)
    cases, _ = load(dataset)
    if digest(dataset / "manifest.json") != manifest["dataset_manifest_sha256"]:
        raise ValueError("Dataset manifest differs")
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    keys = read(run_dir / "reference-ids.json")
    with (run_dir / "evidence.jsonl").open(encoding="utf-8") as stream:

        def predictions(case):
            found = {}
            for config in CONFIGURATIONS:
                line = json.loads(next(stream))
                if (line["case_id"], line["config"]) != (case["case_id"], config):
                    raise ValueError("Evidence order/configuration differs")
                found[config] = [
                    SimpleNamespace(
                        start=d["start"],
                        end=d["end"],
                        errors=d["errors"],
                        missing_words=d["missing_words"],
                        references=[
                            SimpleNamespace(
                                record=SimpleNamespace(hadith_key=r["record"]["hadith_key"])
                            )
                            for r in d["references"]
                        ],
                    )
                    for d in line["detections"]
                ]
            return found

        publish_review(cases, predictions, keys, output)
        if next(stream, None) is not None:
            raise ValueError("Extra evidence rows")
    names = (
        "review.csv",
        "reference-unions.jsonl",
        "candidate-alerts.jsonl",
        "preparation-summary.json",
    )
    if refresh_review:
        for name in ("evidence.jsonl", "reference-ids.json"):
            shutil.copyfile(run_dir / name, output / name)
        record = {
            **manifest,
            "capture_manifest_sha256": digest(run_dir / "manifest.json"),
            "capture_code_and_lock": manifest["code_and_lock"],
            "code_and_lock": fingerprint(),
            "detector_calls_during_review_export": 0,
            "artifacts": {p.name: digest(p) for p in sorted(output.iterdir())},
        }
        (output / "manifest.json").write_bytes(canonical(record))
    else:
        for name in names:
            if digest(output / name) != manifest["artifacts"][name]:
                raise ValueError(f"Deterministic replay differs: {name}")
    return {"reproduced": True, "detector_calls": 0}


def check_review(dataset: Path, run_dir: Path, reviewed: Path):
    manifest = verify_run(run_dir)
    if digest(dataset / "manifest.json") != manifest["dataset_manifest_sha256"]:
        raise ValueError("Review dataset differs from captured run")
    cases, _ = load(dataset)
    keys = read(run_dir / "reference-ids.json")
    original = {r["proposal_id"]: r for r in decode_csv((run_dir / "review.csv").read_bytes())}
    rows = decode_csv(reviewed.read_bytes())
    for row in rows:
        baseline = original.get(row["proposal_id"])
        if baseline:
            if any(row[k] != baseline[k] for k in baseline if k not in EDITABLE):
                raise ValueError("Exported proposal changed; use correction columns")
        elif (
            row["row_kind"] != "span"
            or not row["proposal_id"].startswith(f"manual:{row['case_id']}:")
            or not row["corrected_intent"]
        ):
            raise ValueError("New rows need manual:CASE: identities and corrected intent")
    if not original.keys() <= {r["proposal_id"] for r in rows}:
        raise ValueError("Review rows removed; reject or mark uncertain instead")
    return validate_review(rows, cases, keys, CONFIGURATIONS)
