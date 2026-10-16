"""Prepare provisional evaluation evidence; no command approves gold or quality scores."""

import argparse
import json
from pathlib import Path

from .acquire import fetch
from .dataset import freeze
from .pipeline import check_review, replay, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    acquire = commands.add_parser("fetch")
    acquire.add_argument("--selection", type=Path, default=Path(__file__).with_name("sources.json"))
    acquire.add_argument("--output-dir", type=Path, required=True)
    prepare = commands.add_parser("freeze")
    prepare.add_argument("--legacy-csv", type=Path, required=True)
    prepare.add_argument("--source-dir", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    execute = commands.add_parser("run")
    execute.add_argument("--dataset-dir", type=Path, required=True)
    execute.add_argument("--index-dir", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    again = commands.add_parser("replay")
    again.add_argument("--dataset-dir", type=Path, required=True)
    again.add_argument("--run-dir", type=Path, required=True)
    again.add_argument("--output-dir", type=Path, required=True)
    again.add_argument(
        "--refresh-review",
        action="store_true",
        help="Export updated review layout without detecting again",
    )
    review = commands.add_parser("check-review")
    review.add_argument("--dataset-dir", type=Path, required=True)
    review.add_argument("--run-dir", type=Path, required=True)
    review.add_argument("--review-csv", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch":
        fetch(args.selection, args.output_dir)
    elif args.command == "freeze":
        freeze(args.legacy_csv, args.source_dir, args.output_dir)
    elif args.command == "run":
        print(json.dumps(run(args.dataset_dir, args.index_dir, args.output_dir), ensure_ascii=True))
    elif args.command == "replay":
        print(
            replay(
                args.dataset_dir, args.run_dir, args.output_dir, refresh_review=args.refresh_review
            )
        )
    else:
        print(check_review(args.dataset_dir, args.run_dir, args.review_csv))


if __name__ == "__main__":
    main()
