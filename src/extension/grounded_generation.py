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


MECH_SYSTEM = ('You read one excerpt from a spaceflight mishap investigation report. Respond with ONLY a JSON object '
               '{"mechanism": "<one sentence copied EXACTLY from the excerpt that states a specific failure, defect, '
               'error or causal mechanism>"} or {"mechanism": "NONE"} if the excerpt states none.')


def extract_mechanisms(chunk_map: dict, units_by_id: dict, model: str) -> dict:
    """Step 1 of two-step generation (protocol section 10): one verbatim mechanism sentence per chunk, kept only if
    it is found in the chunk text (same quote check as factor extraction)."""
    from extension.factor_extractor import locate_quote
    out = {}
    for cid, uid in chunk_map.items():
        text = units_by_id[uid].text
        r = rg._chat(f"Excerpt:\n\"\"\"{text}\"\"\"", model, MECH_SYSTEM)
        try:
            m = str(json.loads(r["raw"]).get("mechanism", "")).strip()
        except (json.JSONDecodeError, AttributeError):
            m = ""
        if m and m.upper() != "NONE" and len(m.split()) >= 5:
            span = locate_quote(text, m)
            if span:
                out[cid] = text[span[0]:span[1]]
    return out


def mechanism_block(mechs: dict) -> str:
    if not mechs:
        return ""
    lines = [f"[{c}] {s}" for c, s in sorted(mechs.items(), key=lambda x: int(x[0][1:]))]
    return ("\nSpecific mechanisms copied verbatim from the evidence (use these to state WHAT failed; cite the chunk id):\n"
            + "\n".join(lines) + "\n")


# P2-2step-hyp (protocol section 11): causes are hypotheses attributed to a named precedent mission
HYPOTHESIS = ("\nIMPORTANT: the NEW mishap's own investigation is NOT available. A precedent's mechanism is NOT the cause of "
              "the new mishap; it is only a hypothesis to investigate. For every root cause and contributing factor give "
              "\"statement\" (the specific mechanism), \"type\": \"analogy_hypothesis\", \"precedent_mission\" (the "
              "mission of the chunk you cite) and \"evidence\" (chunk ids). Use \"type\": \"established\" ONLY if a cited "
              "chunk is from the new mishap itself.")
TYPES = ("established", "analogy_hypothesis", "insufficient_evidence")


def _norm_mission(s: str) -> str:
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def enforce_hypotheses(answer, chunk_map: dict, units_by_id: dict, query_missions: set[str],
                       category_names: set[str], mission_names: dict) -> tuple[dict | None, dict]:
    """Deterministic rules of protocol section 11 for root causes / contributing factors; the other keys follow P2."""
    base, stats = enforce(answer, set(chunk_map), category_names)
    stats.update({"relabelled_established": 0, "precedent_corrected": 0, "hypothesis_items": 0, "established_items": 0})
    if base is None or stats["abstain"]:
        return base, stats
    out = dict(base)
    for k, field in (("probable_root_causes", "cause"), ("contributing_factors", "factor")):
        items = []
        for it in base.get(k) or []:
            cited = [chunk_map[c] for c in it["evidence"] if c in chunk_map]
            cited_m = []
            for uid in cited:
                for m in units_by_id[uid].missions:
                    if m not in cited_m:
                        cited_m.append(m)
            typ = str(it.get("type", "")).strip().lower()
            typ = typ if typ in TYPES else "analogy_hypothesis"
            if typ == "established" and not (set(cited_m) & query_missions):
                typ = "analogy_hypothesis"
                stats["relabelled_established"] += 1
            if typ == "insufficient_evidence":
                typ = "analogy_hypothesis"
            pm_raw = str(it.get("precedent_mission", ""))
            pm = next((m for m in cited_m if _norm_mission(m) == _norm_mission(pm_raw)
                       or _norm_mission(mission_names.get(m, "")) == _norm_mission(pm_raw)), None)
            if pm is None:
                pm = cited_m[0] if cited_m else None
                stats["precedent_corrected"] += 1
            text = str(it.get("statement") or it.get(field) or "").strip()
            low = text.lower()
            if low.startswith("by analogy with") and ":" in text:
                text = text.split(":", 1)[1].strip()
            if typ == "established":
                stats["established_items"] += 1
                rendered = text
            else:
                stats["hypothesis_items"] += 1
                rendered = f"By analogy with {mission_names.get(pm, pm)}: {text}"
            items.append({field: rendered, "type": typ, "precedent_mission": pm, "evidence": it["evidence"]})
        out[k] = items
    return out, stats


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
        return None, {"abstain": True, "dropped_items": 0, "removed_citations": 0, "generic_dropped": 0,
                      "cause_items_raw": 0, "cause_items_kept": 0}
    out, dropped, removed, generic = copy.deepcopy(answer), 0, 0, 0
    raw_causes = sum(len(answer.get(k) or []) for k in ("probable_root_causes", "contributing_factors"))
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
            text = it.get("cause") or it.get("factor") or it.get("action") or it.get("statement") or ""
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
    kept_causes = 0 if abstain else sum(len(out.get(k) or []) for k in ("probable_root_causes", "contributing_factors"))
    return out, {"abstain": abstain, "dropped_items": dropped, "removed_citations": removed, "generic_dropped": generic,
                 "cause_items_raw": raw_causes, "cause_items_kept": kept_causes}


