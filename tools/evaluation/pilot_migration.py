"""Lossless, reviewable migration of technical judgments; activation is a separate step."""

import argparse
import copy
import json
from pathlib import Path

from tools.exact_benchmark.corpus import canonical, digest

from .dataset import read
from .pilot import publish, verified
from .pilot_review import PilotSession, blank_answer


def matching_identity(session, identity):
    case_id, item = session.items[identity]
    return canonical(
        {
            "input": session.by_case[case_id],
            "displayed_item": item,
            "supporting_evidence": [session.evidence(e) for e in item["evidence_ids"]],
        }
    )


def propose(old, new, output):
    """Copy only exact input/display/support identities; retain every excluded answer."""
    old.validate(old.progress)
    new.validate(new.progress)
    if old.disk_hash() != old.saved_hash or new.disk_hash() != new.saved_hash:
        raise ValueError("Review state changed while preparing migration")
    if new.progress_path.exists():
        raise FileExistsError("Refuse to replace existing destination progress")
    proposed = copy.deepcopy(new.progress)
    migrated, excluded = [], []
    for identity, answer in old.progress["decisions"].items():
        if answer == blank_answer():
            continue
        if identity not in new.items:
            reason = "input_or_span_not_selected"
        elif matching_identity(old, identity) != matching_identity(new, identity):
            reason = "input_display_or_complete_supporting_evidence_changed"
        else:
            proposed["decisions"][identity] = copy.deepcopy(answer)
            migrated.append(identity)
            continue
        excluded.append({"item_id": identity, "reason": reason, "answer": copy.deepcopy(answer)})
    acknowledgements = []
    for case_id in old.progress["acknowledged_cases"]:
        old_card = next(c for c in old.cards if c["case_id"] == case_id)
        new_card = next((c for c in new.cards if c["case_id"] == case_id), None)
        if (
            new_card
            and not new_card["items"]
            and old.by_case[case_id] == new.by_case[case_id]
            and old_card == new_card
        ):
            proposed["acknowledged_cases"].append(case_id)
            acknowledgements.append(case_id)
        else:
            excluded.append(
                {
                    "case_id": case_id,
                    "reason": "zero_alert_input_or_evidence_changed",
                    "acknowledgement": True,
                }
            )
    new.validate(proposed)
    report = {
        "version": 1,
        "kind": "technical_pilot_migration_report",
        "old_progress_sha256": old.saved_hash,
        "old_inputs_manifest_sha256": old.identity["inputs_manifest_sha256"],
        "old_capture_manifest_sha256": old.identity["capture_manifest_sha256"],
        "new_inputs_manifest_sha256": new.identity["inputs_manifest_sha256"],
        "new_capture_manifest_sha256": new.identity["capture_manifest_sha256"],
        "migrated_items": migrated,
        "migrated_zero_alert_acknowledgements": acknowledgements,
        "unmigrated": excluded,
        "requires_explicit_activation_approval": bool(excluded),
        "old_review_untouched": True,
        "human_review_approved": False,
    }
    with publish(output) as temporary:
        (temporary / "proposed-progress.json").write_bytes(canonical(proposed))
        (temporary / "report.json").write_bytes(canonical(report))
        # Keep the entire original progress, not just selected answers, independently recoverable.
        (temporary / "original-progress.json").write_bytes(old.progress_path.read_bytes())
        (temporary / "manifest.json").write_bytes(
            canonical(
                {
                    "version": 1,
                    "kind": "technical_pilot_migration",
                    "artifacts": {p.name: digest(p) for p in sorted(temporary.iterdir())},
                }
            )
        )
    return report


def activate(proposal, old_progress, destination, *, approve_unmigrated=False):
    """Never overwrite old or existing new progress. Approval is caller-supplied, not inferred."""
    verified(proposal, "technical_pilot_migration")
    report = read(proposal / "report.json")
    if report["unmigrated"] and not approve_unmigrated:
        raise ValueError("Unmigrated judgments require explicit approval before activation")
    if digest(old_progress) != report["old_progress_sha256"]:
        raise ValueError("Original annotations changed; prepare and review a fresh migration")
    if destination.progress_path.exists():
        raise FileExistsError("Destination progress exists; refuse to overwrite judgments")
    proposed = read(proposal / "proposed-progress.json")
    destination.validate(proposed)
    destination.save(proposed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("old", "new"):
        parser.add_argument(f"--{prefix}-inputs", type=Path, required=True)
        parser.add_argument(f"--{prefix}-run", type=Path, required=True)
        parser.add_argument(f"--{prefix}-progress", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    old = PilotSession(args.old_inputs, args.old_run, args.old_progress)
    new = PilotSession(args.new_inputs, args.new_run, args.new_progress)
    report = propose(old, new, args.output_dir)
    print(
        json.dumps(
            {
                "migrated_items": len(report["migrated_items"]),
                "unmigrated": len(report["unmigrated"]),
                "activated": False,
                "report": str(args.output_dir / "report.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
