"""
factor_graph.py — mission-level causal-factor profiles from verified extractions,
and their Neo4j representation (Stage 4).

Profile of mission m:  F_m = {code: {"roles": Counter, "evidence": [factor mentions]}}
built from data/processed/factors/*.jsonl (accepted factors only; "-verification"
ablation: also rejected proposals that have a valid code).

Analogy (Proposal v2, Sec. 9):
    analogy(m_i, m_j) = sum_{f in F_i & F_j} idf(f) / sum_{f in F_i | F_j} idf(f)
    idf(f) = ln(N / df(f)) + 1      (N missions, df = missions whose profile contains f; +1 keeps
                                      ubiquitous codes from vanishing entirely)

Neo4j (separate from Stage 1 nodes; never touches :Chunk/:FailureMode):
    (:Mission {id})-[:HAS_FACTOR {roles, n_evidence}]->(:FactorCategory {code, name, group})
    (:Passage {id})-[:STATES_FACTOR {role, statement, quote, char_start, char_end}]->(:FactorCategory)
"""

import collections
import json
import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

ROLE_ORDER = {"root": 0, "contributing": 1, "observation": 2}


def load_mentions(include_rejected: bool = False, valid_codes: set[str] | None = None) -> list[dict]:
    out = []
    for f in sorted((get_settings().processed_dir / "factors").glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            items = list(r["accepted"])
            if include_rejected:
                items += [x for x in r["rejected"] if valid_codes and x.get("code") in valid_codes]
            for x in items:
                out.append({"passage_id": r["passage_id"], "doc_id": r["doc_id"], "page": r["page"],
                            "missions": r["missions"], **x})
    return out


def profiles(mentions: list[dict], roles: tuple[str, ...] = ("root", "contributing", "observation")) -> dict:
    prof: dict[str, dict] = collections.defaultdict(dict)
    for m in mentions:
        if m.get("role") not in roles:
            continue
        for mission in m["missions"]:
            e = prof[mission].setdefault(m["code"], {"roles": collections.Counter(), "evidence": []})
            e["roles"][m["role"]] += 1
            e["evidence"].append(m)
    return dict(prof)


def idf(prof: dict, n_missions: int | None = None) -> dict[str, float]:
    n = n_missions or len(prof)
    df = collections.Counter(code for p in prof.values() for code in p)
    return {c: math.log(n / d) + 1.0 for c, d in df.items()}


def analogy(a: set[str], b: set[str], w: dict[str, float]) -> float:
    union = a | b
    if not union:
        return 0.0
    return sum(w.get(c, 1.0) for c in a & b) / sum(w.get(c, 1.0) for c in union)


def write_neo4j(prof: dict, taxonomy_codes: dict) -> dict:
    from graph.neo4j_connector import get_driver
    drv = get_driver()
    with drv.session() as s:
        s.run("CREATE CONSTRAINT factor_code IF NOT EXISTS FOR (f:FactorCategory) REQUIRE f.code IS UNIQUE")
        s.run("CREATE CONSTRAINT mission_id IF NOT EXISTS FOR (m:Mission) REQUIRE m.id IS UNIQUE")
        s.run("MATCH (:Mission)-[r:HAS_FACTOR]->() DELETE r")            # rebuilt from scratch each time
        s.run("MATCH (:Passage)-[r:STATES_FACTOR]->() DELETE r")
        s.run("UNWIND $rows AS r MERGE (f:FactorCategory {code: r.code}) SET f.name = r.name, f.group = r.group",
              rows=[{"code": c, "name": v["name"], "group": v["group"]} for c, v in taxonomy_codes.items()])
        mission_rows, mention_rows = [], []
        for m, codes in prof.items():
            for c, e in codes.items():
                mission_rows.append({"m": m, "code": c, "roles": dict(e["roles"]), "n": len(e["evidence"])})
                for x in e["evidence"]:
                    mention_rows.append({"pid": x["passage_id"], "code": c, "role": x["role"], "statement": x["statement"],
                                         "quote": x["quote"], "cs": x["char_start"], "ce": x["char_end"]})
        s.run("""UNWIND $rows AS r MERGE (m:Mission {id: r.m}) WITH m, r
                 MATCH (f:FactorCategory {code: r.code})
                 MERGE (m)-[h:HAS_FACTOR]->(f) SET h.root = coalesce(r.roles.root, 0),
                   h.contributing = coalesce(r.roles.contributing, 0), h.observation = coalesce(r.roles.observation, 0),
                   h.n_evidence = r.n""", rows=mission_rows)
        # a passage of a multi-mission document appears once per mission in the profile; keep one edge per mention
        uniq = {(r["pid"], r["code"], r["cs"]): r for r in mention_rows}
        s.run("""UNWIND $rows AS r MATCH (p:Passage {id: r.pid}) MATCH (f:FactorCategory {code: r.code})
                 CREATE (p)-[:STATES_FACTOR {role: r.role, statement: r.statement, quote: r.quote,
                                             char_start: r.cs, char_end: r.ce}]->(f)""", rows=list(uniq.values()))
        counts = s.run("""MATCH (m:Mission)-[h:HAS_FACTOR]->() WITH count(DISTINCT m) AS missions, count(h) AS has
                          MATCH ()-[s:STATES_FACTOR]->() RETURN missions, has, count(s) AS states""").single()
    return dict(counts)
