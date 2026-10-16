"""Technical pilot projections, independent progress validation and limited metrics."""

import copy
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from hadith_detector import Detection
from tools.exact_benchmark.corpus import canonical, digest

from .dataset import read
from .pilot import verified
from .pipeline import CONFIGURATIONS, DEFAULT

CORRESPONDENCE = {"", "yes", "no", "uncertain"}
BOUNDARIES = {"", "yes", "correct", "uncertain"}
ANSWER_FIELDS = {
    "correspondence",
    "boundaries",
    "input_start",
    "input_end",
    "source_start",
    "source_end",
    "notes",
}


def blank_answer():
    return {
        "correspondence": "",
        "boundaries": "",
        "input_start": None,
        "input_end": None,
        "source_start": None,
        "source_end": None,
        "notes": "",
    }


def answer_complete(answer):
    return bool(
        answer["correspondence"]
        and answer["boundaries"]
        and (
            answer["boundaries"] != "correct"
            or answer["input_start"] is not None
            or answer["source_start"] is not None
        )
    )


def evidence_rows(cases, path):
    expected = {c["case_id"] for c in cases}
    output = {c: {} for c in expected}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            identity, config = row["case_id"], row["config"]
            if (
                identity not in expected
                or config not in CONFIGURATIONS
                or config in output[identity]
            ):
                raise ValueError("Unknown or duplicate pilot evidence identity")
            output[identity][config] = row["detections"]
    if any(set(row) != set(CONFIGURATIONS) for row in output.values()):
        raise ValueError("Incomplete configuration evidence")
    return output


def representative(case, entries):
    ordered = sorted(entries, key=lambda e: (e[0] != DEFAULT, list(CONFIGURATIONS).index(e[0])))
    target = case["target"]
    for config, _, detection in ordered:
        if target:
            for ref in detection["references"]:
                if ref["record"]["hadith_key"] == target["record"]["hadith_key"]:
                    occurrences = sorted(
                        ref["occurrences"],
                        key=lambda o: (
                            (o["start"], o["end"])
                            != (target["source_start"], target["source_end"]),
                            o["start"],
                            o["end"],
                        ),
                    )
                    return {
                        "config": config,
                        "record": ref["record"],
                        "occurrence": occurrences[0],
                        "selection": "known originating record; target occurrence preferred",
                    }
    config, _, detection = ordered[0]
    ref = detection["references"][0]
    occurrence = min(ref["occurrences"], key=lambda o: (o["start"], o["end"]))
    return {
        "config": config,
        "record": ref["record"],
        "occurrence": occurrence,
        "selection": "first reference in saved corpus order; earliest occurrence",
    }


