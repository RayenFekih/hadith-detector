"""Freeze a small technical pilot before reading outcomes; capture only missing evidence."""

import argparse
import hashlib
import json
import platform
import shutil
import tempfile
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path

from hadith_detector._text import tokenize
from tools.exact_benchmark.corpus import canonical, digest

from .dataset import load, read
from .pipeline import CONFIGURATIONS, DEFAULT, fingerprint, verify_run

EXACT_STRATA = ("quote_marked", "middle_window", "opening_window", "long_narration")
FUZZY_COUNTS = {"edits": 6, "omissions": 6, "combined": 3}


def ranked(items):
    return sorted(
        items,
        key=lambda item: (
            hashlib.sha256(("phase6-pilot-v1|42|" + item["parent_id"]).encode()).hexdigest(),
            item["parent_id"],
        ),
    )


def boundary(tokens, position):
    return position in (0, len(tokens)) or (
        tokens[position - 1].start,
        tokens[position - 1].end,
    ) != (tokens[position].start, tokens[position].end)


def positive(identity, group, subtype, text, record, source_positions, errors, missing, parent):
    query = tokenize(text).tokens
    source = tokenize(record["text"]).tokens
    if len(query) < 5 or len(query) != len(source_positions):
        raise ValueError("Fewer than five aligned words or incomplete construction")
    first, last = source_positions[0], source_positions[-1]
    if not boundary(source, first) or not boundary(source, last + 1):
        raise ValueError("Partial source symbol expansion")
    if query[0].segment != query[-1].segment or source[first].segment != source[last].segment:
        raise ValueError("Source or input crosses a matching barrier")
    return {
        "case_id": identity,
        "parent_id": parent["parent_id"],
        "group": group,
        "subtype": subtype,
        "text": text,
        "provenance": parent,
        "target": {
            "input_start": query[0].start,
            "input_end": query[-1].end,
            "source_start": source[first].start,
            "source_end": source[last].end,
            "aligned_source_tokens": source_positions,
            "matched_words": len(query),
            "construction_errors": errors,
            "construction_missing_words": missing,
            "record": record,
        },
    }


def exact_case(case, records):
    record = records[case["source"]["hadith_key"]]
    source = case["source"]
    if (
        record["text"] != source["text"]
        or record["text"][source["start"] : source["end"]] != case["text"]
    ):
        raise ValueError("Original source extraction does not round trip")
    tokens = tokenize(record["text"]).tokens
    path = []
    # Repeated spans in symbol expansions need positions, not a span-to-last-ID map.
    for token in tokenize(case["text"]).tokens:
        candidates = [
            i
            for i, t in enumerate(tokens)
            if (t.start, t.end) == (source["start"] + token.start, source["start"] + token.end)
            and t.term == token.term
            and (not path or i > path[-1])
        ]
        if not candidates:
            raise ValueError("Extraction cuts a written word or symbol")
        path.append(candidates[0])
    if not path or path != list(range(path[0], path[-1] + 1)):
        raise ValueError("Exact source words are not contiguous")
    return positive(
        case["case_id"],
        "exact",
        case["stratum"],
        case["text"],
        record,
        path,
        0,
        0,
        {"parent_id": case["case_id"], "phase": 6, "source": source},
    )


