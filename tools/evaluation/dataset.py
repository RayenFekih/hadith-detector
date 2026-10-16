"""Freeze original evaluation inputs and explicitly provisional draft spans."""

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from tools.evaluation.acquire import Paragraphs
from tools.exact_benchmark.corpus import canonical, digest


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def draft_spans(text):
    """Input-only annotation suggestions; never detector outputs or gold labels."""
    proposals = []
    for match in re.finditer(r"«([^»]+)»|“([^”]+)”", text):
        group = 1 if match.group(1) is not None else 2
        a, b = match.span(group)
        if len(text[a:b].split()) >= 3:
            context = text[max(0, a - 120) : a]
            label = (
                "intended_quotation" if re.search(r"ﷺ|رسول الله|النبي", context) else "uncertain"
            )
            proposals.append(
                {
                    "start": a,
                    "end": b,
                    "label": label,
                    "flags": "quoted_speech_requires_attribution_review",
                    "note": "Quotation marks identify speech, not Hadith authentication.",
                }
            )
    if not proposals:
        cue = re.search(r"(?:رسول الله|النبي)[^\n.!؟]{0,35}?\bيقول\b\s*[:：]?\s*", text)
        if cue:
            a = cue.end()
            stop = re.search(r"(?:رواه|خرجه|أخرجه|متفق عليه)", text[a:])
            b = a + stop.start() if stop else len(text)
            while a < b and text[a].isspace():
                a += 1
            while b > a and text[b - 1].isspace():
                b -= 1
            if len(text[a:b].split()) >= 3:
                proposals.append(
                    {
                        "start": a,
                        "end": b,
                        "label": "intended_quotation",
                        "flags": "attribution_and_boundaries_require_review",
                        "note": "Draft from an explicit attribution cue, before detection.",
                    }
                )
    return proposals


def freeze(legacy: Path, sources: Path, output: Path):
    """Publish inputs only after structure/provenance checks; never overwrite."""
    if output.exists():
        raise FileExistsError(output)
    lock = read(sources / "sources.lock.json")
    cases = []
    with legacy.open(encoding="utf-8-sig", newline="") as stream:
        original = list(csv.DictReader(stream))
    for row in original:
        text = row["query_text"]
        a, b = int(row["source_start"]), int(row["source_end"])
        if row["source_text"][a:b] != text:
            raise ValueError(f"Legacy substring mismatch: {row['sample_id']}")
        if any(row[k] for k in ("gold_label", "expected_references", "reviewer_notes")):
            raise ValueError(
                "Existing human annotations require deliberate import, not replacement"
            )
        proposal = {
            "start": 0,
            "end": len(text),
            "label": "intended_quotation"
            if row["sample_stratum"] == "quote_marked"
            else "uncertain",
            "flags": "legacy_sampling_is_not_gold",
            "note": "Review attribution and boundaries in source context; no mode filtering.",
        }
        cases.append(
            {
                "case_id": row["sample_id"],
                "group": "corpus_derived",
                "stratum": row["sample_stratum"],
                "text": text,
                "proposed_case_label": "contains_quotation"
                if proposal["label"] == "intended_quotation"
                else "uncertain",
                "proposals": [proposal],
                "source": {
                    "hadith_key": row["source_hadith_key"],
                    "url": row["sunnah_url"],
                    "revision": "",
                    "start": a,
                    "end": b,
                    "text": row["source_text"],
                    "input_sha256": digest(legacy),
                    "reuse": {
                        "license": "Classical Arabic public domain; upstream compilation Unlicense",
                        "license_url": "https://github.com/fawazahmed0/hadith-api/blob/1/LICENSE",
                        "attribution": "QuranLab and fawazahmed0/hadith-api; see data/README.md",
                    },
                },
                "original": row,
            }
        )
    for source in lock["sources"]:
        path = sources / source["snapshot"]
        if digest(path) != source["snapshot_sha256"]:
            raise ValueError("Source checksum mismatch")
        parser = Paragraphs()
        parser.feed(read(path)["parse"]["text"])
        parser.close()
        full = "\n\n".join(parser.items)
        if hashlib.sha256(full.encode()).hexdigest() != source["plain_text_sha256"]:
            raise ValueError("Source extraction changed")
        for selected in source["selected"]:
            a, b = selected["start"], selected["end"]
            text = full[a:b]
            if text != parser.items[selected["paragraph"]]:
                raise ValueError("Extraction boundaries differ")
            proposals = draft_spans(text)
            general = source["stratum"] == "general_arabic"
            number = sum(c["group"] == "natural_text" for c in cases) + 1
            cases.append(
                {
                    "case_id": f"N{number:04d}",
                    "group": "natural_text",
                    "stratum": source["stratum"],
                    "text": text,
                    "proposed_case_label": "quotation_free"
                    if general
                    else "contains_quotation"
                    if any(p["label"] == "intended_quotation" for p in proposals)
                    else "uncertain",
                    "proposals": proposals,
                    "source": {**source, "start": a, "end": b, "text": text},
                }
            )
    drafts_path = Path(__file__).with_name("natural-drafts.json")
    if drafts_path.exists():
        drafts = read(drafts_path)["annotations"]
        natural_ids = {c["case_id"] for c in cases if c["stratum"] == "quotation_rich"}
        if set(drafts) != natural_ids:
            raise ValueError("Input-first annotation IDs differ from selected paragraphs")
        for case in cases:
            if case["case_id"] in drafts:
                draft = drafts[case["case_id"]]
                if hashlib.sha256(case["text"].encode()).hexdigest() != draft["text_sha256"]:
                    raise ValueError("Input-first annotation was prepared for different text")
                case["proposals"] = draft["proposals"]
                case["proposed_case_label"] = draft["case_label"]
    validate_cases(cases)
    if Counter(c["group"] for c in cases) != {"corpus_derived": 96, "natural_text": 40}:
        raise ValueError("Expected 96 corpus-derived and 40 natural cases")
    output.mkdir(parents=True)
    (output / "cases.jsonl").write_bytes(b"".join(canonical(c) for c in cases))
    manifest = {
        "version": 1,
        "status": "provisional_unreviewed",
        "gold_approved": False,
        "counts": dict(Counter(c["group"] for c in cases)),
        "cases_sha256": digest(output / "cases.jsonl"),
        "legacy_sha256": digest(legacy),
        "sources_lock_sha256": digest(sources / "sources.lock.json"),
        "source_lock": lock,
        "draft_annotations_sha256": digest(drafts_path) if drafts_path.exists() else None,
        "selection_before_detection": True,
    }
    (output / "manifest.json").write_bytes(canonical(manifest))
    print(f"Frozen {len(cases)} provisional inputs; no detector was loaded.", flush=True)
    return cases


def validate_cases(cases):
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate case identity")
    for case in cases:
        if case["group"] not in ("natural_text", "corpus_derived") or not case["text"]:
            raise ValueError("Invalid case")
        for p in case["proposals"]:
            a, b = p["start"], p["end"]
            if not (isinstance(a, int) and isinstance(b, int) and 0 <= a < b <= len(case["text"])):
                raise ValueError("Invalid proposal offsets")


def load(path):
    manifest = read(path / "manifest.json")
    if digest(path / "cases.jsonl") != manifest["cases_sha256"]:
        raise ValueError("Frozen case checksum mismatch")
    cases = [
        json.loads(line) for line in (path / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    validate_cases(cases)
    return cases, manifest
