"""
factor_extractor.py — evidence-anchored causal-factor extraction (Stage 4).

For one passage the local LLM proposes causal factors, each with a taxonomy
code (evalutation/benchmark/causal_taxonomy.json), a role and a VERBATIM quote.
A factor is kept only if it passes deterministic verification:

  V-code   code is a taxonomy subcategory
  V-role   role in {root, contributing, observation}
  V-quote  quote (>= MIN_QUOTE_WORDS words) occurs in the passage text, after
           whitespace/case/quote-mark normalisation; its exact character span in
           the passage is recorded, so every factor has page-level provenance

Rejected proposals are kept with their reason (the "-verification" ablation
uses them). LLM outputs are cached by prompt hash (cross-session
nondeterminism, Stages 1 and 3).

Development rule: prompts were written and checked on passages that are NOT in
the D1 benchmark sample (evalutation/benchmark/sheets.meta.json, d1.passage_ids).
"""

import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

ROOT = Path(__file__).resolve().parent.parent.parent
TAXONOMY_PATH = ROOT / "evalutation" / "benchmark" / "causal_taxonomy.json"
ROLES = ("root", "contributing", "observation")
MIN_QUOTE_WORDS = 5
NUM_CTX = 4096


def taxonomy() -> dict:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def codes() -> dict[str, dict]:
    return {c["code"]: {**c, "group": g["code"]} for g in taxonomy()["categories"] for c in g["children"]}


def _taxonomy_text() -> str:
    lines = []
    for g in taxonomy()["categories"]:
        for c in g["children"]:
            lines.append(f"{c['code']} {c['name']}: {c['desc']}")
    return "\n".join(lines)


SYSTEM = """You extract causal factors from passages of official spaceflight mishap investigation reports.
A causal factor is something the report states caused or contributed to the mishap, or a deficiency the board explicitly identifies.
Choose the code that best matches what went wrong (e.g. too few staff is M6, not H3).
Do NOT extract background facts, chronology, design descriptions or recommendations unless they state a cause or deficiency.

Taxonomy codes:
{taxonomy}

Roles: root (stated root, primary or proximate cause), contributing (contributing or intermediate cause, significant factor), observation (deficiency noted, not stated to have caused the mishap).

Respond with ONLY a JSON object:
{{"factors": [{{"code": "<code>", "role": "<root|contributing|observation>", "statement": "<what specifically went wrong in this mishap, at most 15 words; not the category name>", "quote": "<exact words copied from the passage, 8-40 words>"}}]}}
Return {{"factors": []}} if the passage states no causal factor."""

USER = """Report: {title}
Section: {section}
Passage:
\"\"\"{text}\"\"\""""


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _norm_with_map(s: str) -> tuple[str, list[int]]:
    """Lower-cased, whitespace-collapsed text plus a map from each normalised char to its original index."""
    out, idx, prev_space = [], [], False
    for i, ch in enumerate(s.translate(_QUOTES)):
        if ch.isspace():
            if prev_space or not out:
                continue
            out.append(" "); idx.append(i); prev_space = True
        else:
            out.append(ch.lower()); idx.append(i); prev_space = False
    return "".join(out), idx


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Character span of `quote` in `text` (normalised match), or None."""
    nt, m = _norm_with_map(text)
    nq, _ = _norm_with_map(quote.strip().strip('"').strip())
    if not nq:
        return None
    k = nt.find(nq)
    if k < 0:
        return None
    return m[k], m[k + len(nq) - 1] + 1


def verify(proposal: dict, text: str, valid_codes: set[str]) -> tuple[bool, str, tuple[int, int] | None]:
    if not isinstance(proposal, dict):
        return False, "not_object", None
    code = str(proposal.get("code", "")).strip().upper()
    if code not in valid_codes:
        return False, "bad_code", None
    if str(proposal.get("role", "")).strip().lower() not in ROLES:
        return False, "bad_role", None
    quote = str(proposal.get("quote", ""))
    if len(quote.split()) < MIN_QUOTE_WORDS:
        return False, "quote_too_short", None
    span = locate_quote(text, quote)
    if span is None:
        return False, "quote_not_in_passage", None
    return True, "ok", span


def _cache_path(model: str, prompt: str) -> Path:
    key = hashlib.sha256(f"{model}|{NUM_CTX}|{prompt}".encode("utf-8")).hexdigest()
    return get_settings().processed_dir / "factor_cache" / model.replace(":", "_") / key[:2] / f"{key}.json"


def _llm(system: str, user: str, model: str) -> tuple[str, bool]:
    prompt = system + "\n\n" + user
    cache = _cache_path(model, prompt)
    if cache.exists() and os.environ.get("MISSIONMIND_GEN_NO_CACHE") != "1":
        return json.loads(cache.read_text(encoding="utf-8"))["raw"], True
    import ollama
    s = get_settings()
    r = ollama.chat(model=model, format="json", messages=[{"role": "system", "content": system},
                                                          {"role": "user", "content": user}],
                    options={"temperature": s.llm_temperature, "seed": s.llm_seed, "num_ctx": NUM_CTX})
    raw = r["message"]["content"]
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(f".tmp{os.getpid()}")
        tmp.write_text(json.dumps({"raw": raw}), encoding="utf-8")
        os.replace(tmp, cache)
    return raw, False


def extract(unit, title: str, model: str | None = None) -> dict:
    """unit: retrieval.corpus.Unit (or any object with id, text, section, page, doc_id, missions)."""
    model = model or get_settings().llm_model
    system = SYSTEM.format(taxonomy=_taxonomy_text())
    user = USER.format(title=title, section=unit.section or "(none)", text=unit.text)
    raw, cached = _llm(system, user, model)
    try:
        proposals = json.loads(raw).get("factors", [])
        if not isinstance(proposals, list):
            proposals = []
        parse_ok = True
    except (json.JSONDecodeError, AttributeError):
        proposals, parse_ok = [], False
    valid, accepted, rejected = set(codes()), [], []
    for p in proposals:
        ok, reason, span = verify(p, unit.text, valid)
        rec = {"code": str(p.get("code", "")).strip().upper() if isinstance(p, dict) else None,
               "role": str(p.get("role", "")).strip().lower() if isinstance(p, dict) else None,
               "statement": str(p.get("statement", ""))[:200] if isinstance(p, dict) else None,
               "quote": str(p.get("quote", ""))[:500] if isinstance(p, dict) else None}
        if ok:
            accepted.append({**rec, "char_start": unit.char_start + span[0], "char_end": unit.char_start + span[1]})
        else:
            rejected.append({**rec, "reason": reason})
    return {"passage_id": unit.id, "doc_id": unit.doc_id, "page": unit.page, "missions": list(unit.missions),
            "field": unit.field, "model": model, "cached": cached, "parse_ok": parse_ok,
            "accepted": accepted, "rejected": rejected}
