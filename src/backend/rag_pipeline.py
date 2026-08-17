"""
rag_pipeline.py

CLI / standalone entry point for MissionMind Graph-RAG. Same retrieval logic
as main.py, both pulling from retriever.py — this is what was previously
duplicated between the two files.
"""

import sys
from pathlib import Path

import ollama

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from graph.retriever import GraphRAGRetriever

_PROMPT_TEMPLATE = """You are MissionMind, an advanced aerospace failure analysis AI assistant.
Use the following retrieved document chunks and Knowledge Graph FMEA insights — including any cross-mission patterns — to answer the user's diagnostic query accurately and professionally.
If the exact cause is listed in the Graph Intelligence, highlight it explicitly. If a cross-mission pattern is present, call it out by name.

CONTEXT:
{context}

USER QUERY:
{question}

ANSWER:
"""


class MissionMindGraphRAG:
    def __init__(self, model_name="llama3"):
        print("Initializing MissionMind Graph-RAG Engine...")
        self.retriever = GraphRAGRetriever()
        self.ollama_model = model_name

    def query(self, user_question: str):
        print(f"\n🔍 Processing Diagnostic Query: '{user_question}'")
        results = self.retriever.hybrid_search(user_question, top_k=3)
        aggregated_context = self.retriever.build_context_text(results)
        prompt = _PROMPT_TEMPLATE.format(context=aggregated_context, question=user_question)

        print(f"🤖 Synthesizing response using local Ollama ({self.ollama_model})...\n" + "=" * 60)
        response = ollama.chat(model=self.ollama_model, messages=[{"role": "user", "content": prompt}], stream=True)
        for chunk in response:
            print(chunk["message"]["content"], end="", flush=True)
        print("\n" + "=" * 60)

    def close(self):
        self.retriever.close()


if __name__ == "__main__":
    rag = MissionMindGraphRAG(model_name="llama3")
    rag.query("Provide a detailed breakdown of the O-ring failure during the Challenger launch and its root cause.")
    rag.close()