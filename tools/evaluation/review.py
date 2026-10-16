"""One reversible, editable CSV; no automatic promotion of drafts to gold."""

import csv
import io
import json
from collections import Counter

DECISIONS = {"", "accept", "correct", "reject", "uncertain"}
CASE_LABELS = {"contains_quotation", "quotation_free", "uncertain", "out_of_corpus"}
INTENTS = {
    "intended_quotation",
    "not_intended_quotation",
    "incidental_chain",
    "quranic_wording",
    "uncertain",
    "out_of_corpus",
}
EDITABLE = [
    "decision",
    "corrected_case_label",
    "corrected_intent",
    "corrected_start",
    "corrected_end",
    "corrected_references",
    "reviewer_notes",
]
FIELDS = EDITABLE + [
    "case_id",
    "row_kind",
    "proposal_id",
    "proposed_case_label",
    "proposed_intent",
    "span_start",
    "span_end",
    "span_text",
    "input_text",
    "corpus_support",
    "supporting_references",
    "supporting_reference_count",
    "reference_union_id",
    "reference_preview_note",
    "uncertainty_flags",
    "proposal_notes",
    "group",
    "stratum",
    "source_url",
    "source_revision",
    "source_license",
    "source_license_url",
    "source_attribution",
    "source_start",
    "source_end",
    "source_context",
    "configurations",
    "evidence_ids",
    "config_costs",
    "default_comparison",
    "csv_escaped_fields",
]


def base_row(case, kind, identity):
    source = case["source"]
    row = dict.fromkeys(FIELDS, "")
    row.update(
        case_id=case["case_id"],
        row_kind=kind,
        proposal_id=identity,
        proposed_case_label=case["proposed_case_label"],
        input_text=case["text"],
        group=case["group"],
        stratum=case["stratum"],
        source_url=source["url"],
        source_revision=str(source["revision"]),
        source_license=source.get("reuse", {}).get("license", ""),
        source_license_url=source.get("reuse", {}).get("license_url", ""),
        source_attribution=source.get("reuse", {}).get("attribution", ""),
        source_start=str(source["start"]),
        source_end=str(source["end"]),
        source_context=source["text"],
        uncertainty_flags="human_review_required",
    )
    return row


def rows_for_case(case, predictions, keys, default="m5-e0-o0"):
    """Merge exactly equal input spans, not semantic claims or overlapping passages."""
    assessment = base_row(case, "case", case["case_id"] + ":case")
    assessment["proposal_notes"] = (
        "Review the WHOLE input; quotation-free is provisional, not inferred from no matches. "
        "Add missing spans, including quotations missed by all configurations."
    )
    rows = [assessment]
    spans = {}
    for proposal in case["proposals"]:
        a, b = proposal["start"], proposal["end"]
        spans[a, b] = {
            "proposal": proposal,
            "refs": set(),
            "configs": [],
            "evidence": [],
            "costs": {},
        }
        if case["group"] == "corpus_derived":
            spans[a, b]["refs"].add(case["source"]["hadith_key"])
    for config, results in predictions.items():
        for index, match in enumerate(results):
            a, b = match.start, match.end
            if (a, b) not in spans:
                spans[a, b] = {
                    "proposal": {
                        "label": "not_intended_quotation"
                        if case["proposed_case_label"] == "quotation_free"
                        else "uncertain",
                        "flags": "detector_suggestion_not_gold",
                        "note": "Textual support does not establish intended quotation status.",
                    },
                    "refs": set(),
                    "configs": [],
                    "evidence": [],
                    "costs": {},
                }
            item = spans[a, b]
            item["refs"].update(ref.record.hadith_key for ref in match.references)
            item["configs"].append(config)
            item["evidence"].append(f"{case['case_id']}:{config}:{index}")
            item["costs"][config] = [match.errors, match.missing_words]
    for number, ((a, b), item) in enumerate(sorted(spans.items()), 1):
        row = base_row(case, "span", f"{case['case_id']}:span:{number}")
        row.update(
            span_start=str(a),
            span_end=str(b),
            span_text=case["text"][a:b],
            proposed_intent=item["proposal"]["label"],
            uncertainty_flags="human_review_required;" + item["proposal"]["flags"],
            proposal_notes=item["proposal"]["note"],
            supporting_references=";".join(sorted(item["refs"], key=keys.__getitem__)),
            configurations=";".join(item["configs"]),
            evidence_ids=";".join(item["evidence"]),
            config_costs=json.dumps(item["costs"], sort_keys=True, separators=(",", ":")),
            corpus_support="detector_supported"
            if item["configs"]
            else "source_slice_verified"
            if case["group"] == "corpus_derived"
            else "unestablished",
            default_comparison="in_default"
            if default in item["configs"]
            else "alternate_settings_only"
            if item["configs"]
            else "input_proposal_only",
        )
        if case["proposed_case_label"] == "quotation_free" and item["configs"]:
            row["uncertainty_flags"] += ";candidate_unwanted_alert_not_confirmed_false_positive"
        rows.append(row)
    return rows


