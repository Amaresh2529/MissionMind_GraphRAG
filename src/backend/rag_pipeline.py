"""
rag_pipeline.py

CLI entry point for MissionMind Graph-RAG. Same retrieval (graph/retriever.py)
and same prompt/decoding (backend/generation.py) as the API.

Usage (from the repository root):
    python src/backend/rag_pipeline.py "What caused the Ariane 5 Flight 501 failure?"
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from graph.retriever import GraphRAGRetriever
from graph.neo4j_connector import close_driver
from backend.generation import build_prompt, generate


class MissionMindGraphRAG:
    def __init__(self, model_name: str | None = None, top_k: int = 3):
        print("Initializing MissionMind Graph-RAG Engine...")
        self.retriever = GraphRAGRetriever()
        self.model = model_name or get_settings().llm_model
        self.top_k = top_k

    def query(self, user_question: str, stream: bool = True) -> str:
        print(f"\n🔍 Processing Diagnostic Query: '{user_question}'")
        results = self.retriever.hybrid_search(user_question, top_k=self.top_k)
        prompt = build_prompt(user_question, self.retriever.build_context_text(results))
        print(f"🤖 Synthesizing response using local Ollama ({self.model})...\n" + "=" * 60)
        if not stream:
            answer = generate(prompt, model=self.model)
            print(answer)
        else:
            parts = []
            for chunk in generate(prompt, model=self.model, stream=True):
                piece = chunk["message"]["content"]
                parts.append(piece)
                print(piece, end="", flush=True)
            answer = "".join(parts)
        print("\n" + "=" * 60)
        print("Sources: " + ", ".join(r["chunk_id"] for r in results))
        return answer

    def close(self):
        self.retriever.close()
        close_driver()


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or (
        "Provide a detailed breakdown of the O-ring failure during the Challenger launch and its root cause.")
    rag = MissionMindGraphRAG()
    try:
        rag.query(question)
    finally:
        rag.close()
