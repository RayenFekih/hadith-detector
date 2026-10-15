"""Independent HTML parsing checks for offline installed-library validation."""

from html.parser import HTMLParser


class Fragment(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.marks = []
        self.current = None
        self.feed(html)
        self.close()
        assert self.current is None

    def handle_starttag(self, tag, attrs):
        assert tag == "mark" and self.current is None
        assert len(attrs) == 7
        attributes = dict(attrs)
        assert attributes.pop("class") == "hadith-match"
        assert set(attributes) == {
            "data-match-index",
            "data-start",
            "data-end",
            "data-errors",
            "data-missing-words",
            "data-reference-count",
        }
        assert all(value.isascii() and value.isdecimal() for value in attributes.values())
        self.current = {"attrs": attributes, "text": []}

    def handle_endtag(self, tag):
        assert tag == "mark" and self.current is not None
        self.marks.append(self.current)
        self.current = None

    def handle_data(self, data):
        self.text.append(data)
        if self.current is not None:
            self.current["text"].append(data)

    def handle_comment(self, data):
        raise AssertionError("Unexpected HTML comment")

    def handle_decl(self, decl):
        raise AssertionError("Unexpected declaration")


def assert_annotation(html, text, matches):
    parsed = Fragment(html)
    assert "".join(parsed.text) == text
    assert len(parsed.marks) == len(matches)
    for index, (mark, match) in enumerate(zip(parsed.marks, matches, strict=True)):
        assert "".join(mark["text"]) == text[match.start : match.end] == match.text
        assert mark["attrs"] == {
            "data-match-index": str(index),
            "data-start": str(match.start),
            "data-end": str(match.end),
            "data-errors": str(match.errors),
            "data-missing-words": str(match.missing_words),
            "data-reference-count": str(len(match.references)),
        }
