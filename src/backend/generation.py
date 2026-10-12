"""
generation.py

The one prompt template and the one LLM call used by the API (main.py), the
CLI (rag_pipeline.py) and the evaluation runner — previously three slightly
different copies of the prompt existed, so results depended on which entry
point produced them.

Decoding settings (model, temperature, seed) come from config.py so that they
are recorded with every run.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

PROMPT_TEMPLATE = """You are MissionMind, an aerospace failure analysis assistant.
Answer the user's question using ONLY the context below: retrieved report excerpts and, where present, knowledge-graph facts and cross-mission patterns. Cite the source id in square brackets (e.g. [2]) for each claim. If the context does not contain the answer, say so.

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
"""

LLM_ONLY_TEMPLATE = """You are MissionMind, an aerospace failure analysis assistant.
Answer the question from your own knowledge. If you are not sure, say so.

QUESTION:
{question}

ANSWER:
"""


def build_prompt(question: str, context: str | None) -> str:
    if context is None:
        return LLM_ONLY_TEMPLATE.format(question=question)
    return PROMPT_TEMPLATE.format(context=context, question=question)


def decoding_options() -> dict:
    s = get_settings()
    return {"temperature": s.llm_temperature, "seed": s.llm_seed}


def generate(prompt: str, model: str | None = None, stream: bool = False):
    """Single place that calls Ollama. Returns the answer text, or the raw
    stream iterator when stream=True."""
    import ollama
    model = model or get_settings().llm_model
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}],
                           options=decoding_options(), stream=stream)
    if stream:
        return response
    return response["message"]["content"]