def assemble(cases, evidence):
    outputs = evidence_rows(cases, evidence)
    cards = []
    for case in cases:
        spans = {}
        for config in CONFIGURATIONS:
            minimum, errors, missing = CONFIGURATIONS[config]
            last = 0
            for i, detection in enumerate(outputs[case["case_id"]][config]):
                Detection.from_dict(detection)
                a, b = detection["start"], detection["end"]
                if not last <= a < b <= len(case["text"]) or case["text"][a:b] != detection["text"]:
                    raise ValueError("Detection does not slice the original input")
                last = b
                for ref in detection["references"]:
                    for occurrence in ref["occurrences"]:
                        if occurrence["errors"] > errors or occurrence["missing_words"] > missing:
                            raise ValueError("Occurrence exceeds configuration budgets")
                if detection["matched_words"] < minimum:
                    raise ValueError("Result below configured minimum")
                spans.setdefault((a, b), []).append((config, i, detection))
        items = []
        for (a, b), entries in sorted(spans.items()):
            rep = representative(case, entries)
            items.append(
                {
                    "item_id": f"{case['case_id']}:span:{a}:{b}",
                    "kind": "detection",
                    "start": a,
                    "end": b,
                    "text": case["text"][a:b],
                    "configurations": [e[0] for e in entries],
                    "evidence_ids": [f"{case['case_id']}:{c}:{i}" for c, i, _ in entries],
                    "representative": rep,
                }
            )
        target = case["target"]
        if target and (target["input_start"], target["input_end"]) not in spans:
            a, b = target["input_start"], target["input_end"]
            items.append(
                {
                    "item_id": f"{case['case_id']}:expected",
                    "kind": "expected_target_not_returned",
                    "start": a,
                    "end": b,
                    "text": case["text"][a:b],
                    "configurations": [],
                    "evidence_ids": [],
                    "representative": {
                        "config": None,
                        "record": target["record"],
                        "selection": "frozen source construction, not a detection",
                        "occurrence": {
                            "start": target["source_start"],
                            "end": target["source_end"],
                            "text": target["record"]["text"][
                                target["source_start"] : target["source_end"]
                            ],
                            "errors": target["construction_errors"],
                            "missing_words": target["construction_missing_words"],
                            "alignment": [],
                            "omitted_source_tokens": [],
                        },
                    },
                }
            )
        cards.append({"case_id": case["case_id"], "group": case["group"], "items": items})
    count = sum(len(c["items"]) for c in cards)
    empty = sum(not c["items"] for c in cards)
    return {
        "version": 1,
        "kind": "technical_pilot_review",
        "cards": cards,
        "workload": {
            "input_screens": len(cards),
            "review_pairs": count,
            "textual_judgments": count,
            "boundary_judgments": count,
            "total_judgments": count * 2,
            "zero_alert_acknowledgements": empty,
            "detected_unique_spans": sum(
                i["kind"] == "detection" for c in cards for i in c["items"]
            ),
            "expected_target_checks": sum(
                i["kind"] != "detection" for c in cards for i in c["items"]
            ),
        },
    }


