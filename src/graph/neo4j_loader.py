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
from graph.neo4j_connector import get_driver, close_driver

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def ingest_chunks_to_neo4j():
    base_dir = Path(__file__).resolve().parent.parent.parent
    chunks_dir = base_dir / "data" / "processed" / "chunks"

    json_files = list(chunks_dir.glob("*_chunks.json"))
    if not json_files:
        print(f"No chunk files found in {chunks_dir}. Run text_chunker.py first.")
        return

    print(f"Loading Sentence-Transformer model ({EMBEDDING_MODEL})...")
    embedder = SentenceTransformer(EMBEDDING_MODEL)

    driver = get_driver()
    print("Connecting to local Neo4j instance...")

    with driver.session() as session:
        session.run("""
            CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
        """)

    total_inserted = 0
    total_skipped = 0

    for json_path in json_files:
        print(f"📥 Processing chunks from: {json_path.name}")
        start = time.time()

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        doc_id = data["document_id"]
        chunks = data["chunks"]

        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts, show_progress_bar=False)

        with driver.session() as session:
            # Skip chunks already ingested (idempotent re-runs, e.g. after
            # adding a new PDF without wanting to re-embed everything)
            existing = session.run(
                "MATCH (c:Chunk) WHERE c.id STARTS WITH $prefix RETURN c.id AS id",
                {"prefix": f"{doc_id}_"}
            )
            existing_ids = {r["id"] for r in existing}

            for chunk, embedding in zip(chunks, embeddings):
                if chunk["chunk_id"] in existing_ids:
                    total_skipped += 1
                    continue

                session.run("""
                    MERGE (d:Document {id: $doc_id})
                    CREATE (c:Chunk {
                        id: $chunk_id,
                        text: $text,
                        embedding: $embedding
                    })
                    MERGE (d)-[:HAS_CHUNK]->(c)
                """, {
                    "doc_id": doc_id,
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "embedding": embedding.tolist(),
                })
                total_inserted += 1

        print(f"   ✅ {len(chunks)} chunks processed in {time.time() - start:.1f}s")

    close_driver()
    print(f"{'='*60}\n🎉 Ingestion Complete: {total_inserted} new chunks stored, "
          f"{total_skipped} already present and skipped.")


if __name__ == "__main__":
    ingest_chunks_to_neo4j()