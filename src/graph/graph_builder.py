"""
graph_builder.py

Builds the FMEA knowledge graph from chunked report text.

Extraction strategy (two-tier, per the project's own stack table):
  1. NER (ner_model.py) — primary. Fast, deterministic, and — critically —
     it only asserts what's actually present in the text.
  2. LLM fallback — only runs on chunks where NER found nothing usable.
     Catches phrasing the seeded gazetteer doesn't cover yet.

Graph construction, two passes:
  Pass 1 — per-chunk extraction, writes Mission/Subsystem/FailureMode/RootCause
           nodes and the same structural edges as before.
  Pass 2 — once every failure record is known, compares them pairwise via BERT
           embeddings (embeddings.py) and writes SIMILAR_ROOT_CAUSE edges
           between DIFFERENT missions' failure nodes. This is the edge type
           that makes cross-mission queries answerable at all.
"""

import json
import re
import sys
import time
from pathlib import Path
import ollama

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from models.ner_model import FailureNER, ROOT_CAUSE_CATEGORIES
from models.embeddings import FailureRecord, find_cross_mission_similarities, DEFAULT_SIMILARITY_THRESHOLD
from graph.neo4j_connector import get_driver, close_driver

# Maps a chunk's source document_id (== PDF filename stem) to a display mission
# name. This is provenance labeling, not content inference — unlike the old
# EXTRACTION_RULES, it never asserts a subsystem/failure_mode/root_cause from
# a keyword match. Add an entry here whenever you add a new PDF to data/raw;
# anything not listed just falls back to a cleaned-up version of the filename.
MISSION_NAME_MAP = {
    "Challenger": "STS-51-L Challenger",
    "NASA_Columbia_CAIB_Vol1": "STS-107 Columbia",
    "Ariane_5_Flight_501_Failure_Inquiry_Board_Report.": "Ariane 5 Flight 501",
    "Mars_Climate_Orbiter": "Mars Climate Orbiter",
    "ExoMars_2016_Schiaparelli_Module_Trajectory": "ExoMars 2016 Schiaparelli",
    # "MPL_report": "Mars Polar Lander",              # add once that PDF is in
    # "Chandrayaan2_analysis": "Chandrayaan-2 Vikram", # add once that PDF is in
}

_LLM_EXTRACTION_PROMPT = """You are an aerospace failure-analysis engineer. Read the excerpt below.

Decide whether it describes a specific engineering failure (mission, subsystem, failure mode, root cause). Reports may contain unrelated material — in that case, no failure data should be extracted.

Respond with ONLY a JSON object:
{{
  "has_failure_data": true or false,
  "mission": "<mission or program name, or null>",
  "subsystem": "<subsystem or component involved, or null>",
  "failure_mode": "<the specific technical failure mode, or null>",
  "root_cause": "<the root cause identified in the text, or null>"
}}

If has_failure_data is false, all other fields must be null. Do not invent a mission or cause not directly supported by the excerpt.

EXCERPT:
\"\"\"{chunk_text}\"\"\"
"""


def _llm_fallback_extract(chunk_text: str, model: str | None = None) -> dict:
    """Only called when NER found nothing — see extract_failure_data()."""
    s = get_settings()
    response = ollama.chat(
        model=model or s.llm_model,
        messages=[{"role": "user", "content": _LLM_EXTRACTION_PROMPT.format(chunk_text=chunk_text)}],
        format="json",
        options={"temperature": 0, "seed": s.llm_seed}
    )
    try:
        data = json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        return {"has_failure_data": False}
    if not data.get("has_failure_data"):
        return {"has_failure_data": False}
    if not all(data.get(k) for k in ("mission", "subsystem", "failure_mode", "root_cause")):
        return {"has_failure_data": False}
    return data


def _extract_cause_sentence(text: str, category: str) -> str | None:
    """Pulls the actual sentence containing the matched root-cause keyword,
    so the graph stores a real, readable description rather than just a
    category label like 'software_defect'."""
    keywords = ROOT_CAUSE_CATEGORIES.get(category, [])
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        s_lower = sentence.lower()
        if any(kw in s_lower for kw in keywords):
            return sentence.strip()
    return None


_ner_singleton = None


def _get_ner() -> FailureNER:
    global _ner_singleton
    if _ner_singleton is None:
        print("Loading NER model...")
        _ner_singleton = FailureNER()
    return _ner_singleton


def extract_failure_data(text: str, mission: str | None = None, ner: FailureNER | None = None,
                         llm_fn=None) -> dict:
    """
    Per-chunk extraction exactly as build_knowledge_graph() performs it:
    NER gate (domain entity AND root-cause keyword) first, LLM fallback
    otherwise. Exposed so evaluation (run_eval.py / metrics.extraction_metrics)
    scores the same code path that builds the graph.

    `mission`: the graph labels every record with the mission of its source
    document (provenance), so pass the document's mission to reproduce the
    graph's behaviour. If None, the LLM's own mission guess is returned for
    LLM-path records and None for NER-path records.

    Returns {"has_failure_data", "mission", "subsystem", "failure_mode",
             "root_cause", "method"}; method is "ner", "llm" or None.
    Raises whatever the LLM call raises (the build loop counts those as
    llm_failures).
    """
    ner = ner or _get_ner()
    llm_fn = llm_fn or _llm_fallback_extract
    empty = {"has_failure_data": False, "mission": None, "subsystem": None,
             "failure_mode": None, "root_cause": None, "method": None}

    ner_fields = ner.extract_structured_fields(text)
    if ner_fields["has_entities"] and ner_fields["root_cause_category"]:
        category = ner_fields["root_cause_category"]
        return {
            "has_failure_data": True,
            "mission": mission,
            "subsystem": ner_fields["subsystem"] or "Unspecified Subsystem",
            "failure_mode": ner_fields["failure_type"] or f"{category.replace('_', ' ')} related failure",
            "root_cause": _extract_cause_sentence(text, category) or category.replace("_", " "),
            "method": "ner",
        }

    llm_result = llm_fn(text)
    if not llm_result.get("has_failure_data"):
        return {**empty, "method": "llm"}
    return {
        "has_failure_data": True,
        "mission": mission if mission is not None else llm_result.get("mission"),
        "subsystem": llm_result["subsystem"],
        "failure_mode": llm_result["failure_mode"],
        "root_cause": llm_result["root_cause"],
        "method": "llm",
    }