class PilotSession:
    """Separate technical decisions; never read or reinterpret the intent-review CSV."""

    def __init__(self, inputs, run_dir, progress):
        self.inputs = Path(inputs).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.progress_path = Path(progress).resolve()
        self.input_manifest = verified(self.inputs, "technical_pilot_inputs")
        self.capture_manifest = verified(self.run_dir, "technical_pilot_capture")
        if self.capture_manifest["inputs_manifest_sha256"] != digest(self.inputs / "manifest.json"):
            raise ValueError("Pilot capture belongs to different inputs")
        if self.progress_path.is_relative_to(self.inputs) or self.progress_path.is_relative_to(
            self.run_dir
        ):
            raise ValueError("Save progress outside frozen pilot directories")
        if (
            self.progress_path.name in ("phase6-reviewed.csv", "review.csv")
            or self.progress_path.suffix != ".json"
        ):
            raise ValueError("Use a separate .json technical-review progress file")
        self.cases = [
            json.loads(line)
            for line in (self.inputs / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.by_case = {c["case_id"]: c for c in self.cases}
        self.review = read(self.run_dir / "review.json")
        if self.review["version"] != 1 or self.review["kind"] != "technical_pilot_review":
            raise ValueError("Incompatible technical review")
        self.cards = self.review["cards"]
        if [c["case_id"] for c in self.cards] != [c["case_id"] for c in self.cases]:
            raise ValueError("Review cards do not preserve frozen input order")
        self.items = {i["item_id"]: (c["case_id"], i) for c in self.cards for i in c["items"]}
        if len(self.items) != sum(len(c["items"]) for c in self.cards):
            raise ValueError("Duplicate technical review item")
        self.evidence_offsets = {}
        with (self.run_dir / "evidence.jsonl").open("rb") as stream:
            while True:
                offset = stream.tell()
                line = stream.readline()
                if not line:
                    break
                prefix, separator, _ = line.partition(b',"detections":')
                if not separator:
                    raise ValueError("Noncanonical pilot evidence header")
                header = json.loads(prefix + b"}")
                key = (header["case_id"], header["config"])
                if key in self.evidence_offsets:
                    raise ValueError("Duplicate evidence row")
                self.evidence_offsets[key] = offset
        if set(self.evidence_offsets) != {
            (c["case_id"], name) for c in self.cases for name in CONFIGURATIONS
        }:
            raise ValueError("Incomplete pilot evidence")
        self.identity = {
            "version": 1,
            "kind": "technical_pilot_progress",
            "inputs_manifest_sha256": digest(self.inputs / "manifest.json"),
            "capture_manifest_sha256": digest(self.run_dir / "manifest.json"),
        }
        self.saved_hash = self.disk_hash()
        self.progress = (
            read(self.progress_path)
            if self.progress_path.exists()
            else {
                **self.identity,
                "decisions": {key: blank_answer() for key in self.items},
                "acknowledged_cases": [],
            }
        )
        self.validate(self.progress)
        self.current = next((n for n, c in enumerate(self.cards) if not self.complete(c)), None)

    def disk_hash(self):
        return digest(self.progress_path) if self.progress_path.exists() else None

    def evidence(self, identity):
        case_id, config, number = identity.rsplit(":", 2)
        with (self.run_dir / "evidence.jsonl").open("rb") as stream:
            stream.seek(self.evidence_offsets[case_id, config])
            row = json.loads(stream.readline())
        return row["detections"][int(number)]

    def validate(self, progress):
        if not isinstance(progress, dict) or type(progress.get("version")) is not int:
            raise ValueError("Invalid technical progress structure")
        if set(progress) != {*self.identity, "decisions", "acknowledged_cases"} or any(
            progress[k] != v for k, v in self.identity.items()
        ):
            raise ValueError("Progress format or frozen pilot identity differs")
        answers = progress["decisions"]
        if not isinstance(answers, dict) or set(answers) != set(self.items):
            raise ValueError("Every pilot pair must be preserved exactly once")
        for key, answer in answers.items():
            if not isinstance(answer, dict) or set(answer) != ANSWER_FIELDS:
                raise ValueError("Unknown or missing technical decision fields")
            if (
                not isinstance(answer["correspondence"], str)
                or answer["correspondence"] not in CORRESPONDENCE
                or not isinstance(answer["boundaries"], str)
                or answer["boundaries"] not in BOUNDARIES
                or not isinstance(answer["notes"], str)
            ):
                raise ValueError("Invalid technical judgment or notes")
            case_id, item = self.items[key]
            changes = []
            for prefix, text in (
                ("input", self.by_case[case_id]["text"]),
                ("source", item["representative"]["record"]["text"]),
            ):
                a, b = answer[prefix + "_start"], answer[prefix + "_end"]
                if a is None and b is None:
                    continue
                if type(a) is not int or type(b) is not int or not 0 <= a < b <= len(text):
                    raise ValueError("Corrected boundaries must be valid Python character offsets")
                old_a = (
                    item["start"]
                    if prefix == "input"
                    else item["representative"]["occurrence"]["start"]
                )
                old_b = (
                    item["end"]
                    if prefix == "input"
                    else item["representative"]["occurrence"]["end"]
                )
                changes.append((a, b) != (old_a, old_b))
            if answer["boundaries"] == "correct":
                if changes and not any(changes):
                    raise ValueError(
                        "Correct requires at least one changed input or source boundary"
                    )
            elif changes:
                raise ValueError("Boundary edits require Correct")
        acknowledged = progress["acknowledged_cases"]
        empty = {c["case_id"] for c in self.cards if not c["items"]}
        if (
            not isinstance(acknowledged, list)
            or any(not isinstance(c, str) for c in acknowledged)
            or len(set(acknowledged)) != len(acknowledged)
            or not set(acknowledged) <= empty
        ):
            raise ValueError("Only zero-alert cases can be acknowledged")
        return {
            "status": "technical_review_draft",
            "human_review_approved": False,
            "pairs": len(answers),
            "completed_pairs": sum(answer_complete(a) for a in answers.values()),
            "acknowledged_zero_alert_cases": len(acknowledged),
        }

    def complete(self, card):
        if not card["items"]:
            return card["case_id"] in self.progress["acknowledged_cases"]
        return all(answer_complete(self.progress["decisions"][i["item_id"]]) for i in card["items"])

    def save(self, progress):
        self.validate(progress)
        if self.disk_hash() != self.saved_hash:
            raise ValueError("Progress changed externally; reopen this notebook before saving")
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        content = canonical(progress)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.progress_path.parent,
                prefix=".pilot-progress-",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.progress_path)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        self.progress = progress
        self.saved_hash = hashlib.sha256(content).hexdigest()

    def update(self, item_id, **changes):
        if item_id not in self.items or not changes.keys() <= ANSWER_FIELDS:
            raise ValueError("Unknown item or decision field")
        proposed = copy.deepcopy(self.progress)
        proposed["decisions"][item_id].update(changes)
        self.save(proposed)

    def acknowledge(self, case_id):
        proposed = copy.deepcopy(self.progress)
        if case_id not in proposed["acknowledged_cases"]:
            proposed["acknowledged_cases"].append(case_id)
        self.save(proposed)


def metrics(session):
    """Controlled and descriptive measurements only; never finalize reviewed scores."""
    outputs = evidence_rows(session.cases, session.run_dir / "evidence.jsonl")
    per_config = {}
    for config, (minimum, errors, missing) in CONFIGURATIONS.items():
        groups = {}
        recovered_ids = set()
        for group in ("exact", "fuzzy:edits", "fuzzy:omissions", "fuzzy:combined"):
            selected = [
                c
                for c in session.cases
                if (c["group"] if c["group"] != "fuzzy" else "fuzzy:" + c["subtype"]) == group
            ]
            eligible, recovered, eligible_recovered, boundaries, partial = [], [], [], [], []
            for case in selected:
                target = case["target"]
                fits = (
                    target["matched_words"] >= minimum
                    and target["construction_errors"] <= errors
                    and target["construction_missing_words"] <= missing
                )
                if fits:
                    eligible.append(case["case_id"])
                full = []
                for d in outputs[case["case_id"]][config]:
                    if d["start"] <= target["input_start"] and d["end"] >= target["input_end"]:
                        for ref in d["references"]:
                            if ref["record"]["hadith_key"] == target["record"]["hadith_key"]:
                                full.extend(
                                    (d, o)
                                    for o in ref["occurrences"]
                                    if o["start"] <= target["source_start"]
                                    and o["end"] >= target["source_end"]
                                    and o["alignment"][0]["source_token"]
                                    == target["aligned_source_tokens"][0]
                                    and o["alignment"][-1]["source_token"]
                                    == target["aligned_source_tokens"][-1]
                                )
                if full:
                    recovered.append(case["case_id"])
                    recovered_ids.add(case["case_id"])
                    if fits:
                        eligible_recovered.append(case["case_id"])
                    if any(
                        (d["start"], d["end"], o["start"], o["end"])
                        == (
                            target["input_start"],
                            target["input_end"],
                            target["source_start"],
                            target["source_end"],
                        )
                        for d, o in full
                    ):
                        boundaries.append(case["case_id"])
                elif outputs[case["case_id"]][config]:
                    partial.append(case["case_id"])
            groups[group] = {
                "total": len(selected),
                "construction_eligible": len(eligible),
                "construction_eligible_ids": eligible,
                "full_origin_recovered": len(recovered),
                "full_origin_recovered_ids": recovered,
                "eligible_full_origin_recovered": len(eligible_recovered),
                "exact_boundary_agreement": len(boundaries),
                "partial_or_other_matches_ids": partial,
                "construction_ineligible": len(selected) - len(eligible),
            }
        descriptive = {}
        for name in ("natural", "commentary"):
            paragraphs = [c for c in session.cases if c["group"] == name]
            alerts = [
                {
                    "case_id": c["case_id"],
                    "start": d["start"],
                    "end": d["end"],
                    "text": d["text"],
                    "references": [r["record"]["hadith_key"] for r in d["references"]],
                }
                for c in paragraphs
                for d in outputs[c["case_id"]][config]
            ]
            descriptive[name] = {
                "paragraphs": len(paragraphs),
                "affected_ids": sorted({a["case_id"] for a in alerts}),
                "detections": len(alerts),
                "alerts": alerts,
                "classification": "textual_alerts_not_false_positive_or_recall_labels",
            }
        per_config[config] = {
            "positives": groups,
            "recovered_positive_ids": sorted(recovered_ids),
            **descriptive,
        }
    baseline = set(per_config[DEFAULT]["recovered_positive_ids"])
    for config, output in per_config.items():
        recovered = set(output["recovered_positive_ids"])
        here = {
            (c["case_id"], d["start"], d["end"])
            for c in session.cases
            for d in outputs[c["case_id"]][config]
        }
        base = {
            (c["case_id"], d["start"], d["end"])
            for c in session.cases
            for d in outputs[c["case_id"]][DEFAULT]
        }
        output["versus_default"] = {
            "gained_full_targets": sorted(recovered - baseline),
            "lost_full_targets": sorted(baseline - recovered),
            "added_spans": sorted(here - base),
            "removed_spans": sorted(base - here),
        }
        eligible_here = {
            identity
            for group in output["positives"].values()
            for identity in group["construction_eligible_ids"]
        }
        eligible_base = {
            identity
            for group in per_config[DEFAULT]["positives"].values()
            for identity in group["construction_eligible_ids"]
        }
        common = eligible_here & eligible_base
        output["versus_default"]["common_construction_eligible"] = {
            "ids": sorted(common),
            "denominator": len(common),
            "recovered_here": len(recovered & common),
            "recovered_default": len(baseline & common),
        }
        output["all_positive_recovery"] = {
            "count": len(recovered),
            "denominator": sum(c["target"] is not None for c in session.cases),
        }
        output["groups"] = {}
        for group in ("exact", "fuzzy", "natural", "commentary"):
            members = {c["case_id"] for c in session.cases if c["group"] == group}
            summary = {
                "inputs": len(members),
                "added_spans_vs_default": sorted(s for s in here - base if s[0] in members),
                "removed_spans_vs_default": sorted(s for s in base - here if s[0] in members),
            }
            if group in ("natural", "commentary"):
                summary["descriptive_alerts"] = output[group]
            else:
                details = {
                    k: v
                    for k, v in output["positives"].items()
                    if k == group or k.startswith(group + ":")
                }
                summary["controlled_recovery"] = details
                summary["construction_eligible"] = sum(
                    v["construction_eligible"] for v in details.values()
                )
                summary["eligible_full_origin_recovered"] = sum(
                    v["eligible_full_origin_recovered"] for v in details.values()
                )
                summary["all_input_recovery_yield"] = {
                    "count": len(recovered & members),
                    "denominator": len(members),
                }
            output["groups"][group] = summary
    # These counts are progress only, not human-reviewed quality conclusions.
    progress = {
        name: dict(Counter(a[name] or "pending" for a in session.progress["decisions"].values()))
        for name in ("correspondence", "boundaries")
    }
    by_group = {}
    for group in ("exact", "fuzzy", "natural", "commentary"):
        answers = [
            session.progress["decisions"][identity]
            for identity, (case_id, _) in session.items.items()
            if session.by_case[case_id]["group"] == group
        ]
        by_group[group] = {
            "inputs": sum(c["group"] == group for c in session.cases),
            "pairs": len(answers),
            **{
                name: dict(Counter(a[name] or "pending" for a in answers))
                for name in ("correspondence", "boundaries")
            },
        }
    return {
        "status": "controlled_and_descriptive_only",
        "inputs_manifest_sha256": session.identity["inputs_manifest_sha256"],
        "capture_manifest_sha256": session.identity["capture_manifest_sha256"],
        "progress_sha256": session.saved_hash,
        "group_denominators": {
            group: sum(c["group"] == group for c in session.cases)
            for group in ("exact", "fuzzy", "natural", "commentary")
        },
        "human_review_approved": False,
        "configurations": per_config,
        "review_progress_counts": progress,
        "review_progress_by_group": by_group,
        "reviewed_error_scores": "withheld_until_maintainer_review",
        "precision_recall": "not_estimated",
        "default_unchanged": True,
    }
