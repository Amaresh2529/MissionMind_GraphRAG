import json
from pathlib import Path
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

# Hardcoded Neo4j Aura Credentials
NEO4J_URI = "neo4j+s://977dc26d.databases.neo4j.io"
NEO4J_USERNAME = "977dc26d"
NEO4J_PASSWORD = "_3TKAVEcstPYAxJ31McvAjd6umCp1Tg8TJi98AQnnCY"
NEO4J_DATABASE = "977dc26d"

def ingest_chunks_to_neo4j():
    """Reads chunked JSON files, generates embeddings, and pushes nodes to Neo4j Aura."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    chunks_dir = base_dir / "data" / "processed" / "chunks"
    
    json_files = list(chunks_dir.glob("*_chunks.json"))
    if not json_files:
        print(f"No chunk files found in {chunks_dir}. Run text_chunker.py first.")
        return

    print("Loading Sentence-Transformer model (all-MiniLM-L6-v2)...")
    embedder = SentenceTransformer('all-MiniLM-L6-v2')

    print(f"Connecting to Neo4j Aura instance at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    # Specify the database explicitly for Aura cloud environments
    with driver.session(database=NEO4J_DATABASE) as session:
        # Create vector index constraint for hybrid search
        session.run("""
            CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
            FOR (c:Chunk) ON (c.embedding)
            OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}}
        """)

    total_inserted = 0

    for json_path in json_files:
        print(f"📥 Processing chunks from: {json_path.name}")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        doc_id = data["document_id"]
        chunks = data["chunks"]
        
        # Batch process chunk embeddings
        texts = [c["text"] for c in chunks]
        embeddings = embedder.encode(texts, show_progress_bar=False)

        with driver.session(database=NEO4J_DATABASE) as session:
            for chunk, embedding in zip(chunks, embeddings):
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
                    "embedding": embedding.tolist()
                })
                total_inserted += 1

        print(f"   ✅ Successfully loaded {len(chunks)} chunks into Neo4j for {doc_id}")

    driver.close()
    print(f"{'='*60}\n🎉 Ingestion Complete: Stored {total_inserted} total text chunks with vector embeddings in Neo4j Aura.")

if __name__ == "__main__":
    ingest_chunks_to_neo4j()