def draft_rca_p(query: str, passages: list[dict], units_by_id: dict, graph: dict, code_names: dict,
                mission_evidence: dict, model: str | None = None, specific: bool = False,
                two_step: bool = False, hypothesis: bool = False, query_missions: set[str] | None = None,
                mission_names: dict | None = None, top_missions: list[str] | None = None) -> dict:
    from config import get_settings
    model = model or get_settings().llm_model
    context, used = rg.pack_context(passages, units_by_id)
    chunk_map = {f"C{i}": uid for i, uid in enumerate(used, 1)}
    chunk_of = {uid: c for c, uid in chunk_map.items()}
    mechs = extract_mechanisms(chunk_map, units_by_id, model) if two_step else {}
    prompt = GROUNDED_P.format(context=context, graph=graph_block(graph, code_names, mission_evidence, chunk_of)
                               + mechanism_block(mechs), query=query)
    r = rg._chat(prompt, model, SYSTEM_P + (SPECIFIC if specific else "") + (HYPOTHESIS if hypothesis else ""))
    try:
        raw_answer = json.loads(r["raw"])
    except json.JSONDecodeError:
        raw_answer = None
    if hypothesis:
        enforced, stats = enforce_hypotheses(raw_answer, chunk_map, units_by_id, query_missions or set(),
                                             set(code_names.values()), mission_names or {})
        if enforced and not stats["abstain"] and top_missions is not None:
            pms = [it.get("precedent_mission") for k in ("probable_root_causes", "contributing_factors")
                   for it in enforced.get(k) or []]
            stats["precedent_in_top5"] = sum(1 for m in pms if m in top_missions[:5])
            stats["precedent_items"] = len(pms)
    else:
        enforced, stats = enforce(raw_answer, set(chunk_map), set(code_names.values()) if specific else None)
    return {"model": model, "chunks_used": len(chunk_map), "chunk_map": chunk_map,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_eval_count": r.get("prompt_eval_count"), "cached": r["cached"],
            "answer": enforced, "raw_answer": raw_answer, "enforcement": stats, "mechanisms": mechs,
            "checks": rg.validate(enforced if enforced and not stats["abstain"] else None, set(chunk_map))
            if not stats["abstain"] else {"schema_ok": True, "citations": 0, "invalid_citations": 0,
                                          "items": 0, "uncited_items": 0},
            "checks_raw": rg.validate(raw_answer, set(chunk_map))}
