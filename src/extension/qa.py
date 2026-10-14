"""
qa.py — question answering for the D3 benchmark (B0, B3, P share prompt and schema).

Schema: {"answer": str, "key_points": [{"point": str, "evidence": [chunk ids]}], "abstain": bool}
  B0  no context; evidence must be empty
  B3  B3 passages (packed exactly as for RCA drafting)
  P   P passages + factor-graph analogies; citation enforcement (uncited points dropped,
      abstain when no cited point remains)
Outputs are cached by prompt hash (retrieval.rca_generation._chat).
"""

import hashlib
import json

from extension.grounded_generation import SPECIFIC, extract_mechanisms, graph_block, is_generic, mechanism_block
from retrieval import rca_generation as rg

SYSTEM_QA = """You answer questions for spaceflight mishap investigators.
Respond with ONLY a JSON object:
{"answer": "<2-6 sentences>", "key_points": [{"point": "<one fact>", "evidence": ["<chunk id>", ...]}], "abstain": <true|false>}
If the provided material does not answer the question, set "abstain": true and leave "key_points" empty."""

WITH_CONTEXT = """Excerpts from mishap investigation reports (each chunk: id, mission, document, field, page):

{context}
{graph}
QUESTION: {question}

Answer using only the excerpts. Every key point must cite the ids of the chunks that support it."""

NO_CONTEXT = """QUESTION: {question}

Answer from your own knowledge. No documents are provided, so every "evidence" list must be empty."""


def _enforce(ans, allowed: set[str], category_names: set[str] | None = None) -> tuple[dict | None, dict]:
    if not isinstance(ans, dict):
        return None, {"abstain": True, "dropped_points": 0, "removed_citations": 0, "generic_dropped": 0,
                      "points_raw": 0, "points_kept": 0}
    kept, dropped, removed, generic = [], 0, 0, 0
    raw_points = len(ans.get("key_points") or [])
    for kp in ans.get("key_points") or []:
        if not isinstance(kp, dict):
            dropped += 1
            continue
        ev = kp.get("evidence") or []
        ev = ev if isinstance(ev, list) else [ev]
        good = [rg.norm_cite(e) for e in ev if rg.norm_cite(e) in allowed]
        removed += len(ev) - len(good)
        if category_names and is_generic(kp.get("point", ""), category_names):
            generic += 1
            dropped += 1
            continue
        if good:
            kept.append({**kp, "evidence": good})
        else:
            dropped += 1
    abstain = bool(ans.get("abstain")) or not kept
    out = {"answer": "" if abstain else ans.get("answer", ""), "key_points": [] if abstain else kept, "abstain": abstain}
    return out, {"abstain": abstain, "dropped_points": dropped, "removed_citations": removed, "generic_dropped": generic,
                 "points_raw": raw_points, "points_kept": 0 if abstain else len(kept)}


def answer(system: str, question: str, passages: list[dict] | None = None, units_by_id: dict | None = None,
           graph: dict | None = None, code_names: dict | None = None, mission_evidence: dict | None = None,
           model: str | None = None) -> dict:
    from config import get_settings
    model = model or get_settings().llm_model
    chunk_map = {}
    if system == "B0":
        prompt = NO_CONTEXT.format(question=question)
    else:
        context, used = rg.pack_context(passages, units_by_id)
        chunk_map = {f"C{i}": uid for i, uid in enumerate(used, 1)}
        gtext = ""
        if system in ("P", "P2", "P2-2step") and graph is not None:
            chunk_of = {u: c for c, u in chunk_map.items()}
            gtext = ("\nCausal-factor analogies from a knowledge graph of verified board statements:\n"
                     + graph_block(graph, code_names or {}, mission_evidence or {}, chunk_of) + "\n")
        if system == "P2-2step":
            gtext += mechanism_block(extract_mechanisms(chunk_map, units_by_id, model))
        prompt = WITH_CONTEXT.format(context=context, graph=gtext, question=question)
    r = rg._chat(prompt, model, SYSTEM_QA + (SPECIFIC if system in ("P2", "P2-2step") else ""))
    try:
        raw = json.loads(r["raw"])
    except json.JSONDecodeError:
        raw = None
    if system in ("P", "P2", "P2-2step"):
        names = set((code_names or {}).values()) if system != "P" else None
        final, enf = _enforce(raw, set(chunk_map), names)
    else:
        final = raw if isinstance(raw, dict) else None
        enf = None
    return {"system": system, "model": model, "chunks_used": len(chunk_map), "chunk_map": chunk_map,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "cached": r["cached"],
            "answer": final, "raw_answer": raw, "enforcement": enf}
