"""
normalize.py

Text normalisation for the Stage 2 page-aware pipeline. Replaces the Stage 1
approach of deleting every non-ASCII character (text_cleaner.sanitize_text),
which destroyed ligatures ("Profiles" -> "Pro les", "flew" -> "ew") and
apostrophes ("Earthʼs" -> "Earth s").

Order matters:
  1. NFKC — expands compatibility characters such as the "ﬁ"/"ﬂ" ligatures.
  2. Soft hyphens — a word split across lines with U+00AD is re-joined.
  3. Typographic punctuation mapped to ASCII equivalents (apostrophes, quotes,
     dashes, ellipsis, bullets) so lexical retrieval matches plain queries.
  4. Line handling inside a text block — "word-\nword" keeps the hyphen and
     joins (O-ring, self-test); other line breaks become spaces.
Non-ASCII letters and symbols that carry meaning (°, ±, Greek letters, é) are
KEPT. The Stage 1 cleaner is left untouched so baseline B4 stays reproducible.
"""

import re
import unicodedata

_PUNCT_MAP = str.maketrans({
    "ʼ": "'", "’": "'", "‘": "'", "‛": "'", "′": "'", "´": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "•": "-", "●": "-", "◦": "-", "▪": "-", "‣": "-",
    " ": " ", " ": " ", " ": " ", " ": " ",
    "​": "", "﻿": "",
})
_SOFT_HYPHEN_BREAK = re.compile(r"­[ \t]*\n[ \t]*")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HARD_HYPHEN_BREAK = re.compile(r"([A-Za-z0-9]+)-[ \t]*\n[ \t]*([A-Za-z0-9]+)")

try:
    from wordfreq import zipf_frequency
except ImportError:  # without a dictionary, hyphens at line ends are kept
    zipf_frequency = None


def _rejoin_line_hyphen(match: re.Match) -> str:
    """Typeset line-end hyphenation ("includ-\\ned", "Or-\\nbiter") is undone when
    the joined form is a real word; genuine compounds ("O-\\nring", "low-\\ncost",
    "field-\\njoint", "re-\\nentry") keep their hyphen. Rule checked on real cases in
    docs/research/06_Stage2_Ingestion_Provenance.md."""
    a, b = match.group(1), match.group(2)
    if zipf_frequency is not None and a.isalpha() and b.isalpha():
        joined = zipf_frequency((a + b).lower(), "en")
        parts = min(zipf_frequency(a.lower(), "en"), zipf_frequency(b.lower(), "en"))
        if joined >= 3.0 or (joined >= 2.0 and joined >= parts):
            return a + b
    return f"{a}-{b}"
_SPACES = re.compile(r"[ \t]+")
_ORING = re.compile(r"\b0-ring", re.IGNORECASE)  # known OCR glyph error, as in Stage 1


def normalize_chars(text: str) -> str:
    """Character-level normalisation; keeps line breaks."""
    text = unicodedata.normalize("NFKC", text)
    text = _SOFT_HYPHEN_BREAK.sub("", text)        # "conduct\xad\ned" -> "conducted"
    text = text.replace("­", "")              # soft hyphen inside a line: invisible, drop
    text = text.replace("…", "...")
    text = text.translate(_PUNCT_MAP)
    text = _CONTROL.sub(" ", text)
    return _ORING.sub(lambda m: "O" + m.group(0)[1:], text)


def normalize_block(text: str) -> str:
    """A text block (paragraph) as one line of normalised text."""
    text = normalize_chars(text)
    text = _HARD_HYPHEN_BREAK.sub(_rejoin_line_hyphen, text)  # "includ-\ned" -> "included"; "O-\nring" kept
    text = text.replace("\r", "\n").replace("\n", " ")
    return _SPACES.sub(" ", text).strip()
