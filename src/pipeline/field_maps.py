"""
field_maps.py — curated per-document field maps (Stage 2 option (b)).

Stage 2 measured automatic pseudo-field assignment (heading rules, LLM) far
below target (B5 failed), so fields are assigned from a human-checked map per
document, written from the report's own table of contents:

  data/field_maps/<doc_id>.json
  {
    "doc_id": "...",
    "status": "draft" | "reviewed",      # only "reviewed" maps are used for reported results
    "drafted_by": "...", "reviewed_by": null | "...",
    "default": "other",
    "ranges": [                           # first match wins -> list specific entries first
      {"pages": [12, 40], "field": "analysis", "label": "Chapter 4 - The Cause of the Accident",
       "section_regex": "optional; entry applies only when the passage's section heading matches"}
    ]
  }

Pages are 1-based PDF page indices (not the printed page numbers). Fields use
the 4-label scheme that mirrors the base paper's Summary / Causes / Disposition:

  description      summary of the report, mission/system background, chronology of events
  analysis         investigation, evidence, findings, causes and contributing factors
  recommendations  recommendations, lessons learned, corrective actions
  other            front/back matter, member lists, appendices about administration, references
"""

import json
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

FIELDS = ("description", "analysis", "recommendations", "other")

# 6 -> 4 labels, for comparing with the Stage 2 heading rules
FROM_SIX = {"summary": "description", "narrative": "description", "findings": "analysis",
            "causes": "analysis", "recommendations": "recommendations", "other": "other"}


def maps_dir() -> Path:
    return get_settings().data_dir / "field_maps"


def validate_map(m: dict, n_pages: int | None = None) -> list[str]:
    problems = []
    if m.get("default", "other") not in FIELDS:
        problems.append(f"default {m.get('default')!r} not in {FIELDS}")
    if m.get("status") not in ("draft", "reviewed"):
        problems.append(f"status {m.get('status')!r}")
    for i, r in enumerate(m.get("ranges", [])):
        a, z = r["pages"]
        if r["field"] not in FIELDS:
            problems.append(f"range {i}: field {r['field']!r}")
        if not 1 <= a <= z or (n_pages and z > n_pages):
            problems.append(f"range {i}: pages {a}-{z} invalid (document has {n_pages})")
        if r.get("section_regex"):
            try:
                re.compile(r["section_regex"])
            except re.error as err:
                problems.append(f"range {i}: bad regex {err}")
    return problems


def load_map(doc_id: str) -> dict | None:
    path = maps_dir() / f"{doc_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def field_for(m: dict, page: int, section: str | None) -> tuple[str, int | None]:
    """Returns (field, index of the matching range or None for the default)."""
    for i, r in enumerate(m["ranges"]):
        a, z = r["pages"]
        if a <= page <= z and (not r.get("section_regex")
                               or re.search(r["section_regex"], section or "", re.I)):
            return r["field"], i
    return m.get("default", "other"), None


def assign_fields(doc_id: str, passages: list[dict], m: dict | None = None) -> list[dict]:
    m = m or load_map(doc_id)
    if m is None:
        raise FileNotFoundError(f"no field map for {doc_id}")
    out = []
    for p in passages:
        f, idx = field_for(m, p["page"], p.get("section"))
        out.append({"passage_id": p["passage_id"], "field": f, "map_range": idx, "map_status": m["status"]})
    return out
