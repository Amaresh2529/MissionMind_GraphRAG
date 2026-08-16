import os
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import ollama

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"

class MissionMindGraphRAG:
    def __init__(self, model_name="llama3"):
        print("Initializing MissionMind Graph-RAG Engine...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        self.ollama_model = model_name

    def query(self, user_question: str):
        print(f"\n🔍 Processing Diagnostic Query: '{user_question}'")
        
        # 1. Generate Vector Embedding for User Question
        query_embedding = self.embedder.encode(user_question, show_progress_bar=False).tolist()

        # 2. Hybrid Graph Traversal Cypher Query
        cypher_query = """
        CALL db.index.vector.queryNodes('chunk_vector_index', 3, $embedding)
        YIELD node AS chunk, score
        OPTIONAL MATCH (chunk)-[:MENTIONS]->(fm:FailureMode)
        OPTIONAL MATCH (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s:Subsystem)
        OPTIONAL MATCH (fm)-[:CAUSED_BY]->(rc:RootCause)
        OPTIONAL MATCH (m:Mission)-[:EXPERIENCED_FAILURE]->(fm)
        RETURN 
            chunk.text AS text_context,
            m.name AS mission,
            s.name AS subsystem,
            fm.name AS failure_mode,
            rc.description AS root_cause
        """

        context_blocks = []
        with self.driver.session() as session:
            results = session.run(cypher_query, {"embedding": query_embedding})
            for record in results:
                block = f"Text Snippet: {record['text_context']}\n"
                if record['failure_mode']:
                    block += f"[Graph Intelligence Found] Mission: {record['mission']} | Subsystem: {record['subsystem']} | Failure Mode: {record['failure_mode']} | Root Cause: {record['root_cause']}\n"
                context_blocks.append(block)

        aggregated_context = "\n---\n".join(context_blocks)

        # 3. Construct Prompt for Ollama LLM
        prompt = f"""You are MissionMind, an advanced aerospace failure analysis AI assistant. 
Use the following retrieved document chunks and Knowledge Graph FMEA insights to answer the user's diagnostic query accurately and professionally. 
If the exact cause is listed in the Graph Intelligence, highlight it explicitly.

CONTEXT:
{aggregated_context}

USER QUERY:
{user_question}

ANSWER:
"""

        print(f"🤖 Synthesizing response using local Ollama ({self.ollama_model})...\n" + "="*60)
        
        # 4. Stream response from local Ollama instance
        response = ollama.chat(model=self.ollama_model, messages=[
            {"role": "user", "content": prompt}
        ], stream=True)

        for chunk in response:
            print(chunk['message']['content'], end='', flush=True)
        print("\n" + "="*60)

    def close(self):
        self.driver.close()

if __name__ == "__main__":
    rag = MissionMindGraphRAG(model_name="llama3") # Change to your preferred local ollama model if needed
    
    # Test query
    rag.query("Provide a detailed breakdown of the O-ring failure during the Challenger launch and its root cause.")
    
    rag.close()