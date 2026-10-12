"""
queries.py — development queries for the Stage 3 reproduction.

The base paper's query is "a free-text description of a vessel incident". The
human-authored MissionMind benchmark queries (D2/D3) do not exist yet, so for
plumbing and smoke runs each primary mission gets an AUTOMATIC dev query: the
first QUERY_WORDS words of its own report's description-field passages, in page
order, taken from documents that cover only that mission. These queries are
NOT a benchmark (they can contain the board's own summary of causes) and must
not be used to tune anything that is later reported.
"""

import json

from retrieval.corpus import Unit

QUERY_WORDS = 300


def dev_queries(units: list[Unit]) -> list[dict]:
    by_mission: dict[str, list[Unit]] = {}
    for u in units:
        if len(u.missions) == 1 and u.field == "summary":
            by_mission.setdefault(u.missions[0], []).append(u)
    out = []
    for m, us in sorted(by_mission.items()):
        us.sort(key=lambda u: (u.doc_id, u.page, u.char_start))
        words = " ".join(u.text for u in us).split()[:QUERY_WORDS]
        out.append({"query_id": f"dev-{m}", "mission": m, "kind": "dev_auto_description",
                    "source_units": [u.id for u in us][:10], "text": " ".join(words)})
    return out


def load_queries(path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
