"""
run_pipeline.py

End-to-end pipeline entry point: PDF -> clean text -> chunks -> Neo4j chunks
+ vector index -> FMEA knowledge graph (NER + LLM fallback + cross-mission
similarity edges).

Each step skips work already done. Every invocation writes its own run
directory runs/<run_id>/ (config, environment, log, timings, statistics,
per-chunk extraction records) and refuses to overwrite an earlier run.

IMPORTANT: point NEO4J_URI at a FRESH database for any run whose outputs will
be reported. Ingestion never updates chunks that already exist, and graph
writes are MERGEs, so an old database keeps stale text and old facts
(see docs/research/05_Stage1_Audit_BasePaper_Plan.md, section 1.4).

Usage:
    python run_pipeline.py                                   # all documents
    python run_pipeline.py --docs Mars_Climate_Orbiter --run-id smoke_mco
    python run_pipeline.py --skip-extract-text --docs A B    # reuse existing text/chunks
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from config import get_settings
from runlog import new_run_dir, write_json, environment_info, tee_output, Timer
from pipeline.pdf_loader import process_all_pdfs
from pipeline.text_chunker import process_and_chunk
from graph.neo4j_connector import verify_connectivity, close_driver
from graph.neo4j_loader import ingest_chunks_to_neo4j
from graph.graph_builder import build_knowledge_graph


def graph_statistics() -> dict:
    from graph.neo4j_connector import get_driver
    with get_driver().session() as s:
        nodes = {r["label"]: r["n"] for r in s.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n")}
        rels = {r["type"]: r["n"] for r in s.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n")}
        methods = {str(r["m"]): r["n"] for r in s.run(
            "MATCH (fm:FailureMode) RETURN fm.extraction_method AS m, count(*) AS n")}
    close_driver()
    return {"nodes": nodes, "relationships": rels, "failure_mode_extraction_method": methods}


def main(argv=None):
    parser = argparse.ArgumentParser(description="MissionMind end-to-end pipeline")
    parser.add_argument("--docs", nargs="*", default=None,
                        help="document ids (PDF stems) to ingest and build; default: all")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--skip-extract-text", action="store_true",
                        help="skip PDF extraction and chunking (use existing files)")
    args = parser.parse_args(argv)

    run_dir = new_run_dir(args.run_id, prefix="pipeline")
    timer = Timer()
    with tee_output(run_dir / "log.txt"):
        if not verify_connectivity():
            sys.exit(1)
        settings = get_settings()
        write_json(run_dir / "config.json", {"settings": settings.public_dict(), "args": vars(args)})
        write_json(run_dir / "env.json", environment_info())
        stats = {}
        try:
            if not args.skip_extract_text:
                with timer.step("pdf_extraction"):
                    process_all_pdfs()
                with timer.step("chunking"):
                    process_and_chunk()
            with timer.step("neo4j_ingestion"):
                stats["ingestion"] = ingest_chunks_to_neo4j(doc_ids=args.docs)
            with timer.step("graph_construction"):
                stats["graph_build"] = build_knowledge_graph(
                    doc_ids=args.docs, records_out=run_dir / "extraction_records.jsonl")
            stats["graph"] = graph_statistics()
        finally:
            write_json(run_dir / "timings.json", timer.timings)
            write_json(run_dir / "stats.json", stats)
            close_driver()
        total = sum(timer.timings.values())
        print(f"\n{'='*60}\n🎉 Pipeline complete in {total / 60:.1f} minutes. Run artefacts: {run_dir}")


if __name__ == "__main__":
    main()
