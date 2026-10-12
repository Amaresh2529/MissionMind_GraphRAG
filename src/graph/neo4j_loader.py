"""
neo4j_loader.py

Reads chunked JSON files (data/processed/chunks/*.json), embeds each chunk
with the shared sentence-transformer, and writes Document/Chunk nodes into
Neo4j — including the vector index graph_builder.py and retriever.py both
depend on. This has to run before either of those.
"""

import json
import sys
import time
from pathlib import Path
from sentence_transformers import SentenceTransformer

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from graph.neo4j_connector import get_driver, close_driver

# Stage 2: re-ingestion is refresh-on-change. Until Stage 1, chunks whose id
# already existed were skipped and never updated, which left stale text in a
# reused database (449/596 Challenger chunks in the legacy DB). Now a chunk
# whose text changed is updated and re-embedded, and chunks that a document no
# longer produces are deleted. On a fresh database the result is identical to
# Stage 1 (every chunk is an insert), so baseline B4 is unaffected.


def plan_chunk_changes(existing: dict[str, str], chunks: list[dict]) -> dict:
    """Pure diff: existing {chunk_id: text} vs current chunks."""
    cur = {c["chunk_id"]: c["text"] for c in chunks}
    return {
        "insert": [cid for cid in cur if cid not in existing],
        "update": [cid for cid in cur if cid in existing and existing[cid] != cur[cid]],
        "unchanged": [cid for cid in cur if existing.get(cid) == cur[cid]],
        "delete": [cid for cid in existing if cid not in cur],
    }


def ingest_chunks_to_neo4j(doc_ids: list[str] | None = None) -> dict:
    """Embeds and stores Chunk nodes. `doc_ids` restricts ingestion to a
    subset of documents. Returns counts of inserted/updated/skipped/deleted."""
    s = get_settings()
    chunks_dir = s.chunks_dir

    json_files = sorted(chunks_dir.glob("*_chunks.json"))
    if doc_ids:
        json_files = [p for p in json_files if p.name[: -len("_chunks.json")] in set(doc_ids)]
    if not json_files:
        print(f"No chunk files found in {chunks_dir} (filter: {doc_ids}). Run text_chunker.py first.")
        return {"inserted": 0, "skipped": 0, "documents": 0}

    print(f"Loading Sentence-Transformer model ({s.embedding_model})...")
    embedder = SentenceTransformer(s.embedding_model)

    driver = get_driver()
    print("Connecting to local Neo4j instance...")

    dims = embedder.get_sentence_embedding_dimension()  # 384 for all-MiniLM-L6-v2
    with driver.session() as session:
        session.run(f"""
            CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dims)}, `vector.similarity_function`: 'cosine'}}}}
        """)

    totals = {"inserted": 0, "updated": 0, "skipped": 0, "deleted": 0, "documents": len(json_files)}

    for json_path in json_files:
        print(f"📥 Processing chunks from: {json_path.name}")
        start = time.time()

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        doc_id = data["document_id"]
        chunks = data["chunks"]

        with driver.session() as session:
            # Chunks of this document: (Document)-[:HAS_CHUNK]->(Chunk). The id
            # prefix match of Stage 1 also caught other documents whose id starts
            # with this one; the relationship is exact.
            existing = {r["id"]: r["text"] for r in session.run(
                "MATCH (:Document {id: $doc})-[:HAS_CHUNK]->(c:Chunk) RETURN c.id AS id, c.text AS text",
                doc=doc_id)}
            plan = plan_chunk_changes(existing, chunks)
            todo_ids = set(plan["insert"]) | set(plan["update"])
            todo = [c for c in chunks if c["chunk_id"] in todo_ids]
            if todo:
                embeddings = embedder.encode([c["text"] for c in todo], show_progress_bar=False)
                rows = [{"chunk_id": c["chunk_id"], "text": c["text"], "embedding": e.tolist()}
                        for c, e in zip(todo, embeddings)]
                session.run("""
                    UNWIND $rows AS row
                    MERGE (d:Document {id: $doc_id})
                    MERGE (c:Chunk {id: row.chunk_id})
                    SET c.text = row.text, c.embedding = row.embedding
                    MERGE (d)-[:HAS_CHUNK]->(c)
                """, rows=rows, doc_id=doc_id)
            if plan["delete"]:
                session.run("MATCH (c:Chunk) WHERE c.id IN $ids DETACH DELETE c", ids=plan["delete"])

        totals["inserted"] += len(plan["insert"])
        totals["updated"] += len(plan["update"])
        totals["skipped"] += len(plan["unchanged"])
        totals["deleted"] += len(plan["delete"])
        print(f"   ✅ {len(chunks)} chunks: +{len(plan['insert'])} ~{len(plan['update'])} "
              f"={len(plan['unchanged'])} -{len(plan['delete'])} in {time.time() - start:.1f}s")

    close_driver()
    print(f"{'='*60}\n🎉 Ingestion Complete: {totals}")
    return totals


if __name__ == "__main__":
    ingest_chunks_to_neo4j()