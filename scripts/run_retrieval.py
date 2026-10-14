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


def _exclusions(q: dict) -> set[str]:
    """T1 queries exclude their own mission (leave-one-mission-out); D3 questions set
    "exclude_missions": [] because they may ask about any mission."""
    if "exclude_missions" in q:
        return set(q["exclude_missions"])
    return {q["mission"]} if q.get("mission") else set()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--systems", nargs="*", default=list(systems.SYSTEMS))
    ap.add_argument("--queries", default=None, help="jsonl with query_id, mission, text; default: automatic dev queries")
    ap.add_argument("--embedder", default=dense.DEFAULT_MODEL, help="model name, or 'none' for BM25-only runs")
    ap.add_argument("--generate", nargs="*", default=[], choices=["B3", "B0", "P", "P2", "P2-2step"])
    ap.add_argument("--proposed", nargs="*", default=[],
                    choices=["P", "P-noverif", "P-nofields", "P-graphonly", "P-noidf", "P-noprf", "P2", "P2-nofilter"],
                    help="Stage 4 method and ablations (need data/processed/factors from extract_factors.py)")
    ap.add_argument("--qa", nargs="*", default=[], choices=["B0", "B3", "P", "P2", "P2-2step"],
                    help="answer the queries as D3 questions (QA schema) with these systems")
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
        results, prop, qfs = {}, None, {}
        if args.proposed:
            from extension import factor_extractor as fx, factor_graph as fg
            from extension.proposed import ProposedRetriever, query_factors
            valid = set(fx.codes())
            prop = ProposedRetriever(retriever, fg.load_mentions(),
                                     fg.load_mentions(include_rejected=True, valid_codes=valid))
            with timer.step("query_factors"):
                for q in queries:
                    qfs[q["query_id"]] = query_factors(q["text"], fx.extract)
            with open(run / "query_factors.jsonl", "w", encoding="utf-8") as f:
                for qid, qf in qfs.items():
                    f.write(json.dumps({"query_id": qid, "codes": sorted(qf.codes), "accepted": qf.accepted,
                                        "rejected": qf.rejected}, ensure_ascii=False) + "\n")
            write_json(run / "factor_graph_stats.json", {
                v: {"missions": len(d["profiles"]), "mentions": sum(len(e["evidence"]) for p_ in d["profiles"].values() for e in p_.values()),
                    "codes_per_mission": {m: sorted(p_) for m, p_ in d["profiles"].items()},
                    "idf": {c: round(x, 4) for c, x in sorted(d["idf"].items())}}
                for v, d in prop.variants.items()})
        for cfg in cfgs:
            with timer.step(f"search_{cfg.id}"):
                rows = []
                for q in queries:
                    r = retriever.search(cfg, q["text"], exclude_missions=_exclusions(q))
                    rows.append({"query_id": q["query_id"], "mission": q["mission"], **r})
            results[cfg.id] = rows
            with open(run / "predictions" / f"{cfg.id}.jsonl", "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            print(f"{cfg.id:18s} {len(rows)} queries, lists={rows[0]['lists'] if rows else []}")
        for sid in args.proposed:
            with timer.step(f"search_{sid}"):
                rows = [{"query_id": q["query_id"], "mission": q["mission"],
                         **prop.search(sid, q["text"], qfs[q["query_id"]], exclude_missions=_exclusions(q))}
                        for q in queries]
            results[sid] = rows
            with open(run / "predictions" / f"{sid}.jsonl", "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
            print(f"{sid:18s} {len(rows)} queries, fallback_to_B3={sum(r['graph']['fallback_to_base'] for r in rows)}")
        if args.generate:
            if embedder is not None:          # free GPU memory for the local LLM (8 GB card)
                import torch
                del embedder.model
                torch.cuda.empty_cache()
            (run / "generation").mkdir()
            units_by_id = {u.id: u for u in units}
            for g in args.generate:
                src = "P2" if g == "P2-2step" else g
                if src in ("B3", "P", "P2") and src not in results:
                    print(f"{g} generation needs {g} retrieval in this run; skipped")
                    continue
                with timer.step(f"generate_{g}"):
                    rows = []
                    for qi, q in enumerate(queries):
                        if g in ("P", "P2", "P2-2step"):
                            from extension.grounded_generation import draft_rca_p
                            pr = results[src][qi]
                            prof = prop.variants["verified"]["profiles"]
                            qc = set(pr["graph"]["query_codes"])
                            mev = {m: {c: [e["passage_id"] for e in prof[m][c]["evidence"]] for c in qc & set(prof[m])}
                                   for m in pr["graph"]["mission_analogy"]}
                            names = {c: v["name"] for c, v in fx.codes().items()}
                            out = draft_rca_p(q["text"], pr["passages"], units_by_id, pr["graph"], names, mev,
                                              specific=(g in ("P2", "P2-2step")), two_step=(g == "P2-2step"))
                        else:
                            passages = results["B3"][qi]["passages"] if g == "B3" else None
                            out = rca_generation.draft_rca(q["text"], passages, units_by_id)
                        rows.append({"query_id": q["query_id"], "mission": q["mission"], "system": g, **out})
                        print(f"  {g} {q['query_id']}: chunks={out['chunks_used']} schema_ok={out['checks']['schema_ok']} "
                              f"invalid_cites={out['checks']['invalid_citations']} cached={out['cached']}")
                with open(run / "generation" / f"{g}.jsonl", "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if args.qa:
            from extension import qa
            if embedder is not None and hasattr(embedder, "model"):
                import torch
                del embedder.model
                torch.cuda.empty_cache()
            (run / "qa").mkdir(exist_ok=True)
            units_by_id = {u.id: u for u in units}
            for s_ in args.qa:
                src_qa = "P2" if s_ == "P2-2step" else s_
                if s_ != "B0" and src_qa not in results:
                    print(f"QA with {s_} needs {s_} retrieval in this run; skipped")
                    continue
                with timer.step(f"qa_{s_}"):
                    rows = []
                    for qi, q in enumerate(queries):
                        kw = {}
                        if s_ in ("B3", "P", "P2", "P2-2step"):
                            kw = {"passages": results[src_qa][qi]["passages"], "units_by_id": units_by_id}
                        if s_ in ("P", "P2", "P2-2step"):
                            pr = results[src_qa][qi]
                            prof = prop.variants["verified"]["profiles"]
                            qc = set(pr["graph"]["query_codes"])
                            kw |= {"graph": pr["graph"], "code_names": {c: v["name"] for c, v in fx.codes().items()},
                                   "mission_evidence": {m: {c: [e["passage_id"] for e in prof[m][c]["evidence"]]
                                                            for c in qc & set(prof[m])} for m in pr["graph"]["mission_analogy"]}}
                        rows.append({"query_id": q["query_id"], **qa.answer(s_, q["text"], **kw)})
                with open(run / "qa" / f"{s_}.jsonl", "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(r, ensure_ascii=False) + chr(10))
                print(f"QA {s_}: {len(rows)} answers, abstained={sum(bool((r['answer'] or {}).get('abstain')) for r in rows)}")
        write_json(run / "timings.json", timer.timings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
