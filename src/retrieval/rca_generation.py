"""
rca_generation.py — precedent-grounded root-cause-analysis drafting (base paper's
generation step) and its LLM-only baseline (B0), with one shared JSON schema.

Base paper: top-40 chunks by RRF score, each annotated with case id and field
type; temperature 0; strict JSON enforced by system prompting; generator
Qwen3-Next-80B-A3B-Instruct. MissionMind (recorded deviations):
  - generator: local Ollama model (config MISSIONMIND_LLM_MODEL, llama3 8B Q4_0);
  - context: llama3 has an 8,192-token window, so chunks are packed in rank order
    up to CONTEXT_WORD_BUDGET words (at most TOP_K_GEN = 40); the number actually
    used is recorded per query;
  - annotations add mission, document and page (needed for page-level citations);
  - the paper's prompt text is not published, so the prompt below is ours.
Outputs are cached by prompt hash (LLM output is not reproducible across
sessions — Stage 1 finding), so re-runs return identical answers.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

TOP_K_GEN = 40
CONTEXT_WORD_BUDGET = 4200     # ~5.7k tokens of context + prompt/answer within num_ctx 8192
NUM_CTX = 8192
FIELD_NAME = {"summary": "Summary", "causes": "Causes", "disposition": "Disposition"}

SCHEMA_TEXT = """{
  "probable_root_causes": [{"cause": "<text>", "evidence": ["<chunk id>", ...]}],
  "contributing_factors": [{"factor": "<text>", "evidence": ["<chunk id>", ...]}],
  "similar_precedents": [{"mission": "<mission>", "similarity": "<why it is analogous>", "evidence": ["<chunk id>", ...]}],
  "recommended_actions": [{"action": "<text>", "evidence": ["<chunk id>", ...]}]
}"""

SYSTEM = ("You are an assistant to a spaceflight mishap investigation board. You draft a root cause analysis "
          "for a NEW mishap. Respond with ONLY a JSON object that follows this schema exactly:\n" + SCHEMA_TEXT)

GROUNDED = """Precedent evidence from earlier mishap investigation reports (each chunk: id, mission, document, field, page):

{context}

NEW MISHAP DESCRIPTION:
\"\"\"{query}\"\"\"

Using the precedent chunks as evidence, draft the root cause analysis for the NEW mishap. Every item must cite the ids of the chunks that support it in "evidence". Use only the chunk ids shown above. If the precedents do not support an item, leave the list empty rather than guessing."""

LLM_ONLY = """NEW MISHAP DESCRIPTION:
\"\"\"{query}\"\"\"

Draft the root cause analysis for the NEW mishap from your own knowledge. No precedent documents are provided, so every "evidence" list must be empty."""


def pack_context(passages: list[dict], units_by_id: dict) -> tuple[str, list[str]]:
    lines, used, words = [], [], 0
    for p in passages[:TOP_K_GEN]:
        u = units_by_id[p["id"]]
        n = len(u.text.split())
        if used and words + n > CONTEXT_WORD_BUDGET:
            break
        cid = f"C{len(used) + 1}"
        lines.append(f"[{cid}] mission={'/'.join(u.missions)} | doc={u.doc_id} | field={FIELD_NAME[u.field]} | "
                     f"page={u.page}\n{u.text}")
        used.append(u.id)
        words += n
    return "\n\n".join(lines), used


def _cache_path(model: str, prompt: str) -> Path:
    key = hashlib.sha256(f"{model}|{NUM_CTX}|{SYSTEM}|{prompt}".encode("utf-8")).hexdigest()
    return get_settings().processed_dir / "gen_cache" / model.replace(":", "_") / f"{key}.json"


def _chat(prompt: str, model: str) -> dict:
    cache = _cache_path(model, prompt)
    if cache.exists():
        return {**json.loads(cache.read_text(encoding="utf-8")), "cached": True}
    import ollama
    s = get_settings()
    r = ollama.chat(model=model, format="json",
                    messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                    options={"temperature": s.llm_temperature, "seed": s.llm_seed, "num_ctx": NUM_CTX})
    out = {"raw": r["message"]["content"], "prompt_eval_count": r.get("prompt_eval_count"),
           "eval_count": r.get("eval_count")}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(out), encoding="utf-8")
    return {**out, "cached": False}


def validate(answer: dict | None, allowed_ids: set[str]) -> dict:
    """Schema and citation checks: every cited id must be one of the chunks shown."""
    keys = ("probable_root_causes", "contributing_factors", "similar_precedents", "recommended_actions")
    if not isinstance(answer, dict):
        return {"schema_ok": False, "citations": 0, "invalid_citations": 0, "items": 0, "uncited_items": 0}
    cites = items = uncited = invalid = 0
    schema_ok = all(isinstance(answer.get(k), list) for k in keys)
    for k in keys:
        for it in answer.get(k) or []:
            if not isinstance(it, dict):
                schema_ok = False
                continue
            items += 1
            ev = it.get("evidence") or []
            ev = ev if isinstance(ev, list) else [ev]
            cites += len(ev)
            invalid += sum(1 for e in ev if str(e) not in allowed_ids)
            uncited += not ev
    return {"schema_ok": schema_ok, "citations": cites, "invalid_citations": invalid,
            "items": items, "uncited_items": uncited}


def draft_rca(query: str, passages: list[dict] | None, units_by_id: dict | None, model: str | None = None) -> dict:
    """passages=None -> LLM-only baseline (B0)."""
    model = model or get_settings().llm_model
    if passages is None:
        prompt, chunk_map = LLM_ONLY.format(query=query), {}
    else:
        context, used = pack_context(passages, units_by_id)
        prompt = GROUNDED.format(context=context, query=query)
        chunk_map = {f"C{i}": uid for i, uid in enumerate(used, 1)}
    r = _chat(prompt, model)
    try:
        answer = json.loads(r["raw"])
    except json.JSONDecodeError:
        answer = None
    return {"model": model, "chunks_used": len(chunk_map), "chunk_map": chunk_map,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_eval_count": r.get("prompt_eval_count"), "cached": r["cached"],
            "answer": answer, "raw_if_unparsed": None if answer is not None else r["raw"],
            "checks": validate(answer, set(chunk_map))}
