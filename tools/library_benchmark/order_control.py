"""Control whether container gains come from sorted verification order, not the library."""

import argparse
from pathlib import Path

import hadith_detector.detector as runtime
from hadith_detector._fuzzy import FuzzyMatcher
from tools.library_benchmark.__main__ import worker


class OrderedMatcher(FuzzyMatcher):
    def starts(self, *args):
        return sorted(super().starts(*args))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime.FuzzyMatcher = OrderedMatcher
    worker("sorted", args.index_dir, args.output_dir)
