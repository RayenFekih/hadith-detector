"""Repository-only review controller and lazy evidence browser (never detects)."""

import copy
import hashlib
import html
import json
import os
import tempfile
from pathlib import Path

from .dataset import load, read
from .pipeline import CONFIGURATIONS, verify_run
from .review import EDITABLE, base_row, decode_csv, encode_csv, validate_review


def highlighted(text, start=None, end=None):
    """Slice Python characters before escaping; never normalize or use UTF-16 offsets."""
    if start is None and end is None:
        body = html.escape(text)
    else:
        if not 0 <= start < end <= len(text):
            raise ValueError("Highlight outside original input")
        body = (
            html.escape(text[:start])
            + '<mark style="background:#ffe28a;color:#171717">'
            + html.escape(text[start:end])
            + "</mark>"
            + html.escape(text[end:])
        )
    return (
        '<div dir="rtl" style="white-space:pre-wrap;overflow-wrap:anywhere;'
        "font:22px/1.9 Amiri,'Noto Naskh Arabic',serif;padding:16px;"
        'border:1px solid #aaa;border-radius:8px">' + body + "</div>"
    )


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


class ReviewSession:
    """One in-memory CSV, validated atomic saves, no annotation sidecars."""

    def __init__(self, dataset_dir, run_dir, progress_path):
        self.dataset_dir = Path(dataset_dir).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.progress_path = Path(progress_path).resolve()
        if self.progress_path == self.run_dir / "review.csv":
            raise ValueError("Progress must not overwrite the original review CSV")
        # Protect every captured artifact and frozen input, not just review.csv.
        if self.progress_path.is_relative_to(self.run_dir) or self.progress_path.is_relative_to(
            self.dataset_dir
        ):
            raise ValueError("Save progress outside the frozen input and evidence directories")
        manifest = verify_run(self.run_dir)
        if file_hash(self.dataset_dir / "manifest.json") != manifest["dataset_manifest_sha256"]:
            raise ValueError("Review dataset differs from captured run")
        self.cases, _ = load(self.dataset_dir)
        self.by_case = {case["case_id"]: case for case in self.cases}
        self.keys = read(self.run_dir / "reference-ids.json")
        self.original = decode_csv((self.run_dir / "review.csv").read_bytes())
        self.baseline = {r["proposal_id"]: r for r in self.original}
        self.rows = (
            decode_csv(self.progress_path.read_bytes())
            if self.progress_path.exists()
            else copy.deepcopy(self.original)
        )
        self.saved_hash = file_hash(self.progress_path)
        self.validate(self.rows)
        self.current = next((r["proposal_id"] for r in self.rows if not r["decision"]), None)
        if self.current is None:
            self.current = self.rows[0]["proposal_id"] if self.rows else None

    def validate(self, rows):
        for row in rows:
            baseline = self.baseline.get(row["proposal_id"])
            if baseline is not None:
                if any(row[k] != baseline[k] for k in baseline if k not in EDITABLE):
                    raise ValueError("Immutable proposal changed")
            elif (
                row["row_kind"] != "span"
                or not row["proposal_id"].startswith(f"manual:{row['case_id']}:")
                or not row["corrected_intent"]
            ):
                raise ValueError("Manual rows need a manual:CASE: ID and corrected intent")
        if not self.baseline.keys() <= {r["proposal_id"] for r in rows}:
            raise ValueError("Original review rows cannot be removed")
        return validate_review(rows, self.cases, self.keys, CONFIGURATIONS)

    def visible(self, group="all", kind="all", status="pending"):
        return [
            r
            for r in self.rows
            if (group == "all" or r["group"] == group)
            and (kind == "all" or r["row_kind"] == kind)
            and (status == "all" or (r["decision"] or "pending") == status)
        ]

    @property
    def row(self):
        return next((r for r in self.rows if r["proposal_id"] == self.current), None)

    @property
    def progress(self):
        return sum(bool(r["decision"]) for r in self.rows), len(self.rows)

    def jump(self, identity):
        found = [r for r in self.rows if identity in (r["proposal_id"], r["case_id"])]
        if not found:
            raise ValueError("Unknown case or review ID")
        self.current = next((r for r in found if not r["decision"]), found[0])["proposal_id"]

    def move(self, step=1, **filters):
        rows = self.visible(**filters)
        if not rows:
            self.current = None
            return
        ids = [r["proposal_id"] for r in rows]
        position = ids.index(self.current) if self.current in ids else (-1 if step > 0 else 0)
        self.current = ids[(position + step) % len(ids)]

    def save(self, rows=None):
        proposed = self.rows if rows is None else rows
        self.validate(proposed)
        if file_hash(self.progress_path) != self.saved_hash:
            raise ValueError("Progress file changed externally; reopen before saving")
        self.progress_path.parent.mkdir(parents=True, exist_ok=True)
        content = encode_csv(proposed)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.progress_path.parent, prefix=".phase6-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            # Close first: Windows cannot replace an open temporary file.
            os.replace(temporary, self.progress_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.saved_hash = hashlib.sha256(content).hexdigest()
        self.rows = proposed

    def update(self, **changes):
        if self.row is None:
            raise ValueError("No selected review item")
        if any(k not in EDITABLE for k in changes):
            raise ValueError("Only correction and decision fields may be edited")
        rows = copy.deepcopy(self.rows)
        row = next(r for r in rows if r["proposal_id"] == self.current)
        row.update(changes)
        if row["decision"] != "correct":
            for name in EDITABLE[1:-1]:
                row[name] = ""
        self.save(rows)

    def add_span(self, case_id, start, end, intent, references="", notes=""):
        case = self.by_case[case_id]
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not 0 <= start < end <= len(case["text"])
        ):
            raise ValueError("Manual span outside input")
        prefix = f"manual:{case_id}:"
        number = 1
        identities = {r["proposal_id"] for r in self.rows}
        while prefix + str(number) in identities:
            number += 1
        row = base_row(case, "span", prefix + str(number))
        row.update(
            decision="correct",
            corrected_start=str(start),
            corrected_end=str(end),
            corrected_intent=intent,
            corrected_references=references,
            reviewer_notes=notes,
            proposal_notes="Human-added missed quotation; not automatically approved gold.",
        )
        self.save([*self.rows, row])
        self.current = row["proposal_id"]
        return row


