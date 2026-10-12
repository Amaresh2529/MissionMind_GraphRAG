"""
main.py

FastAPI backend for MissionMind Graph-RAG. Retrieval lives in
graph/retriever.py and generation in backend/generation.py; this file only
wires the HTTP layer around them.

Run from the repository root:
    uvicorn --app-dir src backend.main:app --reload

(The previous content of this file was an older duplicate of the pipeline
with hard-coded credentials; the app that briefly lived in graph/retriever.py
has been moved here.)
"""

import sys
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from graph.retriever import GraphRAGRetriever
from graph.neo4j_connector import close_driver
from backend.generation import build_prompt, generate

app = FastAPI(
    title="MissionMind Graph-RAG API",
    description="Aerospace failure analysis using Neo4j, local embeddings, and Ollama.",
    version="1.1.0",
)


@lru_cache(maxsize=1)
def get_retriever() -> GraphRAGRetriever:
    """Created on first request, not at import time, so importing the app
    (e.g. in tests) does not load models or open database connections."""
    return GraphRAGRetriever()


class QueryRequest(BaseModel):
    question: str
    model_name: str | None = None
    top_k: int = 3


class QueryResponse(BaseModel):
    question: str
    model: str
    synthesized_answer: str
    retrieved_contexts: list


@app.get("/")
def health_check():
    return {"status": "online", "message": "MissionMind Graph-RAG API is running."}


@app.post("/query", response_model=QueryResponse)
def execute_graph_rag(payload: QueryRequest):
    try:
        retriever = get_retriever()
        results = retriever.hybrid_search(payload.question, top_k=payload.top_k)
        prompt = build_prompt(payload.question, retriever.build_context_text(results))
        model = payload.model_name or get_settings().llm_model
        answer = generate(prompt, model=model)
        contexts = [
            {"chunk_id": r["chunk_id"], "doc_id": r["doc_id"], "score": r["score"],
             "text": r["context"][:200], "facts": r["facts"],
             "related_failures": r["related_failures"]}
            for r in results
        ]
        return {"question": payload.question, "model": model,
                "synthesized_answer": answer, "retrieved_contexts": contexts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
def shutdown_event():
    close_driver()
