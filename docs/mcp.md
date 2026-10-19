# Use Hadith Detector with an AI assistant

Model Context Protocol (MCP) lets an assistant discover and call tools in a local
program. Hadith Detector exposes its existing Python functionality through the
official Python MCP SDK. The server runs on your computer and communicates over
standard input/output (stdio). It needs no account, hosting, API keys, or network
connection after installation. Your MCP client may separately use an online model;
consult that client's privacy settings before sending sensitive documents.

## Install and start

Regular Python users still install only the matching library:

```bash
pip install hadith-detector
```

For MCP, install the optional extra in a Python 3.11+ environment:

```bash
python -m venv .venv
# Activate the environment using your platform's activation command.
python -m pip install "hadith-detector[mcp]"
hadith-detector-mcp
```

The equivalent module command is `python -m hadith_detector.mcp`. The process waits
for MCP messages; it is not an interactive text prompt. Normally the client starts
and stops it for you. Diagnostics go to stderr; stdout is reserved for protocol
messages. No HTTP server or listening port is started.

The extra uses `mcp>=1.30,<2`, the official SDK's
[supported 1.x maintenance line](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x).
The upper bound avoids automatic migration to the incompatible SDK 2.x API.
Neither MCP nor Pydantic is required by the base installation, and importing
`hadith_detector` does not import them. An attempt to start the CLI without the
extra prints an installation hint to stderr and exits unsuccessfully.

The packaged Sahih al-Bukhari / Sahih Muslim records and prebuilt index are reused.
One detector is loaded lazily per server process and reused across tools. Discovery
does not load the corpus. No matching, indexing, normalization, or search algorithm
has been added or changed.

## Connect a client

