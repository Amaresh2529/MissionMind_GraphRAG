"""
inspect_similarity_distribution.py

Diagnostic only — doesn't modify the graph. Pulls every FailureMode already
extracted (from your last graph_builder.py run) and re-computes pairwise
cross-mission similarity WITHOUT the 0.65 filter, so you can see the actual
score distribution before picking a threshold. Cheap and fast — only the
embedding + comparison step re-runs, not NER/LLM extraction.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from graph.neo4j_connector import get_driver, close_driver
from models.embeddings import FailureRecord, embed_failures
from sentence_transformers import util


def fetch_failure_records() -> list[FailureRecord]:
    driver = get_driver()
    with driver.session() as session:
        results = session.run("""
            MATCH (m:Mission)-[:EXPERIENCED_FAILURE]->(fm:FailureMode)-[:CAUSED_BY]->(rc:RootCause)
            OPTIONAL MATCH (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s:Subsystem)
            RETURN m.name AS mission, s.name AS subsystem, fm.name AS failure_mode, rc.description AS root_cause
        """)
        seen = {}
        for r in results:
            key = (r["mission"], r["failure_mode"])
            if key not in seen:
                seen[key] = FailureRecord(
                    mission=r["mission"], subsystem=r["subsystem"] or "Unspecified",
                    failure_mode=r["failure_mode"], root_cause=r["root_cause"],
                )
        return list(seen.values())


def main():
    records = fetch_failure_records()
    print(f"Pulled {len(records)} failure records from Neo4j.\n")

    embeddings = embed_failures(records)
    sim_matrix = util.cos_sim(embeddings, embeddings)

    pairs = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if records[i].mission == records[j].mission:
                continue
            pairs.append((records[i], records[j], sim_matrix[i][j].item()))

    pairs.sort(key=lambda p: p[2], reverse=True)

    print(f"{'='*70}\nTop 20 cross-mission pairs by similarity (no threshold applied)\n{'='*70}")
    for rec_a, rec_b, score in pairs[:20]:
        print(f"[{score:.4f}] {rec_a.mission} <-> {rec_b.mission}")
        print(f"    A: {rec_a.failure_mode} — {rec_a.root_cause[:80]}")
        print(f"    B: {rec_b.failure_mode} — {rec_b.root_cause[:80]}")
        print("-" * 70)

    scores_only = [p[2] for p in pairs]
    if scores_only:
        sorted_scores = sorted(scores_only)
        print(f"\nDistribution: max={max(scores_only):.4f}, "
              f"median={sorted_scores[len(sorted_scores)//2]:.4f}, "
              f"min={min(scores_only):.4f}, total cross-mission pairs={len(scores_only)}")

    close_driver()


if __name__ == "__main__":
    main()