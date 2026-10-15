"""Three offline examples; pass the path to your already built v2 resources."""

import argparse
import json

from hadith_detector import Detection, DetectorConfig, HadithDetector, clear_cache, detect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index_dir")
    args = parser.parse_args()
    detector = HadithDetector(args.index_dir, DetectorConfig(min_match_words=8, max_errors=1))

    # 1. Exact detection, overriding the configured error budget with zero.
    text = "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى"
    exact = detector.detect(text, max_errors=0)
    print("Exact identities:", [r.record.hadith_key for m in exact for r in m.references])

    # 2. A spelling edit, inheriting the configured budget.
    fuzzy = detector.detect("إنما الأعمال بالنياث وإنما لكل امرئ ما نوى")
    print("Fuzzy costs:", [(m.errors, m.missing_words) for m in fuzzy])

    # 3. Convenience caching, simultaneous budgets and JSON restoration.
    combined = detect(
        "إنما الأعمال بالنياث لكل امرئ ما نوى",
        index_dir=detector.index_dir,
        config=DetectorConfig(min_match_words=7, max_errors=1, max_missing_words=1),
    )
    for match in combined:
        restored = Detection.from_dict(json.loads(json.dumps(match.to_dict())))
        assert restored == match
        print("Combined costs:", (match.errors, match.missing_words))
    print("Escaped annotation:", detector.annotate("<script>literal text</script> " + text))
    clear_cache()


if __name__ == "__main__":
    main()
