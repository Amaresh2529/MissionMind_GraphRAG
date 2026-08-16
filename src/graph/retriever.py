from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

# Local Docker Neo4j Credentials
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"

class GraphRAGRetriever:
    def __init__(self):
        print("Loading Embedding Model...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    def hybrid_search(self, query: str, top_k: int = 3):
        """Performs a vector search and traverses the FMEA knowledge graph."""
        print(f"\n🔍 Querying: '{query}'")
        
        # 1. Embed the user question
        query_embedding = self.embedder.encode(query, show_progress_bar=False).tolist()

        # 2. Cypher query for Hybrid Retrieval
        cypher_query = """
        // Step A: Vector similarity search to find the most relevant chunks
        CALL db.index.vector.queryNodes('chunk_vector_index', $top_k, $embedding)
        YIELD node AS chunk, score
        
        // Step B: Graph traversal to pull deterministic FMEA entities
        OPTIONAL MATCH (chunk)-[:MENTIONS]->(fm:FailureMode)
        OPTIONAL MATCH (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s:Subsystem)
        OPTIONAL MATCH (fm)-[:CAUSED_BY]->(rc:RootCause)
        OPTIONAL MATCH (m:Mission)-[:EXPERIENCED_FAILURE]->(fm)
        
        RETURN 
            score,
            chunk.text AS context,
            m.name AS mission,
            s.name AS subsystem,
            fm.name AS failure_mode,
            rc.description AS root_cause
        ORDER BY score DESC
        """
        
        with self.driver.session() as session:
            results = session.run(cypher_query, {"embedding": query_embedding, "top_k": top_k})
            
            print(f"\n{'='*60}\n🚀 HYBRID SEARCH RESULTS\n{'='*60}")
            for record in results:
                print(f"[{record['score']:.4f}] Context: {record['context'][:150]}...")
                if record['failure_mode']:
                    print(f"   ▶ Mission: {record['mission']}")
                    print(f"   ▶ Subsystem: {record['subsystem']}")
                    print(f"   ▶ Failure Mode: {record['failure_mode']}")
                    print(f"   ▶ Root Cause: {record['root_cause']}")
                else:
                    print("   ▶ No structured FMEA entities attached to this chunk.")
                print("-" * 60)

    def close(self):
        self.driver.close()

if __name__ == "__main__":
    retriever = GraphRAGRetriever()
    
    # Let's test a complex diagnostic query!
    test_query = "What caused the O-ring seal to fail during the launch?"
    retriever.hybrid_search(test_query)
    
    retriever.close()