def fuzzy_case(query, records):
    record = records[query["source_hint"]]
    source = tokenize(record["text"]).tokens
    input_tokens = tokenize(query["text"]).tokens
    mutations = query["mutations"]
    omissions = sum(m["kind"] == "omit" for m in mutations)
    begin = query["source_token_start"]
    path = list(range(begin, begin + len(input_tokens) + omissions))
    if not path or path[-1] >= len(source):
        raise ValueError("Invalid source construction")
    terms = [source[i].term for i in path]
    edits = 0
    for mutation in mutations:
        if mutation["kind"] == "omit":
            i = mutation["current_word"]
            if not 0 < i < len(terms) - 1 or terms[i] != mutation["term"]:
                raise ValueError("Invalid internal omission construction")
            terms.pop(i)
            path.pop(i)
        else:
            i = mutation["input_word"]
            if terms[i] != mutation["original"]:
                raise ValueError("Mutation original word differs")
            old, new = terms[i], mutation["mutated"]
            kind = mutation["kind"]
            valid = (
                (
                    kind == "insert"
                    and len(new) == len(old) + 1
                    and any(new[:j] + new[j + 1 :] == old for j in range(len(new)))
                )
                or (
                    kind == "delete"
                    and len(old) == len(new) + 1
                    and any(old[:j] + old[j + 1 :] == new for j in range(len(old)))
                )
                or (
                    kind == "substitute"
                    and len(old) == len(new)
                    and sum(a != b for a, b in zip(old, new, strict=True)) == 1
                )
            )
            if not valid:
                raise ValueError("Mutation is not one recorded character edit")
            terms[i] = new
            edits += 1
    if " ".join(terms) != query["text"] or [t.term for t in input_tokens] != terms:
        raise ValueError("Mutations do not reproduce the frozen input")
    return positive(
        "F-" + query["id"],
        "fuzzy",
        query["category"],
        query["text"],
        record,
        path,
        edits,
        omissions,
        {"parent_id": query["id"], "phase": 4, "query": query},
    )


def select(cases, queries, records, *, profile="50"):
    """No result or evidence argument exists: selection is exclusively input-derived."""
    if profile not in ("50", "55"):
        raise ValueError("Unknown pilot composition")
    pools = {"exact:" + s: [] for s in EXACT_STRATA}
    pools.update({"fuzzy:" + s: [] for s in FUZZY_COUNTS})
    excluded = []
    for case in cases:
        if case["group"] != "corpus_derived":
            continue
        try:
            pools["exact:" + case["stratum"]].append(exact_case(case, records))
        except (ValueError, KeyError) as error:
            excluded.append({"parent_id": case["case_id"], "reason": str(error)})
    for query in queries:
        category = query["category"]
        kinds = {m["kind"] for m in query["mutations"]}
        if (
            category not in FUZZY_COUNTS
            or query["minimum"] != 5
            or query["errors"] > 1
            or query["missing"] > 1
        ):
            continue
        if not (
            (category == "edits" and kinds - {"omit"})
            or (category == "omissions" and "omit" in kinds)
            or (category == "combined" and "omit" in kinds and kinds - {"omit"})
        ):
            continue
        try:
            pools["fuzzy:" + category].append(fuzzy_case(query, records))
        except (ValueError, KeyError, IndexError) as error:
            excluded.append({"parent_id": query["id"], "reason": str(error)})
    natural = [
        c for c in cases if c["group"] == "natural_text" and c["stratum"] == "general_arabic"
    ]
    urls = sorted({c["source"]["url"] for c in natural})
    if len(urls) != 4:
        raise ValueError("Expected four frozen general-Arabic sources")
    for url in urls:
        pools["natural:" + url] = [
            {
                "case_id": c["case_id"],
                "parent_id": c["case_id"],
                "group": "natural",
                "subtype": "negative_candidate",
                "text": c["text"],
                "target": None,
                "provenance": {"parent_id": c["case_id"], "phase": 6, "source": c["source"]},
            }
            for c in natural
            if c["source"]["url"] == url
        ]
    exact_counts = (5, 5, 5, 5) if profile == "50" else (3, 3, 2, 2)
    fuzzy_counts = FUZZY_COUNTS if profile == "50" else {"edits": 4, "omissions": 4, "combined": 2}
    counts = {
        **{"exact:" + s: n for s, n in zip(EXACT_STRATA, exact_counts, strict=True)},
        **{"fuzzy:" + s: n for s, n in fuzzy_counts.items()},
        **{"natural:" + url: n for url, n in zip(urls, (4, 4, 4, 3), strict=True)},
    }
    if profile == "55":
        commentary = [
            c for c in cases if c["group"] == "natural_text" and c["stratum"] == "quotation_rich"
        ]
        if len(commentary) != 20:
            raise ValueError("Include all 20 frozen commentary inputs, without outcome filtering")
        pools["commentary:all"] = [
            {
                "case_id": c["case_id"],
                "parent_id": c["case_id"],
                "group": "commentary",
                "subtype": "religious_commentary",
                "text": c["text"],
                "target": None,
                "provenance": {"parent_id": c["case_id"], "phase": 6, "source": c["source"]},
            }
            for c in commentary
        ]
        counts["commentary:all"] = 20
    selected = []
    for key, count in counts.items():
        if len(pools[key]) < count:
            raise ValueError(
                f"Input eligibility insufficient for {key}; do not replace failed cases"
            )
        selected.extend(ranked(pools[key])[:count])
    if len(selected) != int(profile) or len({c["case_id"] for c in selected}) != int(profile):
        raise ValueError(f"Pilot requires {profile} distinct input identities")
    return selected, {
        "method": "sha256(phase6-pilot-v1|42|original_case_id), then original ID",
        "quotas": counts,
        "eligible_ids": {k: [c["parent_id"] for c in ranked(v)] for k, v in pools.items()},
        "excluded_input_integrity": excluded,
        "selected_ids": [c["case_id"] for c in selected],
        "input_hashes": {
            c["case_id"]: hashlib.sha256(c["text"].encode()).hexdigest() for c in selected
        },
        "selection_before_results": True,
        "composition": profile,
    }


