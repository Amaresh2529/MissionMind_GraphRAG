from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import ollama

app = FastAPI(
    title="MissionMind Graph-RAG API",
    description="Backend API for aerospace failure analysis using Neo4j, local embeddings, and Ollama.",
    version="1.0.0"
)

# Local Credentials
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"

# Initialize global models and driver on startup to avoid reloading overhead
embedder = SentenceTransformer('all-MiniLM-L6-v2')
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

class QueryRequest(BaseModel):
    question: str
    model_name: str = "llama3"
    top_k: int = 3

class QueryResponse(BaseModel):
    question: str
    synthesized_answer: str
    retrieved_contexts: list

@app.get("/")
def health_check():
    return {"status": "online", "message": "MissionMind Graph-RAG API is running smoothly."}

@app.post("/query", response_model=QueryResponse)
def execute_graph_rag(payload: QueryRequest):
    try:
        # 1. Embed query
        query_embedding = embedder.encode(payload.question, show_progress_bar=False).tolist()

        # 2. Hybrid Cypher Query
        cypher_query = """
        CALL db.index.vector.queryNodes('chunk_vector_index', $top_k, $embedding)
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
            rc.description AS root_cause,
            score
        """

        context_blocks = []
        structured_contexts = []
        
        with driver.session() as session:
            results = session.run(cypher_query, {"embedding": query_embedding, "top_k": payload.top_k})
            for record in results:
                block = f"Text Snippet: {record['text_context']}\n"
                if record['failure_mode']:
                    block += f"[Graph Intelligence] Mission: {record['mission']} | Subsystem: {record['subsystem']} | Failure Mode: {record['failure_mode']} | Root Cause: {record['root_cause']}\n"
                context_blocks.append(block)
                
                structured_contexts.append({
                    "score": record["score"],
                    "mission": record["mission"],
                    "subsystem": record["subsystem"],
                    "failure_mode": record["failure_mode"],
                    "root_cause": record["root_cause"],
                    "text": record["text_context"][:200]
                })

        aggregated_context = "\n---\n".join(context_blocks)

        # 3. Prompt Construction
        prompt = f"""You are MissionMind, an advanced aerospace failure analysis AI assistant. 
Use the following retrieved document chunks and Knowledge Graph FMEA insights to answer the user's diagnostic query accurately and professionally.

CONTEXT:
{aggregated_context}

USER QUERY:
{payload.question}

ANSWER:
"""

        # 4. Ollama Generation
        response = ollama.chat(model=payload.model_name, messages=[
            {"role": "user", "content": prompt}
        ])
        
        answer = response['message']['content']

        return {
            "question": payload.question,
            "synthesized_answer": answer,
            "retrieved_contexts": structured_contexts
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))