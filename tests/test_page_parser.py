"""B1/B2/B3: provenance contract of the Stage 2 page-aware parser, on a synthetic PDF."""
import re
from pathlib import Path

import pymupdf
import pytest

from pipeline.page_parser import parse_document, assign_pseudo_field

FONT = Path("C:/Windows/Fonts/arial.ttf")

BODY = ("The investigation found that the primary seal eroded during ascent because the joint "
        "rotated under pressure and the cold temperature reduced resiliency. ") * 6


@pytest.fixture(scope="module")
def synthetic_pdf(tmp_path_factory):
    path = tmp_path_factory.mktemp("pdf") / "Synthetic_Report.pdf"
    doc = pymupdf.open()
    layout = [
        [("1. THE ACCIDENT", 18, True), (BODY, 11, False), ("Synthetic Board Report", 9, False), ("1", 9, False)],
        [(BODY, 11, False), ("2. CAUSE OF THE ACCIDENT", 18, True),
         (BODY, 11, False), ("Synthetic Board Report", 9, False), ("2", 9, False)],
        [("3. RECOMMENDATIONS", 18, True), (BODY, 11, False), ("Synthetic Board Report", 9, False), ("3", 9, False)],
    ]
    for blocks in layout:
        page = doc.new_page()
        y = 60
        for text, size, bold in blocks:
            font = "hebo" if bold else "helv"
            rect = pymupdf.Rect(50, y, 550, y + 400)
            page.insert_textbox(rect, text, fontsize=size, fontname=font)
            lines = max(1, int(len(text) * size * 0.5 / 500) + 1)
            y += lines * size * 1.4 + 20
    # page 4: characters the Stage 1 cleaner destroyed, written with a TrueType
    # font that has the ligature glyph (base-14 fonts cannot encode U+FB01)
    page = doc.new_page()
    special = "Atmospheric proﬁles were conduct­\ned by the Earthʼs team."
    if FONT.exists():
        page.insert_font(fontname="arialx", fontfile=str(FONT))
        page.insert_text((50, 100), special, fontname="arialx", fontsize=11)
    doc.save(path)
    return path


@pytest.fixture(scope="module")
def parsed(synthetic_pdf):
    return parse_document(synthetic_pdf, use_ocr=False)


def test_passage_text_equals_page_slice(parsed):
    pages, passages, _ = parsed
    texts = {p.number: p.text for p in pages}
    assert passages
    for x in passages:
        assert x["text"] == texts[x["page"]][x["char_start"]:x["char_end"]]
        assert x["doc_id"] == "Synthetic_Report" and x["page"] >= 1


def test_passages_cover_all_non_boilerplate_blocks(parsed):
    pages, passages, _ = parsed
    for page in pages:
        covered = set()
        for x in passages:
            if x["page"] == page.number:
                covered.update(range(x["char_start"], x["char_end"]))
        for b in page.blocks:
            if b.kind != "boilerplate":   # union of passages covers every non-space character
                gaps = [i for i in range(b.start, b.end) if i not in covered and not page.text[i].isspace()]
                assert not gaps, b.text[:40]


def test_boilerplate_detected_and_excluded(parsed):
    pages, passages, _ = parsed
    kinds = {b.text: b.kind for p in pages for b in p.blocks}
    assert kinds["Synthetic Board Report"] == "boilerplate"
    assert not any("Synthetic Board Report" in x["text"] for x in passages)


def test_sections_and_fields_follow_headings(parsed):
    _, passages, _ = parsed
    fields = {x["section"]: x["pseudo_field"] for x in passages}
    assert fields["1. THE ACCIDENT"] == "narrative"
    assert fields["2. CAUSE OF THE ACCIDENT"] == "causes"
    assert fields["3. RECOMMENDATIONS"] == "recommendations"
    # passage before the page-2 heading continues section 1 (no passage spans two sections)
    p2 = [x for x in passages if x["page"] == 2]
    assert p2[0]["section"] == "1. THE ACCIDENT"
    for x in passages:
        assert x["text"].count("CAUSE OF THE ACCIDENT") <= 1


def test_normalisation_applied_in_pages(parsed):
    if not FONT.exists():
        pytest.skip("no TrueType font with ligature glyphs available")
    pages, _, _ = parsed
    text = pages[3].text
    assert "profiles" in text and "Earth's" in text
    assert "conducted" in text            # soft hyphen + line break re-joined
    assert not re.search("[ﬁﬂ­ʼ]", text)
    assert not re.search("[ﬁﬂ­ʼ]", text)


@pytest.mark.parametrize("section,chapter,expected", [
    ("MCO Contributing Cause No. 1: Modeling", "5. Contributing Causes", "causes"),
    ("MPL Recommendations:", None, "recommendations"),
    ("1. INTRODUCTION/BACKGROUND", "Appendix Letter Establishing the Board", "other"),
    ("Executive Summary", None, "summary"),
    ("Some unknown heading", None, "findings"),     # body text under an unmatched heading
    (None, None, "other"),                         # text before the first heading
    ("ENDNOTES FOR CHAPTER 5", "CHAPTER 5", "other"),
])
def test_pseudo_field_rules(section, chapter, expected):
    assert assign_pseudo_field(section, chapter) == expected
