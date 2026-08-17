"""
main.py

FastAPI backend for MissionMind Graph-RAG. Retrieval logic lives entirely in
retriever.py — this file just wires the API layer around it, so there's one
place that knows how to query the graph, not three.
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import ollama

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from graph.retriever import GraphRAGRetriever
from graph.neo4j_connector import close_driver

app = FastAPI(
    title="MissionMind Graph-RAG API",
    description="Backend API for aerospace failure analysis using Neo4j, local embeddings, and Ollama.",
    version="1.0.0"
)

retriever = GraphRAGRetriever()  # one shared instance — owns the embedder + driver

_PROMPT_TEMPLATE = """You are MissionMind, an advanced aerospace failure analysis AI assistant.
Use the following retrieved document chunks and Knowledge Graph FMEA insights — including any cross-mission patterns — to answer the user's diagnostic query accurately and professionally. If a cross-mission pattern is present in the context, mention it explicitly.

CONTEXT:
{context}

USER QUERY:
{question}

ANSWER:
"""


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
        results = retriever.hybrid_search(payload.question, top_k=payload.top_k)
        aggregated_context = retriever.build_context_text(results)

        prompt = _PROMPT_TEMPLATE.format(context=aggregated_context, question=payload.question)
        response = ollama.chat(model=payload.model_name, messages=[{"role": "user", "content": prompt}])
        answer = response["message"]["content"]

        structured_contexts = [
            {
                "score": r["score"], "mission": r["mission"], "subsystem": r["subsystem"],
                "failure_mode": r["failure_mode"], "root_cause": r["root_cause"],
                "text": r["context"][:200], "related_failures": r.get("related_failures", []),
            }
            for r in results
        ]

        return {"question": payload.question, "synthesized_answer": answer, "retrieved_contexts": structured_contexts}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
def shutdown_event():
    close_driver()