"""
corpus.py — the retrieval corpus for the base-paper reproduction (Stage 3).

Retrievable units are the Stage 2 page-aware passages of PRIMARY documents
whose curated field (data/processed/fields, Stage 2b) is not "other". The base
paper's three native fields are mapped from the curated 4-label scheme:

    base paper     MissionMind curated field
    Summary    <-  description
    Causes     <-  analysis
    Disposition <- recommendations
    (none)     <-  other            (front/back matter: not indexed, as in the paper,
                                      whose cards contain only the three fields)

Distractor documents have no fields and are not indexed in Stage 3 (recorded
deviation). Every unit keeps its provenance (doc_id, page, char offsets).
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

PAPER_FIELD = {"description": "summary", "analysis": "causes", "recommendations": "disposition"}
FIELDS = ("summary", "causes", "disposition")


@dataclass(frozen=True)
class Unit:
    id: str
    doc_id: str
    missions: tuple[str, ...]
    field: str            # summary | causes | disposition
    page: int
    char_start: int
    char_end: int
    section: str | None
    text: str


def manifest() -> dict:
    path = get_settings().data_dir / "manifest.json"
    return {d["doc_id"]: d for d in json.loads(path.read_text(encoding="utf-8"))["documents"]}


def load_units(require_status: str | None = None) -> list[Unit]:
    """require_status="reviewed" refuses draft field maps (for reportable runs)."""
    s, man, units = get_settings(), manifest(), []
    for doc_id, d in sorted(man.items()):
        if d["role"] != "primary":
            continue
        fields_path = s.processed_dir / "fields" / f"{doc_id}.jsonl"
        if not fields_path.exists():
            raise FileNotFoundError(f"no field assignment for primary document {doc_id}")
        fields = {r["passage_id"]: r for r in map(json.loads, open(fields_path, encoding="utf-8"))}
        for line in open(s.processed_dir / "passages" / f"{doc_id}.jsonl", encoding="utf-8"):
            p = json.loads(line)
            f = fields[p["passage_id"]]
            if require_status and f["map_status"] != require_status:
                raise ValueError(f"{doc_id}: field map status {f['map_status']!r}, required {require_status!r}")
            if f["field"] not in PAPER_FIELD:
                continue
            units.append(Unit(p["passage_id"], doc_id, tuple(d["mission_ids"]), PAPER_FIELD[f["field"]],
                              p["page"], p["char_start"], p["char_end"], p.get("section"), p["text"]))
    return units


def missions(units: list[Unit]) -> list[str]:
    return sorted({m for u in units for m in u.missions})
