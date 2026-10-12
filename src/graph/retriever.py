"""
retriever.py

GraphRAGRetriever — the CURRENT MissionMind retrieval method, restored after
commit 5d0219e accidentally overwrote this file with the FastAPI app (which
now lives in backend/main.py again).

Semantics are those of the original GraphRAGRetriever (commit 7d9ce24):
  1. dense vector search over Chunk embeddings (Neo4j `chunk_vector_index`),
  2. for each retrieved chunk, attach the FMEA facts the graph links to it
     (Mission, Subsystem, FailureMode, RootCause),
plus the two things the API/CLI already expected but that never existed:
  - `related_failures`: failures in OTHER missions connected by a
    SIMILAR_ROOT_CAUSE edge (the cross-mission pattern), and
  - `build_context_text()`: the prompt context block.

This is baseline B4 ("vector + unverified graph facts") in the experiment
plan. It deliberately does NOT add BM25, fields or verification — those are
separate baselines/extensions so that results stay attributable.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from graph.neo4j_connector import get_driver

_HYBRID_QUERY = """
CALL db.index.vector.queryNodes('chunk_vector_index', $top_k, $embedding)
YIELD node AS chunk, score
OPTIONAL MATCH (d:Document)-[:HAS_CHUNK]->(chunk)
OPTIONAL MATCH (chunk)-[:MENTIONS]->(fm:FailureMode)
OPTIONAL MATCH (m:Mission)-[:EXPERIENCED_FAILURE]->(fm)
OPTIONAL MATCH (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s:Subsystem)
OPTIONAL MATCH (fm)-[:CAUSED_BY]->(rc:RootCause)
OPTIONAL MATCH (fm)-[sim:SIMILAR_ROOT_CAUSE]-(fm2:FailureMode)<-[:EXPERIENCED_FAILURE]-(m2:Mission)
WHERE m2.name <> m.name
WITH chunk, score, d, fm, m, s, rc,
     collect(DISTINCT CASE WHEN fm2 IS NULL THEN NULL ELSE
       {mission: m2.name, failure_mode: fm2.name, similarity: sim.similarity} END) AS related
RETURN chunk.id AS chunk_id, d.id AS doc_id, chunk.text AS context, score,
       m.name AS mission, s.name AS subsystem, fm.name AS failure_mode,
       rc.description AS root_cause, fm.extraction_method AS extraction_method,
       related
ORDER BY score DESC
"""


def aggregate_rows(rows: list[dict]) -> list[dict]:
    """Collapses the row-per-(chunk, fact) Cypher output into one result per
    chunk, keeping rank order. A chunk that MENTIONS several failure modes
    yields several `facts` instead of several duplicated results (the old
    retriever printed one block per row, repeating the chunk text)."""
    by_chunk: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        cid = r["chunk_id"]
        if cid not in by_chunk:
            by_chunk[cid] = {
                "chunk_id": cid, "doc_id": r.get("doc_id"), "score": r["score"],
                "context": r["context"], "facts": [], "related_failures": [],
            }
            order.append(cid)
        entry = by_chunk[cid]
        if r.get("failure_mode"):
            fact = {k: r.get(k) for k in ("mission", "subsystem", "failure_mode",
                                          "root_cause", "extraction_method")}
            if fact not in entry["facts"]:
                entry["facts"].append(fact)
        for rel in r.get("related") or []:
            if rel and rel not in entry["related_failures"]:
                entry["related_failures"].append(rel)
    return [by_chunk[c] for c in order]


def build_context_text(results: list[dict]) -> str:
    """Prompt context: each chunk with its source id, then its graph facts
    and any cross-mission related failures."""
    blocks = []
    for i, r in enumerate(results, start=1):
        lines = [f"[{i}] Source: {r['chunk_id']} (similarity {r['score']:.3f})",
                 f"Text: {r['context']}"]
        for f in r["facts"]:
            lines.append(f"[Graph fact] Mission: {f['mission']} | Subsystem: {f['subsystem']} | "
                         f"Failure mode: {f['failure_mode']} | Root cause: {f['root_cause']}")
        for rel in r["related_failures"]:
            lines.append(f"[Cross-mission pattern] {rel['mission']}: {rel['failure_mode']} "
                         f"(root-cause similarity {rel['similarity']})")
        blocks.append("\n".join(lines))
    return "\n---\n".join(blocks)


class GraphRAGRetriever:
    def __init__(self, driver=None, embedder=None):
        self._driver = driver
        self._embedder = embedder

    @property
    def driver(self):
        if self._driver is None:
            self._driver = get_driver()
        return self._driver

    @property
    def embedder(self):
        if self._embedder is None:
            from sentence_transformers import SentenceTransformer
            self._embedder = SentenceTransformer(get_settings().embedding_model)
        return self._embedder

    def hybrid_search(self, query: str, top_k: int = 3) -> list[dict]:
        """Vector search over chunks + graph facts attached to each hit."""
        embedding = self.embedder.encode(query, show_progress_bar=False).tolist()
        with self.driver.session() as session:
            rows = [dict(r) for r in session.run(_HYBRID_QUERY, {"embedding": embedding, "top_k": top_k})]
        return aggregate_rows(rows)

    def vector_search_chunk_ids(self, query: str, top_k: int = 3) -> list[str]:
        """Ranked chunk ids only — used by retrieval metrics."""
        return [r["chunk_id"] for r in self.hybrid_search(query, top_k=top_k)]

    build_context_text = staticmethod(build_context_text)

    def close(self):
        # The driver is shared (neo4j_connector); closing it is the caller's job.
        self._driver = None


if __name__ == "__main__":
    retriever = GraphRAGRetriever()
    for r in retriever.hybrid_search("What caused the O-ring seal to fail during the launch?"):
        print(f"[{r['score']:.4f}] {r['chunk_id']}: {r['context'][:120]}...")
        for f in r["facts"]:
            print(f"   ▶ {f['mission']} | {f['subsystem']} | {f['failure_mode']} | {f['root_cause']}")