def encode_csv(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\r\n")
    writer.writeheader()
    for original in rows:
        row = original.copy()
        escaped = []
        for name, value in row.items():
            if (
                name not in EDITABLE
                and name != "csv_escaped_fields"
                and value.lstrip().startswith(("=", "+", "-", "@"))
            ):
                row[name] = "'" + value
                escaped.append(name)
        row["csv_escaped_fields"] = ";".join(escaped)
        writer.writerow(row)
    return stream.getvalue().encode("utf-8-sig")


def decode_csv(content):
    csv.field_size_limit(100_000_000)
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != FIELDS:
        raise ValueError("Review CSV columns changed; retain the exported header")
    rows = list(reader)
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed CSV row")
        escaped = row["csv_escaped_fields"].split(";") if row["csv_escaped_fields"] else []
        for name in escaped:
            if name not in FIELDS or name in EDITABLE or not row[name].startswith("'"):
                raise ValueError("Invalid reversible CSV text escape")
            row[name] = row[name][1:]
        row["csv_escaped_fields"] = ""
    return rows


def validate_review(rows, cases, keys, config_ids):
    """Validate reviewer edits as drafts; this function never approves gold."""
    by_id = {c["case_id"]: c for c in cases}
    seen = set()
    assessed = Counter()
    for row in rows:
        if row["case_id"] not in by_id or row["proposal_id"] in seen:
            raise ValueError("Unknown case or duplicate review row")
        seen.add(row["proposal_id"])
        case = by_id[row["case_id"]]
        if row["input_text"] != case["text"] or row["group"] != case["group"]:
            raise ValueError("Frozen input/group edited; use correction fields only")
        if row["decision"] not in DECISIONS or row["row_kind"] not in ("case", "span"):
            raise ValueError("Invalid decision or row kind")
        if row["corrected_case_label"] and row["corrected_case_label"] not in CASE_LABELS:
            raise ValueError("Unknown corrected case label")
        if row["corrected_intent"] and row["corrected_intent"] not in INTENTS:
            raise ValueError("Unknown corrected intent")
        if row["decision"] == "correct" and not any(row[k] for k in EDITABLE[1:-1]):
            raise ValueError("A correct decision needs at least one correction field")
        if row["decision"] != "correct" and any(row[k] for k in EDITABLE[1:-1]):
            raise ValueError("Correction fields require decision=correct")
        for name in ("supporting_references", "corrected_references"):
            if any(key not in keys for key in row[name].split(";") if key):
                raise ValueError("Unknown reference identity")
        if any(c not in config_ids for c in row["configurations"].split(";") if c):
            raise ValueError("Unknown configuration")
        if row["row_kind"] == "case":
            if any(row[k] for k in ("corrected_start", "corrected_end", "corrected_intent")):
                raise ValueError("Paragraph assessments cannot correct span fields")
            assessed[case["case_id"]] += 1
        else:
            if row["corrected_case_label"]:
                raise ValueError("Correct paragraph status on its case row")
            if row["span_start"] or row["span_end"]:
                a, b = int(row["span_start"]), int(row["span_end"])
                if not 0 <= a < b <= len(case["text"]) or case["text"][a:b] != row["span_text"]:
                    raise ValueError("Original span offsets/text changed")
            if bool(row["corrected_start"]) != bool(row["corrected_end"]):
                raise ValueError("Supply both corrected offsets, including explicit zero")
            if row["corrected_start"]:
                a, b = int(row["corrected_start"]), int(row["corrected_end"])
                if not 0 <= a < b <= len(case["text"]):
                    raise ValueError("Corrected span outside original input")
            if not row["span_start"] and not row["corrected_start"]:
                raise ValueError("New span rows require corrected offsets")
    if assessed != Counter({c["case_id"]: 1 for c in cases}):
        raise ValueError("Exactly one paragraph assessment is required per case")
    return {
        "status": "draft_only",
        "gold_approved": False,
        "rows": len(rows),
        "decisions": dict(Counter(r["decision"] or "pending" for r in rows)),
    }


def resolve_drafts(rows):
    """Normalize decisions for future scoring without granting annotation approval."""
    proposals = []
    for row in rows:
        item = {
            "case_id": row["case_id"],
            "proposal_id": row["proposal_id"],
            "row_kind": row["row_kind"],
            "decision": row["decision"] or "pending",
        }
        if row["decision"] in ("accept", "correct"):
            if row["row_kind"] == "case":
                item["classification"] = row["corrected_case_label"] or row["proposed_case_label"]
            else:
                item["classification"] = row["corrected_intent"] or row["proposed_intent"]
                item["start"] = int(row["corrected_start"] or row["span_start"])
                item["end"] = int(row["corrected_end"] or row["span_end"])
                refs = row["corrected_references"] or row["supporting_references"]
                item["known_supporting_references"] = refs.split(";") if refs else []
                item["references_complete"] = False
                item["reference_union_id"] = row["reference_union_id"]
        proposals.append(item)
    return {"gold_approved": False, "status": "draft_decisions_only", "proposals": proposals}