@contextmanager
def publish(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".pilot-", dir=output.parent)).resolve()
    try:
        yield temporary
        if output.exists():
            raise FileExistsError(output)
        try:
            temporary.rename(output)
        except PermissionError:
            # Some managed Windows workspaces prohibit directory renames. A final
            # manifest is the commit marker: readers reject incomplete directories.
            output.mkdir()
            for path in sorted(temporary.iterdir(), key=lambda p: p.name == "manifest.json"):
                shutil.copyfile(path, output / path.name)
    finally:
        if temporary.exists():
            if temporary.parent != output.parent or not temporary.name.startswith(".pilot-"):
                raise ValueError("Unexpected temporary directory")
            shutil.rmtree(temporary)


def freeze(dataset, fuzzy_dir, index, output, *, profile="50"):
    """Only inputs and checksums are read here. No historical outcomes or detector."""
    cases, _ = load(dataset)
    manifest = read(index / "manifest.json")
    if digest(index / "records.jsonl") != manifest["artifacts"]["records.jsonl"]:
        raise ValueError("Source records checksum mismatch")
    records = {
        r["hadith_key"]: r
        for r in (
            json.loads(line)
            for line in (index / "records.jsonl").read_text(encoding="utf-8").splitlines()
        )
    }
    suite = read(fuzzy_dir / "queries.json")
    ready = read(fuzzy_dir / "ready.json")
    if (
        digest(fuzzy_dir / "queries.json") != ready["queries_sha256"]
        or suite["corpus_fingerprint"] != manifest["source_fingerprint"]
    ):
        raise ValueError("Fuzzy query or corpus fingerprint mismatch")
    selected, selection = select(cases, suite["queries"], records, profile=profile)
    parents = {
        "dataset_manifest": digest(dataset / "manifest.json"),
        "fuzzy_queries": digest(fuzzy_dir / "queries.json"),
        "fuzzy_ready": digest(fuzzy_dir / "ready.json"),
        "index_manifest": digest(index / "manifest.json"),
        "source_records": manifest["artifacts"]["records.jsonl"],
        "corpus_fingerprint": manifest["source_fingerprint"],
    }
    with publish(output) as temporary:
        (temporary / "cases.jsonl").write_bytes(b"".join(canonical(c) for c in selected))
        (temporary / "selection.json").write_bytes(canonical(selection))
        (temporary / "manifest.json").write_bytes(
            canonical(
                {
                    "version": 1,
                    "kind": "technical_pilot_inputs",
                    "parents": parents,
                    "artifacts": {p.name: digest(p) for p in sorted(temporary.iterdir())},
                    "selection_code_sha256": digest(Path(__file__)),
                    "results_read": False,
                    "composition": profile,
                }
            )
        )
    return selection


