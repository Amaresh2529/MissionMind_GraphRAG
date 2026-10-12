"""
run_retrieval.py — Stage 3 runner for the base-paper retrieval configurations
(B1, B2, H-whole, single-field SF-*, B3) and the generation step (B3 grounded / B0 LLM-only).

    python scripts/run_retrieval.py --run-id stage3_dev_bm25 --systems B1 SF-summary-bm25 SF-causes-bm25 --embedder none
    python scripts/run_retrieval.py --run-id stage3_dev_all --generate B3 B0

Writes runs/<run_id>/: config.json, env.json, index_stats.json, queries.jsonl,
predictions/<system>.jsonl (top-100 passages with per-list ranks + mission ranking),
generation/<B3|B0>.jsonl, timings.json, log.txt.
Field maps must be "reviewed" unless --allow-draft-fields is given; runs on
draft maps are DEV runs and are marked so in config.json.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from runlog import Timer, environment_info, new_run_dir, tee_output, write_json  # noqa: E402
from retrieval import bm25, dense, fusion, rca_generation, systems  # noqa: E402
from retrieval.corpus import FIELDS, load_units, missions  # noqa: E402
from retrieval.queries import QUERY_WORDS, dev_queries, load_queries  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--systems", nargs="*", default=list(systems.SYSTEMS))
    ap.add_argument("--queries", default=None, help="jsonl with query_id, mission, text; default: automatic dev queries")
    ap.add_argument("--embedder", default=dense.DEFAULT_MODEL, help="model name, or 'none' for BM25-only runs")
    ap.add_argument("--generate", nargs="*", default=[], choices=["B3", "B0"])
    ap.add_argument("--allow-draft-fields", action="store_true")
    args = ap.parse_args(argv)

    run = new_run_dir(args.run_id, prefix="retrieval")
    timer = Timer()
    with tee_output(run / "log.txt"):
        write_json(run / "env.json", environment_info(include_services=bool(args.generate)))
        with timer.step("load_units"):
            units = load_units(None if args.allow_draft_fields else "reviewed")
        queries = load_queries(args.queries) if args.queries else dev_queries(units)
        qtext = "".join(json.dumps(q, sort_keys=True) for q in queries)
        embedder = None
        if args.embedder != "none":
            with timer.step("load_embedder"):
                embedder = dense.Embedder(args.embedder, dense.DEFAULT_REVISION if args.embedder == dense.DEFAULT_MODEL else None)
        with timer.step("build_indexes"):
            retriever = systems.Retriever(units, embedder)
        cfgs = [systems.SYSTEMS[s] for s in args.systems]
        skipped = [c.id for c in cfgs if "dense" in c.methods and embedder is None]
        cfgs = [c for c in cfgs if c.id not in skipped]
        write_json(run / "config.json", {
            "args": vars(args), "dev_run": args.allow_draft_fields or not args.queries,
            "systems": {c.id: {"fields": c.fields, "methods": c.methods} for c in cfgs}, "skipped_no_embedder": skipped,
            "bm25": {"k1": bm25.K1, "b": bm25.B, "tokenizer": "lowercase [a-z0-9]+, no stemming/stopwords"},
            "rrf_k": fusion.K_RRF, "list_depth": systems.LIST_DEPTH, "top_k": systems.TOP_K,
            "dense": None if embedder is None else {"model": embedder.name, "revision": embedder.revision,
                                                     "max_seq_length": embedder.max_seq_length, "normalized": True,
                                                     "cache": str(retriever.dense.cache_path.relative_to(ROOT)),
                                                     "cache_hit": retriever.dense.cache_hit},
            "generation": {"top_k_gen": rca_generation.TOP_K_GEN, "context_word_budget": rca_generation.CONTEXT_WORD_BUDGET,
                           "num_ctx": rca_generation.NUM_CTX},
            "queries": {"source": args.queries or f"automatic dev queries ({QUERY_WORDS} words)", "n": len(queries),
                        "sha256": hashlib.sha256(qtext.encode("utf-8")).hexdigest()},
        })
        write_json(run / "index_stats.json", {
            "units": len(units), "per_field": {f: len(retriever.field_members[f]) for f in FIELDS},
            "missions": missions(units), "n_missions": len(missions(units)),
            "documents": sorted({u.doc_id for u in units})})
        with open(run / "queries.jsonl", "w", encoding="utf-8") as f:
            for q in queries:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        (run / "predictions").mkdir()
        results = {}
        for cfg in cfgs:
            with timer.step(f"search_{cfg.id}"):
                rows = []
                for q in queries:
                    r = retriever.search(cfg, q["text"], exclude_missions={q["mission"]})
                    rows.append({"query_id": q["query_id"], "mission": q["mission"], **r})
            results[cfg.id] = rows
            with open(run / "predictions" / f"{cfg.id}.jsonl", "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            print(f"{cfg.id:18s} {len(rows)} queries, lists={rows[0]['lists'] if rows else []}")
        if args.generate:
            if embedder is not None:          # free GPU memory for the local LLM (8 GB card)
                import torch
                del embedder.model
                torch.cuda.empty_cache()
            (run / "generation").mkdir()
            units_by_id = {u.id: u for u in units}
            for g in args.generate:
                if g == "B3" and "B3" not in results:
                    print("B3 generation needs B3 retrieval in this run; skipped")
                    continue
                with timer.step(f"generate_{g}"):
                    rows = []
                    for qi, q in enumerate(queries):
                        passages = results["B3"][qi]["passages"] if g == "B3" else None
                        out = rca_generation.draft_rca(q["text"], passages, units_by_id)
                        rows.append({"query_id": q["query_id"], "mission": q["mission"], "system": g, **out})
                        print(f"  {g} {q['query_id']}: chunks={out['chunks_used']} schema_ok={out['checks']['schema_ok']} "
                              f"invalid_cites={out['checks']['invalid_citations']} cached={out['cached']}")
                with open(run / "generation" / f"{g}.jsonl", "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        write_json(run / "timings.json", timer.timings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