For Claude Desktop, merge this into `claude_desktop_config.json` (open it through
the client's developer settings), then restart the client:

```json
{
  "mcpServers": {
    "hadith-detector": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["-m", "hadith_detector.mcp"]
    }
  }
}
```

Use the absolute path to the Python interpreter where you installed the extra.
On Windows, a JSON path looks like
`"C:\\projects\\hadith\\.venv\\Scripts\\python.exe"`. Keep the `args` array as
shown; do not add shell quotes around individual arguments. You can instead set
`command` to the absolute path of `hadith-detector-mcp` (Windows: `.exe`) and use
`"args": []`. Installing from PyPI at client startup is unnecessary and would
make startup depend on network access.

The [example configuration](../examples/mcp-client.json) is exercised in automated
tests using the official SDK's stdio client against clean wheel installations,
after substituting the installed interpreter path. The actual Claude Desktop UI
is not part of that automated test. See the
[official local server guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
for client configuration details.

## Tools and inputs

All three tools are read-only and operate only on local bundled data. Successful
results include MCP `structuredContent` and a JSON text representation for clients
that read text content. Tool discovery publishes input and output JSON schemas.

| Tool | Required arguments | Optional arguments | Result |
| --- | --- | --- | --- |
| `detect_hadith` | `text`: original string | `config`, pagination below | Candidate spans and source evidence |
| `annotate_hadith` | `text`: original plain-text string | `config` | `original_text`, escaped `html`, effective `config`, interpretation |
| `get_hadith` | `hadith_key`: bundled identity, e.g. `bukhari:1` | None | `record`: complete original source dictionary |

`config` is an optional object with the library's unchanged defaults:

| Field | Default | Validation |
| --- | ---: | --- |
| `min_match_words` | 5 | Integer >= 1 |
| `max_errors` | 0 | Integer >= 0; total character-edit budget |
| `max_missing_words` | 0 | Integer >= 0; internal source-word omission budget |

Unknown configuration fields, booleans, fractional values, and strings used as
integers are rejected. `null` config uses the defaults. Per-call config does not
change subsequent calls. Tune these settings on representative project data;
short generic phrases and permissive budgets can produce many incidental matches
and increase processing time.

Example tool arguments:

```json
{
  "text": "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى",
  "config": {"min_match_words": 5, "max_errors": 0, "max_missing_words": 0},
  "reference_limit": 3
}
```

Every detection contains `start`, `end`, the exact input substring `text`,
`matched_words`, the best supporting `errors` and `missing_words`, `match_kind`,
and `references`. `match_kind` is `normalized_exact` when both best costs are zero,
otherwise `approximate`. Exact after Arabic normalization does not imply identical
raw spelling. References for one detection can have different costs: inspect each
occurrence's own `errors`, `missing_words`, `alignment`, and
`omitted_source_tokens`, even if the detection's best match is exact.

Each compact reference includes `hadith_key`, `collection`, `hadith_number`,
`sunnah_url` (possibly null), and the original `occurrences`. Occurrences preserve
the public API's source substring, source offsets, token alignment, omission
evidence, and costs. Full records are fetched with `get_hadith` instead of repeated
inside every detection. Keys use **collection:sequence**, which is not necessarily
the printed Hadith number; copy returned keys rather than constructing citations
from printed numbers. Unknown or malformed keys produce an MCP tool error
(`isError: true`), as do invalid configurations and unsupported annotation input.

This complete representative response is returned for `detect_hadith` with
`{"text": ""}` (empty text is valid):

```json
{
  "interpretation": "candidate_textual_matches",
  "config": {"min_match_words": 5, "max_errors": 0, "max_missing_words": 0},
  "matches": [],
  "total_matches": 0,
  "next_match_offset": null,
  "truncated": false
}
```

For `annotate_hadith` with `{"text": ""}`, the response is:

```json
{
  "interpretation": "candidate_textual_matches",
  "original_text": "",
  "html": "",
  "config": {"min_match_words": 5, "max_errors": 0, "max_missing_words": 0}
}
```

Retrieval returns `{"record": {...}}` with exactly the dictionary produced by the
public `HadithRecord.to_dict()` API: original text, identifiers, source metadata,
and supplied grade fields. See [the public API](public-api.md) for record fields.
Grade metadata is preserved dataset content, not a grading decision by this tool.

For a nonempty example, detecting
`🙂 إنما الأعمال بالنيات وإنما لكل امرئ ما نوى` with default configuration produces
one match supported by `bukhari:1` in the current bundle. These are selected fields
from that match (the full response also includes the reference and occurrence evidence):

```json
{
  "start": 2,
  "end": 44,
  "text": "إنما الأعمال بالنيات وإنما لكل امرئ ما نوى",
  "matched_words": 8,
  "errors": 0,
  "missing_words": 0,
  "match_kind": "normalized_exact"
}
```

### Offsets and HTML

All offsets are **zero-based Python Unicode character indices**, with inclusive
start and exclusive end. `text[start:end]` always reproduces the detected text;
source occurrence offsets similarly index the retrieved record's `text`. Neither
input nor source wording is transformed by this adapter. Offsets are not UTF-8
byte positions or JavaScript UTF-16 indices: take care with emoji and other
characters outside the BMP. Arabic diacritics count as separate characters.

Annotation uses the existing `annotate()` API and returns the original input plus
a complete escaped HTML fragment. `<mark>` attributes `data-start` and `data-end`
refer to the **original input**, not positions in the HTML. HTML markup in input is
escaped as literal text. Annotation rejects NUL and lone surrogates because HTML
cannot preserve them losslessly. See [HTML annotation](html-annotation.md).

### Pagination and performance

| Detection argument | Default | Allowed values |
| --- | ---: | --- |
| `match_offset` | 0 | Integer >= 0 |
| `match_limit` | 20 | Integer 1–100 |
| `reference_offset` | 0 | Integer >= 0 |
| `reference_limit` | 10 | Integer 1–100 |
| `occurrence_offset` | 0 | Integer >= 0 |
| `occurrence_limit` | 5 | Integer 1–100 |

Responses report `total_matches` and `next_match_offset`; each match reports
`total_references` and `next_reference_offset`; each reference reports
`total_occurrences` and `next_occurrence_offset`. A next offset is null at the end.
`truncated` is true whenever a page omits evidence, including earlier pages.
An offset beyond the total returns an empty page. No candidate is silently filtered.

Repeat the same text/config with the returned offsets. Reference offsets apply
independently to **every match on the current page**, and occurrence offsets to
**every reference**. To inspect one match's references without skipping another's,
set `match_limit: 1` and select its `match_offset`; for one reference's occurrences,
also set `reference_limit: 1` and its `reference_offset`. Reset inner offsets to
zero when moving to a new match or reference. This allows all references and
occurrences to be inspected, including generic phrases with many supporting records.

Pagination limits serialization only: detection still computes the full result on
each request. There is no result cache or computation deadline. Annotation returns
the complete HTML, so long documents may produce large responses. Split documents
at application-appropriate boundaries if needed, recording chunk positions so your
application can translate offsets back to the complete document.

## Interpret matches responsibly

A textual match is a **candidate**, not proof of intentional quotation, meaning,
authenticity, or scholarly grading. Inspect surrounding context and retrieve source
records before presenting citations. Distinguish actual Hadith wording from
narrator chains, generic religious expressions, Quranic wording embedded in
narrations, blessings, and paraphrases. Explain wording differences and preserve
uncertainty when review is inconclusive. No detection does not prove absence:
coverage is limited to the bundled Sahihayn corpus and the configured thresholds.
Qualified human review remains necessary for religious and consequential uses.

The server conveys these limits in initialization instructions, tool descriptions,
and candidate labels, and returns evidence for review. Instructions alone cannot
guarantee that an assistant interprets a match correctly.

Example workflows:

- **Editorial review:** locate candidates in a document draft, retrieve source
  records, compare wording, and route proposed citations to a qualified reviewer.
- **Research workflows:** add candidate Hadith evidence to retrieved passages,
  then inspect the supporting records through key-based retrieval.
- **Document summarization:** inspect matching passages and surrounding context
  before attributing wording in a summary. Preserve uncertainty and avoid turning a
  match into an authenticity claim.
- **RAG data preprocessing:** annotate source chunks with original offsets,
  configuration, candidate evidence, and stable keys; retrieve and review supporting
  records before treating those annotations as confirmed citation labels.

## Development checks

```bash
uv sync --locked --extra mcp
uv run --frozen --extra mcp pytest
uv run --frozen --extra mcp ruff check .
uv run --frozen --extra mcp ruff format --check .
uv run --frozen --extra mcp mypy src/hadith_detector
```

MCP tests use actual SDK sessions for discovery, schema validation, Arabic offsets,
annotation, exact/fuzzy evidence, validation errors, recovery, and pagination.
Packaging tests build synthetic wheels from both checkout and sdist, verify base
installations exclude optional dependencies, then install the MCP extra in clean
environments and exercise both CLI and module startup over stdio. Dependency
preparation can use the network; running the tools does not require it.
