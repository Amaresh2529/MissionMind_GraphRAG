"""
text_cleaner.py

Text cleaning and extraction-quality scoring, split out of pdf_loader.py so
PDF-handling and text-quality logic aren't tangled in one file. pdf_loader.py
imports from here; nothing else changes about how either behaves.
"""

import re

try:
    from wordfreq import zipf_frequency
    WORDFREQ_AVAILABLE = True
except ImportError:
    WORDFREQ_AVAILABLE = False

# A digit fused directly between letters is close to unambiguous evidence of
# extraction corruption (e.g. "faci8ities" from "facilities"). Legitimate
# technical tokens like "STS-51-L" or "24/7" don't match — the digit has to
# sit *inside* an unbroken run of letters on both sides.
_EMBEDDED_DIGIT_RE = re.compile(r'[A-Za-z]\d[A-Za-z]')

_STRIP_CHARS = '.,;:()[]{}"\'`'

# Known, fixed font-mapping artifact in older scanned reports: the glyph for
# capital "O" gets extracted as digit "0" specifically in "O-ring"/"O-rings"
# (e.g. Challenger's report). Deterministic substitution — "0-ring" never
# legitimately means a numeric zero — so it's safe to correct globally.
_ORING_RE = re.compile(r'\b0-ring', re.IGNORECASE)


def _fix_oring(match: re.Match) -> str:
    return 'O' + match.group(0)[1:]


def sanitize_text(text: str) -> str:
    """Removes excessive whitespace, non-ASCII characters, and fixes the
    known O-ring OCR artifact."""
    cleaned = re.sub(r'\s+', ' ', text)
    cleaned = re.sub(r'[^\x00-\x7F]+', ' ', cleaned)
    cleaned = _ORING_RE.sub(_fix_oring, cleaned)
    return cleaned.strip()


def text_quality_score(text: str) -> float:
    """
    Estimates extraction quality for a page, returning a score in [0, 1]
    where higher is cleaner. Two signals, both designed to leave normal
    technical-document text (citations, page numbers, hyphenated part names,
    ALL-CAPS acronyms, proper nouns) completely untouched:

    1. Embedded-digit corruption — a digit fused between letters is a
       strong, low-noise signature of broken font/encoding extraction. Any
       meaningful presence of it fails the page outright.

    2. Dictionary coverage — for ordinary *lowercase* words only (numbers,
       proper nouns, ALL-CAPS acronyms excluded so "Marshall", "Thiokol",
       "NASA" are never penalized), the fraction that are recognizable
       English words. Requires `wordfreq`; skipped if not installed.
    """
    tokens = text.split()
    if not tokens:
        return 1.0  # nothing to judge; don't force OCR on a blank page

    embedded_digit_hits = sum(1 for t in tokens if _EMBEDDED_DIGIT_RE.search(t))
    if embedded_digit_hits / len(tokens) > 0.01:
        return 0.0

    if not WORDFREQ_AVAILABLE:
        return 1.0

    checkable = []
    for t in tokens:
        core = t.strip(_STRIP_CHARS)
        if len(core) < 3 or not core.isalpha():
            continue
        if core[0].isupper() or core.isupper():
            continue  # assume proper noun / acronym — don't penalize
        checkable.append(core.lower())

    if len(checkable) < 8:
        return 1.0  # too little evidence either way; don't force OCR

    known = sum(1 for w in checkable if zipf_frequency(w, 'en') > 0)
    return known / len(checkable)