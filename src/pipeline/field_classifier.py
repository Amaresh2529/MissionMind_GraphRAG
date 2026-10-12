"""
field_classifier.py — LLM assignment of pseudo-fields to report sections.

Stage 2 measured the heading-keyword rules (page_parser.assign_pseudo_field)
at 0.52 section-level / 0.66 word-weighted accuracy on a 100-section dev
sample — far below the 0.90 target — so this module classifies each section
(heading + chapter + opening text) with the local LLM, using the same label
definitions as the human/assistant labelling guideline.

Policy "hybrid": sections whose heading/chapter matches the explicit
front/back-matter rule list keep "other"; every other section is classified
by the LLM. Outputs are cached per prompt hash (LLM output is not
reproducible across sessions — Stage 1 finding), so re-runs are identical.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from pipeline.page_parser import FIELD_RULES

LABELS = ["summary", "narrative", "findings", "causes", "recommendations", "other"]

PROMPT = """You label sections of official spaceflight accident/mishap investigation reports.
Choose exactly ONE label for the section below.

Labels:
- summary: an overview of the whole report or its overall conclusions (executive summary, synopsis of conclusions).
- narrative: description of the mission, vehicle, systems, organisation history, or the sequence/chronology of events (what happened, when, who was involved in the events).
- findings: analysis, investigation results, evidence, tests, discussion and observations that are NOT stated as the cause.
- causes: text that states or argues the cause, root cause, contributing causes or failure mechanism of the accident/mishap.
- recommendations: recommendations, lessons learned, corrective actions, actions required before return to flight.
- other: front/back matter and non-content: title page, contents, preface, member/staff lists, biographies, acknowledgements, appendices about administration, references, endnotes, acronym lists, figure or table residue, OCR noise.

Report: {doc_title}
Chapter heading: {chapter}
Section heading: {section}
Section text (beginning):
\"\"\"{excerpt}\"\"\"

Respond with ONLY a JSON object: {{"label": "<one of: summary, narrative, findings, causes, recommendations, other>"}}"""


def _cache_file(doc_id: str) -> Path:
    return get_settings().processed_dir / "field_cache" / f"{doc_id}.json"


def rule_says_other(section: str | None, chapter: str | None) -> bool:
    other_keys = FIELD_RULES[0][1]
    return any(k in (h or "").lower() for h in (section, chapter) for k in other_keys)


def classify_section(doc_id: str, doc_title: str, section: str | None, chapter: str | None,
                     excerpt: str, cache: dict, model: str | None = None) -> str:
    s = get_settings()
    model = model or s.llm_model
    prompt = PROMPT.format(doc_title=doc_title, chapter=chapter or "(none)", section=section or "(none)",
                           excerpt=excerpt[:1200])
    key = hashlib.sha256(f"{model}|{prompt}".encode("utf-8")).hexdigest()
    if key in cache:
        return cache[key]
    import ollama
    resp = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}], format="json",
                       options={"temperature": 0, "seed": s.llm_seed})
    try:
        label = json.loads(resp["message"]["content"]).get("label", "").strip().lower()
    except json.JSONDecodeError:
        label = ""
    label = label if label in LABELS else "other"
    cache[key] = label
    return label


def classify_document(doc_id: str, doc_title: str, policy: str = "hybrid") -> dict[tuple, str]:
    """Returns {(section, chapter): label} for every section of a document's
    passages; persists the LLM cache."""
    s = get_settings()
    passages = [json.loads(l) for l in open(s.processed_dir / "passages" / f"{doc_id}.jsonl", encoding="utf-8")]
    first = {}
    for p in passages:
        first.setdefault((p["section"], p["chapter"]), p)
    cache_path = _cache_file(doc_id)
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    labels = {}
    try:
        for (sec, chap), p in first.items():
            if policy == "hybrid" and rule_says_other(sec, chap):
                labels[(sec, chap)] = "other"
            elif sec is None and chap is None:
                labels[(sec, chap)] = "other"
            else:
                labels[(sec, chap)] = classify_section(doc_id, doc_title, sec, chap, p["text"], cache)
    finally:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return labels
