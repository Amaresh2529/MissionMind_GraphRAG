"""
sample_for_labeling.py

Pulls a spread of real chunks from data/processed/chunks/*.json and writes
evalutation/test_data_draft.json with the correct structure already filled
in for chunk_id and text -- you only need to fill in has_failure_data,
mission, subsystem, failure_mode, and root_cause for each one (or null
them out for chunks that describe no failure, e.g. from Annual_Report_*).

Doesn't touch Neo4j or run any model -- just samples from the chunk files
already on disk.
"""

import json
from pathlib import Path

SAMPLES_PER_DOCUMENT = 5

def main():
    base_dir = Path(__file__).resolve().parent.parent
    chunks_dir = base_dir / "data" / "processed" / "chunks"
    out_path = Path(__file__).resolve().parent / "test_data_draft.json"

    labeled_chunks = []
    for json_path in sorted(chunks_dir.glob("*_chunks.json")):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        chunks = data["chunks"]
        if not chunks:
            continue
        # Evenly spaced indices across the document, not just the first N
        step = max(1, len(chunks) // SAMPLES_PER_DOCUMENT)
        picked = chunks[::step][:SAMPLES_PER_DOCUMENT]
        for c in picked:
            labeled_chunks.append({
                "chunk_id": c["chunk_id"],
                "text": c["text"],
                "has_failure_data": None,   # fill: true / false
                "mission": None,             # fill if true, else leave null
                "subsystem": None,
                "failure_mode": None,
                "root_cause": None,
            })

    draft = {
        "labeled_chunks": labeled_chunks,
        "test_queries": [
            {"question": "REPLACE ME", "relevant_chunk_ids": ["REPLACE_WITH_REAL_CHUNK_ID"]}
        ],
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, indent=2)

    print(f"Wrote {len(labeled_chunks)} candidate chunks to {out_path}")
    print("Fill in has_failure_data / mission / subsystem / failure_mode / root_cause for each,")
    print("delete any you don't want to keep, then rename to test_data.json.")

if __name__ == "__main__":
    main()