def verified(path, kind):
    manifest = read(path / "manifest.json")
    if manifest.get("version") != 1 or manifest.get("kind") != kind:
        raise ValueError("Incompatible pilot artifact")
    for name, checksum in manifest["artifacts"].items():
        if Path(name).name != name or digest(path / name) != checksum:
            raise ValueError(f"Pilot checksum mismatch: {name}")
    return manifest


def projected(detections):
    return [
        {
            **d,
            "references": [
                {"hadith_key": r["record"]["hadith_key"], "occurrences": r["occurrences"]}
                for r in d["references"]
            ],
        }
        for d in detections
    ]


def capture(inputs, run_dir, fuzzy_dir, index, output, *, reuse_inputs=None, reuse_run=None):
    """Freeze must already have completed in a previous invocation."""
    from hadith_detector import HadithDetector

    frozen = verified(inputs, "technical_pilot_inputs")
    parents = frozen["parents"]
    if digest(index / "manifest.json") != parents["index_manifest"]:
        raise ValueError("Index differs from frozen selection")
    history = verify_run(run_dir)
    if (
        history["dataset_manifest_sha256"] != parents["dataset_manifest"]
        or history["index_manifest_sha256"] != parents["index_manifest"]
    ):
        raise ValueError("Phase 6 evidence parents differ")
    if (
        digest(fuzzy_dir / "queries.json") != parents["fuzzy_queries"]
        or digest(fuzzy_dir / "ready.json") != parents["fuzzy_ready"]
    ):
        raise ValueError("Phase 4 inputs changed")
    if (
        digest(fuzzy_dir / "oracle-results.jsonl")
        != read(fuzzy_dir / "ready.json")["oracle_sha256"]
    ):
        raise ValueError("Historical oracle checksum mismatch")
    cases = [
        json.loads(line)
        for line in (inputs / "cases.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    chosen = {c["parent_id"]: c for c in cases if c["group"] != "fuzzy"}
    oracle_ids = {c["parent_id"] for c in cases if c["group"] == "fuzzy"}
    oracle = {}
    with (fuzzy_dir / "oracle-results.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["id"] in oracle_ids:
                oracle[row["id"]] = row["result"]
    reusable = {}
    if (reuse_inputs is None) != (reuse_run is None):
        raise ValueError("Specify both saved pilot input and capture directories")
    if reuse_inputs is not None:
        reuse_frozen = verified(reuse_inputs, "technical_pilot_inputs")
        reuse_manifest = verified(reuse_run, "technical_pilot_capture")
        if reuse_frozen["parents"] != parents or reuse_manifest["inputs_manifest_sha256"] != digest(
            reuse_inputs / "manifest.json"
        ):
            raise ValueError("Reusable pilot has different input/corpus parents")
        old_cases = {
            c["case_id"]: c
            for c in (
                json.loads(line)
                for line in (reuse_inputs / "cases.jsonl").read_text(encoding="utf-8").splitlines()
            )
        }
        unchanged = {c["case_id"] for c in cases if old_cases.get(c["case_id"]) == c}
        with (reuse_run / "evidence.jsonl").open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                if row["case_id"] in unchanged:
                    reusable[row["case_id"], row["config"]] = row
    detector = None
    calls = 0
    with publish(output) as temporary:
        with (temporary / "evidence.jsonl").open("wb") as saved:
            with (run_dir / "evidence.jsonl").open(encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    if row["case_id"] in chosen:
                        row["origin"] = "saved_phase6"
                        saved.write(canonical(row))
            for case in cases:
                if case["group"] != "fuzzy":
                    continue
                query = case["provenance"]["query"]
                for config, (minimum, errors, missing) in CONFIGURATIONS.items():
                    key = case["case_id"], config
                    if key in reusable:
                        saved.write(canonical({**reusable[key], "origin": "saved_previous_pilot"}))
                        continue
                    if detector is None:
                        detector = HadithDetector(index)
                    detections = [
                        r.to_dict()
                        for r in detector.detect(
                            case["text"],
                            min_match_words=minimum,
                            max_errors=errors,
                            max_missing_words=missing,
                        )
                    ]
                    calls += 1
                    checked = (minimum, errors, missing) == (
                        query["minimum"],
                        query["errors"],
                        query["missing"],
                    )
                    if checked and projected(detections) != oracle[case["parent_id"]]:
                        raise ValueError(
                            f"Saved oracle disagreement: {case['case_id']}; do not replace"
                        )
                    saved.write(
                        canonical(
                            {
                                "case_id": case["case_id"],
                                "config": config,
                                "detections": detections,
                                "origin": "new_missing_fuzzy_capture",
                                "saved_oracle_compared": checked,
                            }
                        )
                    )
                print(f"Captured {case['case_id']} (six configurations)", flush=True)
        from .pilot_review import assemble

        review = assemble(cases, temporary / "evidence.jsonl")
        (temporary / "review.json").write_bytes(canonical(review))
        (temporary / "manifest.json").write_bytes(
            canonical(
                {
                    "version": 1,
                    "kind": "technical_pilot_capture",
                    "inputs_manifest_sha256": digest(inputs / "manifest.json"),
                    "parent_phase6_manifest_sha256": digest(run_dir / "manifest.json"),
                    "parent_oracle_sha256": digest(fuzzy_dir / "oracle-results.jsonl"),
                    "configurations": CONFIGURATIONS,
                    "default_config": DEFAULT,
                    "new_detector_calls": calls,
                    "reused_previous_pilot_outputs": sum(
                        c["group"] == "fuzzy" and (c["case_id"], name) in reusable
                        for c in cases
                        for name in CONFIGURATIONS
                    ),
                    "previous_pilot_manifest_sha256": digest(reuse_run / "manifest.json")
                    if reuse_run
                    else None,
                    "historical_benchmarks_rerun": False,
                    "environment": {
                        "python": platform.python_version(),
                        "rapidfuzz": version("rapidfuzz"),
                        "marisa-trie": version("marisa-trie"),
                    },
                    "code_and_lock": fingerprint(),
                    "human_review_approved": False,
                    "artifacts": {p.name: digest(p) for p in sorted(temporary.iterdir())},
                }
            )
        )
    return review["workload"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("freeze")
    p.add_argument("--profile", choices=("50", "55"), default="50")
    p.add_argument("--dataset-dir", type=Path, default=Path("data/phase6-inputs"))
    p.add_argument("--fuzzy-dir", type=Path, default=Path("data/phase4-final"))
    p.add_argument("--index-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p = sub.add_parser("capture")
    p.add_argument("--reuse-inputs", type=Path)
    p.add_argument("--reuse-run", type=Path)
    p.add_argument("--inputs-dir", type=Path, required=True)
    p.add_argument("--run-dir", type=Path, default=Path("data/phase6-review-ready"))
    p.add_argument("--fuzzy-dir", type=Path, default=Path("data/phase4-final"))
    p.add_argument("--index-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    for command in ("check", "metrics"):
        p = sub.add_parser(command)
        p.add_argument("--inputs-dir", type=Path, required=True)
        p.add_argument("--run-dir", type=Path, required=True)
        p.add_argument("--progress", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "freeze":
        result = freeze(
            args.dataset_dir, args.fuzzy_dir, args.index_dir, args.output_dir, profile=args.profile
        )
    elif args.command == "capture":
        result = capture(
            args.inputs_dir,
            args.run_dir,
            args.fuzzy_dir,
            args.index_dir,
            args.output_dir,
            reuse_inputs=args.reuse_inputs,
            reuse_run=args.reuse_run,
        )
    else:
        from .pilot_review import PilotSession, metrics

        session = PilotSession(args.inputs_dir, args.run_dir, args.progress)
        result = session.validate(session.progress) if args.command == "check" else metrics(session)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == "__main__":
    main()
