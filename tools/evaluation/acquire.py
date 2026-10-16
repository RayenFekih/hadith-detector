"""Explicit network acquisition; every later operation uses frozen local files."""

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from tools.exact_benchmark.corpus import canonical, digest


class Paragraphs(HTMLParser):
    """Extract paragraph text, excluding non-content tags and reference superscripts."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.current = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "sup"):
            self.skip += 1
        if tag == "p" and self.current is None and not self.skip:
            self.current = []
        if tag == "br" and self.current is not None and not self.skip:
            self.current.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "sup"):
            self.skip = max(0, self.skip - 1)
        if tag == "p" and self.current is not None:
            self.items.append("".join(self.current))
            self.current = None

    def handle_data(self, text):
        if self.current is not None and not self.skip:
            self.current.append(text)


def request(host, parameters):
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(
        {**parameters, "format": "json", "formatversion": 2}
    )
    headers = {"User-Agent": "HadithDetectorEvaluation/0.1 (github.com/RayenFekih/hadith-detector)"}
    for attempt in range(4):
        time.sleep(2)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers=headers), timeout=30
            ) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as error:
            if error.code not in (429, 502, 503, 504) or attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    if "error" in payload:
        raise ValueError(payload["error"])
    return payload


def fetch(selection: Path, output: Path):
    """Capture page revision IDs first, then fetch those exact revisions."""
    output.mkdir(parents=True, exist_ok=False)
    spec = json.loads(selection.read_text(encoding="utf-8"))
    sources = []
    pages = spec.get("sources", spec.get("pages"))
    if not pages:
        raise ValueError("Source specification has no pages")
    for i, page in enumerate(pages, 1):
        host, title = page["host"], page["title"]
        revision = page.get("revision")
        if revision is None:
            query = request(
                host,
                {
                    "action": "query",
                    "titles": title,
                    "prop": "revisions",
                    "rvprop": "ids",
                    "redirects": 1,
                },
            )
            revision = query["query"]["pages"][0]["revisions"][0]["revid"]
        payload = request(host, {"action": "parse", "oldid": revision, "prop": "text|revid"})
        if payload["parse"]["revid"] != revision:
            raise ValueError("Revision changed while acquiring")
        name = f"page-{i:02d}.json"
        (output / name).write_bytes(canonical(payload))
        if page.get("snapshot_sha256") and digest(output / name) != page["snapshot_sha256"]:
            raise ValueError("Pinned HTML rendering changed; retain the archived snapshot")
        parser = Paragraphs()
        parser.feed(payload["parse"]["text"])
        parser.close()
        text = "\n\n".join(parser.items)
        selected = []
        cursor = 0
        for ordinal, paragraph in enumerate(parser.items):
            a, b = cursor, cursor + len(paragraph)
            cursor = b + 2
            eligible = 120 <= len(paragraph) <= 2200 and 20 <= len(paragraph.split()) <= 260
            if page["stratum"] == "quotation_rich":
                eligible = eligible and bool(re.search(r"ﷺ|رسول الله|النبي", paragraph))
            if eligible and len(selected) < page["count"]:
                selected.append({"paragraph": ordinal, "start": a, "end": b})
        if len(selected) != page["count"]:
            raise ValueError(f"Insufficient eligible paragraphs in {title}: {len(selected)}")
        sources.append(
            {
                **page,
                "revision": revision,
                "snapshot": name,
                "snapshot_sha256": digest(output / name),
                "selected": selected,
                "plain_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "url": f"https://{host}/w/index.php?oldid={revision}",
                "history_url": f"https://{host}/w/index.php?"
                + urllib.parse.urlencode({"title": title, "action": "history"}),
                "reuse": page.get("reuse", spec.get("reuse")),
            }
        )
        print(f"Frozen page {i}: revision {revision}, {len(selected)} paragraphs", flush=True)
    lock = {
        "version": 1,
        "selection_sha256": digest(selection),
        "selection": spec["selection"],
        "sources": sources,
    }
    (output / "sources.lock.json").write_bytes(canonical(lock))
    return lock
