"""
run_pipeline.py

End-to-end pipeline entry point: PDF -> clean text -> chunks -> Neo4j chunks
+ vector index -> FMEA knowledge graph (NER + LLM fallback + cross-mission
similarity edges).

Run this after adding new PDFs to data/raw/. Each step is idempotent (skips
work already done), so re-running after adding one new PDF only processes
what's new — it won't re-embed or re-extract everything from scratch.

Usage:
    python run_pipeline.py
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from pipeline.pdf_loader import process_all_pdfs
from pipeline.text_chunker import process_and_chunk
from graph.neo4j_loader import ingest_chunks_to_neo4j
from graph.graph_builder import build_knowledge_graph


def run_step(step_name: str, step_fn):
    print(f"\n{'#'*60}\n# {step_name}\n{'#'*60}")
    start = time.time()
    try:
        step_fn()
    except Exception as err:
        print(f"\n❌ Pipeline stopped — '{step_name}' failed: {err}")
        sys.exit(1)
    print(f"⏱  {step_name} completed in {time.time() - start:.1f}s")


def main():
    pipeline_start = time.time()

    run_step("1/4 — PDF extraction (with OCR fallback)", process_all_pdfs)
    run_step("2/4 — Text chunking", process_and_chunk)
    run_step("3/4 — Neo4j ingestion + vector index", ingest_chunks_to_neo4j)
    run_step("4/4 — Knowledge graph construction (NER + LLM fallback + similarity edges)", build_knowledge_graph)

    total = time.time() - pipeline_start
    print(f"\n{'='*60}\n🎉 Pipeline complete in {total / 60:.1f} minutes.")
    print("Next: run evalutation/run_eval.py once evalutation/test_data.json is filled in.")


if __name__ == "__main__":
    main()