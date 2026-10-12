"""Versioned Arabic matching tokens with spans in the unchanged input.

Tokens sharing a span form an indivisible symbol expansion. Matching must start
and finish at complete expansion boundaries and never cross segment identifiers.
"""

import unicodedata
from dataclasses import dataclass

NORMALIZATION_VERSION = 1
_LETTERS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ی": "ي"})
_IGNORED = frozenset(
    "\u061c\u200c\u200d\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)


@dataclass(frozen=True)
class Token:
    term: str
    start: int
    end: int
    segment: int


@dataclass(frozen=True)
class TextWarning:
    kind: str
    start: int
    end: int
    codepoint: str


@dataclass(frozen=True)
class Tokenization:
    tokens: tuple[Token, ...]
    warnings: tuple[TextWarning, ...]


def _arabic(character: str) -> bool:
    return "ARABIC" in unicodedata.name(character, "")


def tokenize(text: str) -> Tokenization:
    """Normalize written Arabic words, preserving barriers and original spans.

    Compatibility normalization runs on base/combining-mark clusters, so composed
    hamza letters remain distinct before the explicitly selected letter mappings.
    Punctuation separates terms; unsupported characters additionally split segments.
    """
    tokens: list[Token] = []
    warnings: list[TextWarning] = []
    word: list[str] = []
    start = end = segment = 0

    def flush() -> None:
        if word:
            tokens.append(Token("".join(word), start, end, segment))
            word.clear()

    index = 0
    while index < len(text):
        character = text[index]
        stop = index + 1
        if unicodedata.category(character).startswith("M"):
            if word and _arabic(character):
                end = stop
            else:
                warnings.append(TextWarning("orphan_mark", index, stop, f"U+{ord(character):04X}"))
                if not _arabic(character):
                    flush()
                    segment += 1
            index = stop
            continue
        if character == "ـ" or character in _IGNORED:
            if word:
                end = stop
            index = stop
            continue
        if _arabic(character):
            while stop < len(text) and unicodedata.category(text[stop]).startswith("M"):
                if not _arabic(text[stop]):
                    break
                stop += 1
        normalized = unicodedata.normalize("NFKC", text[index:stop]).translate(_LETTERS)
        normalized = "".join(
            c
            for c in normalized
            if not (_arabic(c) and unicodedata.category(c).startswith("M")) and c != "ـ"
        )
        # Multiword ligatures are independent units, with one original span per
        # expanded word. Do not merge a neighbouring word into a partial expansion.
        pieces = normalized.split()
        if len(pieces) > 1 and all(
            all(_arabic(c) and unicodedata.category(c).startswith("L") for c in p) for p in pieces
        ):
            flush()
            tokens.extend(Token(p, index, stop, segment) for p in pieces)
        else:
            for c in normalized:
                if _arabic(c) and unicodedata.category(c).startswith("L"):
                    if not word:
                        start = index
                    word.append(c)
                    end = stop
                elif c.isspace() or unicodedata.category(c).startswith("P"):
                    flush()
                else:
                    flush()
                    segment += 1
                    kind = (
                        "replacement_character" if character == "\ufffd" else "unexpected_character"
                    )
                    warning = TextWarning(kind, index, stop, f"U+{ord(character):04X}")
                    if not warnings or warnings[-1] != warning:
                        warnings.append(warning)
        index = stop
    flush()
    if not text:
        warnings.append(TextWarning("empty_text", 0, 0, ""))
    return Tokenization(tuple(tokens), tuple(warnings))
