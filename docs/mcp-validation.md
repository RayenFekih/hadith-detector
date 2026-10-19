# MCP implementation validation

Validated locally on 2026-10-19 with Windows 11, Python 3.14.6, uv 0.11.26,
and the official MCP SDK 1.30.0. These checks do not publish anything.

## Automated checks

```bash
uv sync --locked --extra mcp
uv run --frozen --extra mcp pytest -p no:cacheprovider
uv run --frozen --extra mcp ruff check .
uv run --frozen --extra mcp ruff format --check .
uv run --frozen --extra mcp mypy src/hadith_detector
```

- Full suite: 266 passed, 9 skipped. Skips require optional data, benchmark, or
  interactive research dependencies; none of the MCP checks were skipped.
- MCP session checks: 24 passed, covering discovery, input/output schemas,
  validation and error recovery, source retrieval, Arabic and emoji offsets,
  annotation fidelity, exact/edit/omission evidence, all three pagination levels,
  per-call configuration isolation, lazy resource reuse, and missing-extra behavior.
- Packaging checks: 5 passed. Both the checkout wheel and the wheel rebuilt from
  an sdist were installed in clean environments. Base installs exclude MCP and
  Pydantic, preserve normal Python operations, and give a useful CLI installation
  hint. MCP installs run real SDK stdio sessions through both launch commands and
  the documented client configuration. These routine tests use synthetic corpora.
- Ruff lint, Ruff formatting, strict mypy, and `git diff --check` passed.

CI now runs MCP and clean-install checks on its existing Python 3.11–3.14 matrix
and Windows job. Those remote jobs have not been executed as part of this local
validation. The actual Claude Desktop UI was not tested; the supplied configuration
was exercised with the official SDK's stdio client.

## Full corpus distribution

```bash
uv build --no-sources --out-dir dist/mcp-validation
python -m twine check dist/mcp-validation/*
```

The existing approved corpus passed the build guard. Both the source archive and
the wheel built from that archive passed Twine checks. Local artifacts are in
`dist/mcp-validation/` (ignored by Git).

For an additional production check, dependencies were prepared in a separate
environment. The full wheel was then installed into two fresh environments using
`uv pip install --offline`, first normally and then with `[mcp]`. Both environments
verified all 14,940 bundled records, detection offsets, source retrieval, and HTML
annotation while Python socket creation was blocked for those library operations.
Imports resolved to each clean environment's installed package.

The MCP environment also passed complete stdio sessions launched with:

1. The example client JSON, substituting its installed interpreter path.
2. The installed `hadith-detector-mcp` executable.
3. The module command with an audit hook rejecting external socket connections
   and external DNS lookups (local event-loop plumbing remained allowed).

Each session initialized, discovered tools, validated all three result schemas,
detected Arabic wording after an emoji, annotated it, retrieved `bukhari:1`,
handled an invalid identifier, and continued successfully. These runtime checks
used the packaged full corpus, outside the source checkout's import path.
Preparation/builds may access the network; library/server operation requires none.

## Limits

The matching algorithms, public API, and default budgets are unchanged. Pagination
limits output only and repeats full matching on each call; it does not bound CPU
time. Annotation remains complete and can be large. Results describe candidate
textual evidence, with no contextual quotation decision or authenticity grading.
See [the MCP guide](mcp.md) for usage and interpretation requirements.
