"""
grounded_generation.py — citation-constrained RCA drafting for P (Stage 4).

Same JSON schema and chunk packing as the B3 generator (retrieval.rca_generation),
plus:
  - a short block of factor-graph analogies (missions sharing verified causal-factor
    categories with the query, with the chunk ids of their evidence when shown);
  - post-hoc enforcement: citations to ids not shown are removed; items left without
    any valid citation are dropped; if no root cause and no precedent remains, the
    answer ABSTAINS ("insufficient evidence") instead of returning ungrounded text.
The raw model answer is kept next to the enforced one, so the effect of enforcement
is measurable (ablation "-citation constraint").
"""

import copy
import hashlib
import json

from retrieval import rca_generation as rg

SYSTEM_P = rg.SYSTEM + ("\nEvery item MUST cite at least one chunk id that directly supports it. Items without "
                        "support are discarded automatically, so do not include them.")

GROUNDED_P = """Precedent evidence from earlier mishap investigation reports (each chunk: id, mission, document, field, page):

{context}

Causal-factor analogies found in a knowledge graph built from verified board statements
(missions that share causal-factor categories with the new mishap):
{graph}

NEW MISHAP DESCRIPTION:
\"\"\"{query}\"\"\"

Draft the root cause analysis for the NEW mishap. Every item must cite the ids of the chunks that support it in "evidence". Use only chunk ids shown above."""

KEYS = ("probable_root_causes", "contributing_factors", "similar_precedents", "recommended_actions")

# P2 generation (fixed 2026-10-13 after the pilot: 21/43 of P's causes were bare category names)
SPECIFIC = ("\nEach cause, factor and action must name the SPECIFIC component, process or decision that failed and "
            "HOW it led to the mishap, in the words of the evidence. A taxonomy category name alone (for example "
            "'Procedure deficient or not followed') is NOT an acceptable cause and will be discarded.")


def is_generic(text: str, category_names: set[str]) -> bool:
    """True when an item is only a taxonomy category name (optionally with a code prefix or a few words)."""
    s = " ".join(str(text).lower().replace("/", " ").split()).strip(" .:-")
    for name in category_names:
        n = " ".join(name.lower().replace("/", " ").split())
        if s == n or (s.startswith(n) and len(s.split()) <= len(n.split()) + 2) or s.endswith(n) and len(s.split()) <= len(n.split()) + 2:
            return True
    return False


def graph_block(graph: dict, code_names: dict, mission_evidence: dict, chunk_of: dict) -> str:
    lines = []
    for m, s in list(graph.get("mission_analogy", {}).items())[:5]:
        shared = mission_evidence.get(m, {})
        parts = []
        for code in sorted(shared):
            cids = sorted({chunk_of[p] for p in shared[code] if p in chunk_of}, key=lambda c: int(c[1:]))
            parts.append(f"{code} {code_names.get(code, '')}" + (f" (chunks {', '.join(cids)})" if cids else ""))
        lines.append(f"- {m} (analogy {s:.2f}): " + "; ".join(parts))
    return "\n".join(lines) if lines else "- none found"


def enforce(answer, allowed: set[str], category_names: set[str] | None = None) -> tuple[dict | None, dict]:
    """category_names given (P2): items whose text is only a category name are dropped and counted."""
    if not isinstance(answer, dict):
        return None, {"abstain": True, "dropped_items": 0, "removed_citations": 0, "generic_dropped": 0}
    out, dropped, removed, generic = copy.deepcopy(answer), 0, 0, 0
    for k in KEYS:
        kept = []
        for it in out.get(k) or []:
            if not isinstance(it, dict):
                dropped += 1
                continue
            ev = it.get("evidence") or []
            ev = ev if isinstance(ev, list) else [ev]
            good = [rg.norm_cite(e) for e in ev if rg.norm_cite(e) in allowed]
            removed += len(ev) - len(good)
            text = it.get("cause") or it.get("factor") or it.get("action") or ""
            if category_names and k != "similar_precedents" and is_generic(text, category_names):
                generic += 1
                dropped += 1
                continue
            if good:
                kept.append({**it, "evidence": good})
            else:
                dropped += 1
        out[k] = kept
    abstain = not out["probable_root_causes"] and not out["similar_precedents"]
    if abstain:
        out = {k: [] for k in KEYS} | {"abstained": "insufficient evidence in the retrieved precedents"}
    return out, {"abstain": abstain, "dropped_items": dropped, "removed_citations": removed, "generic_dropped": generic}


def draft_rca_p(query: str, passages: list[dict], units_by_id: dict, graph: dict, code_names: dict,
                mission_evidence: dict, model: str | None = None, specific: bool = False) -> dict:
    from config import get_settings
    model = model or get_settings().llm_model
    context, used = rg.pack_context(passages, units_by_id)
    chunk_map = {f"C{i}": uid for i, uid in enumerate(used, 1)}
    chunk_of = {uid: c for c, uid in chunk_map.items()}
    prompt = GROUNDED_P.format(context=context, graph=graph_block(graph, code_names, mission_evidence, chunk_of),
                               query=query)
    r = rg._chat(prompt, model, SYSTEM_P + (SPECIFIC if specific else ""))
    try:
        raw_answer = json.loads(r["raw"])
    except json.JSONDecodeError:
        raw_answer = None
    enforced, stats = enforce(raw_answer, set(chunk_map), set(code_names.values()) if specific else None)
    return {"model": model, "chunks_used": len(chunk_map), "chunk_map": chunk_map,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_eval_count": r.get("prompt_eval_count"), "cached": r["cached"],
            "answer": enforced, "raw_answer": raw_answer, "enforcement": stats,
            "checks": rg.validate(enforced if enforced and not stats["abstain"] else None, set(chunk_map))
            if not stats["abstain"] else {"schema_ok": True, "citations": 0, "invalid_citations": 0,
                                          "items": 0, "uncited_items": 0},
            "checks_raw": rg.validate(raw_answer, set(chunk_map))}
