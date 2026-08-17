"""
run_eval.py

Runs the MissionMind Graph-RAG evaluation suite end-to-end and saves a results
summary covering all three tracks in metrics.py:
  1. Extraction quality  (graph_builder.py vs hand-labeled chunks)
  2. Retrieval quality   (vector search vs hand-labeled relevant chunks)
  3. Answer quality      (Graph-RAG vs plain vector RAG, LLM-judged)

Expects evalutation/test_data.json (template below).

ADAPTER NOTE: the three functions in the ADAPTER section talk to Neo4j/Ollama
directly rather than importing from retriever.py/rag_pipeline.py, since I don't
have the current content of those files after the graph/neo4j_connector split.
If they've since diverged (index name, node labels), fix the Cypher there —
nothing below that section needs to change.
"""

import json
import sys
from pathlib import Path

from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer
import ollama

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from graph.graph_builder import extract_failure_data  # noqa: E402
from metrics import (  # noqa: E402
    extraction_metrics, retrieval_metrics, aggregate_retrieval_metrics,
    llm_judge_score, aggregate_judge_scores,
)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "password"

TEST_DATA_PATH = Path(__file__).resolve().parent / "test_data.json"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"

GENERATION_MODEL = "llama3"
JUDGE_MODEL = "llama3"


# ---------------------------------------------------------------------------
# ADAPTER
# ---------------------------------------------------------------------------

_embedder = SentenceTransformer('all-MiniLM-L6-v2')
_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))


def vector_search_chunk_ids(question: str, top_k: int = 3) -> list[str]:
    """Vector search only, ranked chunk ids — used for retrieval_metrics()."""
    embedding = _embedder.encode(question, show_progress_bar=False).tolist()
    with _driver.session() as session:
        result = session.run("""
            CALL db.index.vector.queryNodes('chunk_vector_index', $top_k, $embedding)
            YIELD node AS chunk, score
            RETURN chunk.id AS chunk_id
            ORDER BY score DESC
        """, {"embedding": embedding, "top_k": top_k})
        return [record["chunk_id"] for record in result]


def answer_plain_rag(question: str) -> str:
    """Baseline for the ablation: chunk text only, no graph traversal, no FMEA fields."""
    embedding = _embedder.encode(question, show_progress_bar=False).tolist()
    with _driver.session() as session:
        result = session.run("""
            CALL db.index.vector.queryNodes('chunk_vector_index', 3, $embedding)
            YIELD node AS chunk, score
            RETURN chunk.text AS text
        """, {"embedding": embedding})
        context = "\n---\n".join(r["text"] for r in result)

    prompt = f"Answer the question using only this context.\n\nCONTEXT:\n{context}\n\nQUESTION:\n{question}\n\nANSWER:"
    response = ollama.chat(model=GENERATION_MODEL, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]


def answer_graph_rag(question: str) -> str:
    """Full pipeline: vector search + graph traversal for FMEA context."""
    embedding = _embedder.encode(question, show_progress_bar=False).tolist()
    with _driver.session() as session:
        result = session.run("""
            CALL db.index.vector.queryNodes('chunk_vector_index', 3, $embedding)
            YIELD node AS chunk, score
            OPTIONAL MATCH (chunk)-[:MENTIONS]->(fm:FailureMode)
            OPTIONAL MATCH (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s:Subsystem)
            OPTIONAL MATCH (fm)-[:CAUSED_BY]->(rc:RootCause)
            OPTIONAL MATCH (m:Mission)-[:EXPERIENCED_FAILURE]->(fm)
            RETURN chunk.text AS text, m.name AS mission, s.name AS subsystem,
                   fm.name AS failure_mode, rc.description AS root_cause
        """, {"embedding": embedding})
        blocks = []
        for r in result:
            block = f"Text Snippet: {r['text']}\n"
            if r["failure_mode"]:
                block += (f"[Graph Intelligence] Mission: {r['mission']} | Subsystem: {r['subsystem']} | "
                          f"Failure Mode: {r['failure_mode']} | Root Cause: {r['root_cause']}\n")
            blocks.append(block)
        context = "\n---\n".join(blocks)

    prompt = f"Answer the question using only this context.\n\nCONTEXT:\n{context}\n\nQUESTION:\n{question}\n\nANSWER:"
    response = ollama.chat(model=GENERATION_MODEL, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"]


# ---------------------------------------------------------------------------
# Evaluation tracks
# ---------------------------------------------------------------------------

def run_extraction_eval(gold_chunks: list[dict]) -> dict:
    print(f"\n{'='*60}\n1. EXTRACTION QUALITY  ({len(gold_chunks)} labeled chunks)\n{'='*60}")
    predictions = []
    for item in gold_chunks:
        pred = extract_failure_data(item["text"])
        pred["chunk_id"] = item["chunk_id"]
        predictions.append(pred)
    result = extraction_metrics(predictions, gold_chunks)
    print(json.dumps(result, indent=2))
    return result


def run_retrieval_eval(test_queries: list[dict]) -> dict:
    print(f"\n{'='*60}\n2. RETRIEVAL QUALITY  ({len(test_queries)} test questions)\n{'='*60}")
    per_query = []
    for q in test_queries:
        retrieved = vector_search_chunk_ids(q["question"], top_k=3)
        m = retrieval_metrics(retrieved, set(q["relevant_chunk_ids"]), k=3)
        print(f"  {q['question'][:60]!r}: {m}")
        per_query.append(m)
    result = aggregate_retrieval_metrics(per_query)
    print(json.dumps(result, indent=2))
    return result


def run_ablation_eval(test_queries: list[dict]) -> dict:
    print(f"\n{'='*60}\n3. ANSWER QUALITY — Graph-RAG vs Plain RAG  ({len(test_queries)} questions)\n{'='*60}")
    plain_scores, graph_scores = [], []
    for q in test_queries:
        question = q["question"]
        plain_scores.append(llm_judge_score(question, answer_plain_rag(question), judge_model=JUDGE_MODEL))
        graph_scores.append(llm_judge_score(question, answer_graph_rag(question), judge_model=JUDGE_MODEL))
        print(f"  ✓ {question[:60]!r}")

    result = {"plain_rag": aggregate_judge_scores(plain_scores), "graph_rag": aggregate_judge_scores(graph_scores)}
    print(json.dumps(result, indent=2))
    return result


def main():
    if not TEST_DATA_PATH.exists():
        print(f"No test set found at {TEST_DATA_PATH}. Fill in the template next to this file first.")
        return

    with open(TEST_DATA_PATH, "r", encoding="utf-8") as f:
        test_data = json.load(f)

    results = {
        "extraction": run_extraction_eval(test_data["labeled_chunks"]),
        "retrieval": run_retrieval_eval(test_data["test_queries"]),
        "ablation": run_ablation_eval(test_data["test_queries"]),
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n{'='*60}\nSaved full results to {RESULTS_PATH}")


if __name__ == "__main__":
    main()