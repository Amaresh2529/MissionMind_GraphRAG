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
from models.ner_model import FailureNER, ROOT_CAUSE_CATEGORIES
from models.embeddings import FailureRecord, find_cross_mission_similarities, DEFAULT_SIMILARITY_THRESHOLD
from graph.neo4j_connector import get_driver, close_driver

LLM_FALLBACK_MODEL = "llama3"

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


def _llm_fallback_extract(chunk_text: str, model: str = LLM_FALLBACK_MODEL) -> dict:
    """Only called when NER found nothing — see build_knowledge_graph()."""
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": _LLM_EXTRACTION_PROMPT.format(chunk_text=chunk_text)}],
        format="json",
        options={"temperature": 0}
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


def build_knowledge_graph():
    base_dir = Path(__file__).resolve().parent.parent.parent
    chunks_dir = base_dir / "data" / "processed" / "chunks"

    json_files = list(chunks_dir.glob("*_chunks.json"))
    if not json_files:
        print(f"No chunk files found in {chunks_dir}.")
        return

    print("Loading NER model...")
    ner = FailureNER()

    driver = get_driver()
    print(f"Connected to Neo4j. Building FMEA causal graph...\n{'='*60}")

    stats = {"ner_hits": 0, "llm_hits": 0, "no_data": 0, "llm_failures": 0}
    records_by_key = {}  # (mission, failure_mode) -> FailureRecord, deduped for pass 2
    similar_pairs = []

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

                ner_fields = ner.extract_structured_fields(text)

                if ner_fields["has_entities"] and ner_fields["root_cause_category"]:
                    subsystem = ner_fields["subsystem"] or "Unspecified Subsystem"
                    failure_mode = ner_fields["failure_type"] or f"{ner_fields['root_cause_category'].replace('_', ' ')} related failure"
                    root_cause = (_extract_cause_sentence(text, ner_fields["root_cause_category"])
                                   or ner_fields["root_cause_category"].replace("_", " "))
                    method = "ner"
                    stats["ner_hits"] += 1
                else:
                    try:
                        llm_result = _llm_fallback_extract(text)
                    except Exception as err:
                        print(f"   ⚠️  LLM fallback failed on {chunk_id}: {err}")
                        stats["llm_failures"] += 1
                        continue

                    if not llm_result.get("has_failure_data"):
                        stats["no_data"] += 1
                        continue

                    subsystem = llm_result["subsystem"]
                    failure_mode = llm_result["failure_mode"]
                    root_cause = llm_result["root_cause"]
                    method = "llm"
                    stats["llm_hits"] += 1

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

    close_driver()
    print(f"{'='*60}\nKnowledge Graph Built.")
    print(f"  Extraction: {stats['ner_hits']} via NER, {stats['llm_hits']} via LLM fallback, "
          f"{stats['no_data']} chunks with no failure data, {stats['llm_failures']} LLM failures.")
    print(f"  Cross-mission similarity edges created: {len(similar_pairs)}")


if __name__ == "__main__":
    build_knowledge_graph()