def build_knowledge_graph(doc_ids: list[str] | None = None, records_out: Path | None = None) -> dict:
    """Builds the graph from chunk files. `doc_ids` restricts the build to a
    subset of documents (smoke runs); `records_out` writes one JSON line per
    chunk with the extraction result (run artefact). Returns statistics."""
    chunks_dir = get_settings().chunks_dir

    json_files = sorted(chunks_dir.glob("*_chunks.json"))
    if doc_ids:
        json_files = [p for p in json_files if p.name[: -len("_chunks.json")] in set(doc_ids)]
    if not json_files:
        print(f"No chunk files found in {chunks_dir} (filter: {doc_ids}).")
        return {}

    ner = _get_ner()

    driver = get_driver()
    print(f"Connected to Neo4j. Building FMEA causal graph...\n{'='*60}")

    stats = {"chunks": 0, "ner_hits": 0, "llm_hits": 0, "no_data": 0, "llm_failures": 0}
    records_by_key = {}  # (mission, failure_mode) -> FailureRecord, deduped for pass 2
    similar_pairs = []
    records_fh = open(records_out, "w", encoding="utf-8") if records_out else None

    with driver.session() as session:
        for json_path in json_files:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            document_id = data["document_id"]
            mission = MISSION_NAME_MAP.get(document_id, document_id.replace("_", " ").strip())
            print(f"📄 {json_path.name} -> mission: {mission} ({len(data['chunks'])} chunks)")
            start = time.time()

            for chunk in data["chunks"]:
                text = chunk["text"]
                chunk_id = chunk["chunk_id"]
                stats["chunks"] += 1

                try:
                    record = extract_failure_data(text, mission=mission, ner=ner)
                except Exception as err:
                    print(f"   ⚠️  LLM fallback failed on {chunk_id}: {err}")
                    stats["llm_failures"] += 1
                    if records_fh:
                        records_fh.write(json.dumps({"chunk_id": chunk_id, "error": str(err)}) + "\n")
                    continue

                if records_fh:
                    records_fh.write(json.dumps({"chunk_id": chunk_id, **record}) + "\n")

                if not record["has_failure_data"]:
                    stats["no_data"] += 1
                    continue

                subsystem = record["subsystem"]
                failure_mode = record["failure_mode"]
                root_cause = record["root_cause"]
                method = record["method"]
                stats["ner_hits" if method == "ner" else "llm_hits"] += 1

                session.run("""
                    MATCH (c:Chunk {id: $chunk_id})
                    MERGE (m:Mission {name: $mission})
                    MERGE (s:Subsystem {name: $subsystem})
                    MERGE (fm:FailureMode {name: $failure_mode})
                    MERGE (rc:RootCause {description: $root_cause})

                    MERGE (c)-[:MENTIONS]->(fm)
                    MERGE (m)-[:EXPERIENCED_FAILURE]->(fm)
                    MERGE (fm)-[:OCCURRED_IN_SUBSYSTEM]->(s)
                    MERGE (fm)-[:CAUSED_BY]->(rc)
                    SET fm.extraction_method = $method
                """, {
                    "chunk_id": chunk_id, "mission": mission, "subsystem": subsystem,
                    "failure_mode": failure_mode, "root_cause": root_cause, "method": method,
                })

                key = (mission, failure_mode)
                if key not in records_by_key:
                    records_by_key[key] = FailureRecord(
                        mission=mission, subsystem=subsystem,
                        failure_mode=failure_mode, root_cause=root_cause,
                    )

            print(f"   ✅ Done in {time.time() - start:.1f}s")

        # --- Pass 2: cross-mission similarity edges ---
        print(f"\n{'='*60}\nComparing {len(records_by_key)} unique failure records across missions...")
        similar_pairs = find_cross_mission_similarities(
            list(records_by_key.values()), threshold=DEFAULT_SIMILARITY_THRESHOLD
        )

        for pair in similar_pairs:
            session.run("""
                MATCH (m_a:Mission {name: $mission_a})-[:EXPERIENCED_FAILURE]->(fm_a:FailureMode {name: $failure_mode_a})
                MATCH (m_b:Mission {name: $mission_b})-[:EXPERIENCED_FAILURE]->(fm_b:FailureMode {name: $failure_mode_b})
                MERGE (fm_a)-[r:SIMILAR_ROOT_CAUSE]-(fm_b)
                SET r.similarity = $similarity
            """, pair)

    if records_fh:
        records_fh.close()
    close_driver()
    stats["unique_failure_records"] = len(records_by_key)
    stats["similarity_edges"] = len(similar_pairs)
    print(f"{'='*60}\nKnowledge Graph Built.")
    print(f"  Extraction: {stats['ner_hits']} via NER, {stats['llm_hits']} via LLM fallback, "
          f"{stats['no_data']} chunks with no failure data, {stats['llm_failures']} LLM failures.")
    print(f"  Cross-mission similarity edges created: {len(similar_pairs)}")
    return stats


if __name__ == "__main__":
    build_knowledge_graph()