"""Option (b): curated per-document field maps resolve page/section -> field deterministically."""
import json
from pathlib import Path

import pytest

from pipeline.field_maps import FIELDS, assign_fields, field_for, validate_map

ROOT = Path(__file__).resolve().parent.parent

MAP = {"doc_id": "X", "status": "draft", "default": "other", "ranges": [
    {"pages": [1, 50], "field": "other", "label": "endnotes", "section_regex": "^endnotes"},
    {"pages": [3, 5], "field": "description", "label": "ch 1"},
    {"pages": [6, 9], "field": "analysis", "label": "ch 2"},
    {"pages": [10, 10], "field": "recommendations", "label": "recs"},
]}


@pytest.mark.parametrize("page,section,expected", [
    (1, "Title", "other"),                  # no range -> default
    (4, "1.1 Background", "description"),
    (7, "ENDNOTES FOR CHAPTER 2", "other"),  # first match wins: section rule before page range
    (7, None, "analysis"),
    (10, "Recommendations", "recommendations"),
])
def test_field_for(page, section, expected):
    assert field_for(MAP, page, section)[0] == expected


def test_assign_fields_keeps_ids_and_status():
    rows = assign_fields("X", [{"passage_id": "X::p0004::00", "page": 4, "section": "a"}], MAP)
    assert rows == [{"passage_id": "X::p0004::00", "field": "description", "map_range": 1, "map_status": "draft"}]


def test_validate_map_catches_errors():
    bad = {"status": "final", "default": "x", "ranges": [{"pages": [5, 3], "field": "causes"},
                                                         {"pages": [1, 99], "field": "other", "section_regex": "("}]}
    problems = validate_map(bad, n_pages=50)
    assert len(problems) == 6   # status, default, field, reversed pages, pages > document, regex


@pytest.mark.parametrize("path", sorted((ROOT / "data" / "field_maps").glob("*.json")), ids=lambda p: p.stem[:30])
def test_committed_maps_are_valid(path):
    m = json.loads(path.read_text(encoding="utf-8"))
    manifest = {d["doc_id"]: d for d in json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    assert m["doc_id"] == path.stem and m["doc_id"] in manifest
    assert validate_map(m, manifest[m["doc_id"]]["pages"]) == []
    assert all(r["field"] in FIELDS for r in m["ranges"])
