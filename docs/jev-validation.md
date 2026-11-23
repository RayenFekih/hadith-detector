# Optional Jev contextual validation

The default detector works offline and uses no validation API. Set
`validation_model="jev"` to ask Jev whether each detected input span is being used
as a Hadith quotation in its surrounding paragraph. Implicit quotations count;
shared wording, blessings, narrator formulas and Quran-only uses may be rejected.
The deterministic matcher still finds all candidates and supporting sources.

No additional dependency is needed. The integration uses uncompressed HTTPS JSON
with the Jev System One API. It does not use a chat-completions API.

## Enable and configure

```python
import os
from hadith_detector import HadithDetector

detector = HadithDetector(
    validation_model="jev",
    validation_api_key=os.environ["TYPESAFE_API_KEY"],
    validation_threshold=0.5,
)
text = "ورد في النص: إنما الأعمال بالنيات وإنما لكل امرئ ما نوى"
matches = detector.detect(text)
for match in matches:
    print(match.text, match.validation.quotation_score, match.validation.decision)
    print(match.to_dict())
```

The keyword-only validation settings are:

| Setting | Default | Meaning |
| --- | --- | --- |
| `validation_model` | `None` | Disabled; `"jev"` requests `"jev-latest"`. Explicit `jev-latest`, `jev-1.14.0` and `jev-1.13.0` names are also supported. Other models are rejected. |
| `validation_api_key` | `None` | Explicit provider key. For the default TypeSafe endpoint only, an omitted key uses `TYPESAFE_API_KEY`. |
| `validation_api_base` | `None` | Default `https://api.typesafe.ai/v1`. Supply another compatible HTTPS root ending in `/v1`; `/systemone` is appended. |
| `validation_threshold` | `0.5` | Finite number from 0 to 1. A score equal to the threshold is kept. |

These settings also work with `HadithDetector.from_directory()` and the module-level
`detect()` and `annotate()` functions. They are separate from `DetectorConfig`,
which continues to control only matching. Invalid configuration raises `ValueError`.
The library does not load `.env` files. Load your environment through your own
application or secret manager. Never put a real key in source code.

For TunAI, pass its key and endpoint explicitly:

```python
detector = HadithDetector(
    validation_model="jev",
    validation_api_key=os.environ["TUNAI_API_KEY"],
    validation_api_base="https://api.tunai.tn/v1",
)
```

A custom endpoint never inherits `TYPESAFE_API_KEY`. Keys are not sent through
redirects. Changing providers does not enable arbitrary models. The optional MCP
server continues using the offline detector; these options are Python API settings.

## `detect()`: filter whole spans

Each unique `(start, end)` span is evaluated once within a call. Multiple supporting
references do not create multiple validation questions. A rejection removes the
whole detection and all its references. Accepted detections retain their original
text, offsets, word counts, edit/omission costs, references, occurrences and traces.
They receive a frozen `QuotationValidation` value in `detection.validation`.

`quotation_score` is the actual numerical `noul` answer returned by Jev, without
rounding or another confidence calculation. Higher values favor contextual quotation
use. It is not Hadith authenticity, reference correctness, textual similarity, or
an established calibrated probability of correctness.

Illustrative validation portion of `detection.to_dict()`; the score is an example:

```json
{
  "validation": {
    "model": "jev-1.14.0",
    "quotation_score": 0.92,
    "threshold": 0.5,
    "decision": "keep"
  }
}
```

`model` records the returned model name when validation succeeds. The metadata
round-trips through `Detection.from_dict()` and `QuotationValidation.from_dict()`.
With validation disabled, `.validation` is `None` and `to_dict()` omits the
`validation` key, preserving the previous dictionary shape.

## `annotate()`: inspect every candidate

`annotate()` still returns an escaped HTML fragment. With Jev enabled, it highlights
**all original candidates**, including rejected and unavailable-score candidates.
Each `<mark>` keeps its existing attributes and adds `data-validation` containing
HTML-escaped JSON with the model, score, threshold and decision. It does not insert
scripts or change the input text. With Jev disabled, its markup is unchanged.

```python
import json
from html.parser import HTMLParser

class ValidationMarks(HTMLParser):
    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "mark" and "data-validation" in attributes:
            # HTMLParser already decodes attribute entities.
            metadata = json.loads(attributes["data-validation"])
            print(attributes["data-start"], attributes["data-end"], metadata)

html = detector.annotate(text)
ValidationMarks().feed(html)
```

You can apply another threshold to the saved scores without another API request.
An unavailable score remains unknown; never convert it to zero. HTML contains span
metadata and reference counts, not full source records, as before. The returned
detection objects from `detect()` provide full references for retained spans.

Calling `detect()` and then `annotate()` validates twice. There is no cross-call
score cache; results can vary across requests. Keep the returned HTML if you want
to analyze its candidates without making another call.

## Unavailable scores and operational costs

API errors, timeouts and malformed or missing scores preserve the affected
candidates in both functions. The warning category is `ContextualValidationWarning`.
Their metadata distinguishes failure from a low score:

```json
{
  "validation": {
    "model": "jev-latest",
    "quotation_score": null,
    "threshold": 0.5,
    "decision": "unavailable",
    "error": "timeout"
  }
}
```

Other error codes are `api_error`, `invalid_response` and `request_error`. Metadata
and warnings do not include keys, input passages or raw provider error bodies. A
malformed batch is unavailable as a unit: its candidates are retained without
scores even if some answer fields were present. Other batches can still succeed.
An unexpected or mismatched model response is also unavailable, not a rejection.

Candidates sharing paragraph context are batched, with up to 20 questions per
request. Complete candidate spans are preserved even when they cross paragraph
boundaries. No request is made when matching finds no candidates. Each batch has
a 30-second operation budget and at most two retries for rate limits or temporary
server errors. Authentication and malformed-request failures are not retried.
Socket operations have bounded timeouts; a call containing many batches can take
longer overall. Oversized contexts can fail validation and are retained as unavailable.

Jev requires an external API. Relevant input paragraphs and candidate markers are
sent to the configured provider; supporting source records are not sent. Validation
adds network latency and usage charges. Check your provider's pricing and data
handling terms. No spending limits or automatic provider fallback are implemented.

Matching and source lookup remain protected by the instance's resource lock.
Network validation and enabled HTML rendering run outside that lock, so independent
calls can overlap their network requests. Convenience functions reuse the offline
matcher cache but keep provider credentials and validation state local to each call.
Use a long-lived detector instance to retain its matching resources.
