"""B3: normalisation keeps information the Stage 1 cleaner destroyed."""
import pytest

from pipeline.normalize import normalize_block, normalize_chars


def test_ligatures_expanded():
    assert normalize_block("Atmospheric Proﬁles") == "Atmospheric Profiles"
    assert normalize_block("the module ﬂew through") == "the module flew through"


def test_soft_hyphen_across_line_is_joined():
    assert normalize_block("science conduct­\ned on the mission") == "science conducted on the mission"
    assert "­" not in normalize_block("inter­nal")


def test_typographic_apostrophes_and_quotes():
    assert normalize_block("the Earthʼs horizon") == "the Earth's horizon"
    assert normalize_block("“foam” – debris") == '"foam" - debris'


def test_hard_hyphen_line_break_keeps_hyphen_in_compounds():
    assert normalize_block("primary O-\nring seal") == "primary O-ring seal"
    assert normalize_block("a low-\ncost satellite") == "a low-cost satellite"
    assert normalize_block("the field-\njoint") == "the field-joint"


@pytest.mark.parametrize("broken,joined", [("includ-\ned", "included"), ("Or-\nbiter", "Orbiter"),
                                           ("con-\nditions", "conditions"), ("in-\ncorporate", "incorporate"),
                                           ("mis-\nsions", "missions"), ("Depart-\nment", "Department")])
def test_typeset_line_hyphenation_rejoined(broken, joined):
    assert normalize_block(broken) == joined


def test_line_breaks_and_spaces_collapsed():
    assert normalize_block("  first line\nsecond\t line  ") == "first line second line"


def test_meaningful_symbols_kept():
    out = normalize_block("28 °F ± 2, δ angle, Académie")
    assert "°" in out and "±" in out and "δ" in out and "é" in out


def test_known_oring_ocr_error_fixed():
    assert normalize_chars("the 0-ring") == "the O-ring"