class EvidenceBrowser:
    """Byte-offset index and bounded lazy cache; never retains the entire evidence file."""

    def __init__(self, session):
        self.path = session.run_dir / "evidence.jsonl"
        self.cache = {}
        self.offsets = {}
        with self.path.open("rb") as stream:
            for case in session.cases:
                for config in CONFIGURATIONS:
                    self.offsets[case["case_id"], config] = stream.tell()
                    if not stream.readline():
                        raise ValueError("Incomplete evidence")
            if stream.read(1):
                raise ValueError("Extra evidence rows")
        self.unions = {}
        path = session.run_dir / "reference-unions.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                self.unions[item["reference_union_id"]] = item["supporting_references"]

    def get(self, case_id, config):
        key = (case_id, config)
        if key in self.cache:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        with self.path.open("rb") as stream:
            stream.seek(self.offsets[case_id, config])
            value = json.loads(stream.readline())
        if (value["case_id"], value["config"]) != (case_id, config):
            raise ValueError("Evidence identity/order differs")
        if len(self.cache) == 2:
            del self.cache[next(iter(self.cache))]
        self.cache[key] = value["detections"]
        return self.cache[key]

    def references(self, row):
        return self.unions.get(
            row["reference_union_id"],
            [key for key in row["supporting_references"].split(";") if key],
        )


def create_review_ui(session):
    """Import notebook dependencies only when explicitly creating the UI."""
    from .review_widgets import ReviewWidget

    return ReviewWidget(session)
