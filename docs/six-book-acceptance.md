# Six Books release acceptance

The Arabic Parquet files verified at QuranLab revision
`cc6972dae1f46f5f5e2b65e877d24c4539bc4391`. Counts below use distinct records
per grader and retain each grader's source spelling.

| Collection | Total | With grades | Without grades | Records by attributed grader |
|---|---:|---:|---:|---|
| Abu Dawud | 5,272 | 5,272 | 0 | Al-Albani 5,250, Zubair Ali Zai 5,224, Muhammad Muhyi Al-Din Abdul Hamid 5,169, Shuaib Al Arnaut 3,170 |
| Ibn Majah | 4,338 | 4,336 | 2 | Zubair Ali Zai 4,319, Muhammad Fouad Abd al-Baqi 4,309, Al-Albani 4,303, Shuaib Al Arnaut 3,239 |
| Al-Nasa’i | 5,679 | 5,672 | 7 | Al-Albani 5,641, Zubair Ali Zai 5,626, Abu Ghuddah 5,609 |
| Al-Tirmidhi | 3,924 | 3,889 | 35 | Zubair Ali Zai 3,864, Al-Albani 3,731, Ahmad Muhammad Shakir 3,667, Bashar Awad Maarouf 2,384 |

No blank labels or grader names, repeated grader names within a record, grade count
mismatches, or discrepancies between the supplied summaries and grade lists were
found. All grade fields are retained as supplied.

## Redistribution review

The review covered the Arabic text, references, grader names and labels, grade
counts and summaries, and the derived index. All six pinned configuration rows
attribute the Arabic compilation to hadith-api and identify the classical Arabic
text as public domain. The bundled Unlicense records the upstream compilation's
terms. The broader QuranLab license summary mentions Open-Hadith-Data, while
QuranLab's source notice associates that upstream with Ahmad and al-Darimi.
The six configurations and their references are pinned, and the original notices
are retained. [Bundled provenance](../tools/bundle-notices/PROVENANCE.md)

**Publication decision pending.** The four newly bundled Arabic Parquet files
carry attributed grades and lack a per-row license field. The pinned notices do
not establish the redistribution basis for each grader's annotations. This
affects `grades` and the summaries derived from those labels. Before publishing,
the maintainer must record the basis for redistributing these fields for all
four collections, with supporting evidence. If the evidence cannot be established,
hold the release and agree on a revised bundle before rebuilding and retesting.
The implementation and smoke-test approval covers the candidate's behavior.

## Performance gates

Use clean wheel installs on the same host and Python version. Run
`tools/release_performance.py --cases tools/release-cases.json` in the v0.3.0
and v0.4.0 environments and repeat with `--two-books` in v0.4.0. Use fresh
processes and compare median results across three runs per mode.

| Metric | v0.4.0 limit relative to v0.3.0 |
|---|---|
| Cold initialization and peak RSS | 2.5× in both modes |
| Warm exact p95 | 1.25× filtered, 2.0× all six |
| Warm fuzzy p95 | 1.25× filtered, 2.5× all six |
| Wheel and sdist | Under 60 MB each |

Preserve the v0.3.0 artifacts and baseline reports. Release approval requires
recorded test results and either passing gates or explicit maintainer acceptance
of the measured trade-offs.
