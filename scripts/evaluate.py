"""
evaluate.py — Stage 5 retrieval evaluation against the HUMAN benchmark labels.

    python scripts/evaluate.py --run runs/<retrieval_run> --eval-id <id> [--dev]

Mission level (T1, D2b grades): nDCG@5 (PRIMARY), nDCG@10, Recall@5 (grade >= 2), MRR.
Passage level (paper metrics): NormRecall@100 and nDCG@100; a passage is relevant when it lies on a
D2a evidence page of an analogous mission for one of the codes the pair shares (gain = pair grade).

Guards (refuse unless --dev, which marks every output DEV / not reportable):
  - labels complete (D2b graded, D2a present)                         -> labels.IncompleteLabels
  - the run's queries are exactly the human D2q queries (text hash)    -> invalid comparison otherwise
  - the run used reviewed field maps (config dev_run == False)
Comparisons: P vs B3 on nDCG@5 (primary, paired permutation + bootstrap CI); every other system and
ablation vs B3 and vs P (secondary, Holm-adjusted).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from bench import metrics as M, stats as S  # noqa: E402
from bench.labels import Labels  # noqa: E402
from runlog import new_run_dir, write_json  # noqa: E402

PRIMARY = ("P", "B3", "mission_ndcg@5")


def evaluate_run(run: Path, labels: Labels, units_by_page: dict, missions_of: dict | None = None) -> tuple[dict, dict]:
    """Rankings are restricted to the LABELLED missions (all 22 in the full benchmark; 10 in the pilot), so
    unlabelled missions never count as non-relevant. missions_of: passage id -> mission ids."""
    per_query, summary = {}, {}
    labelled = set(labels.missions)
    for f in sorted((run / "predictions").glob("*.jsonl")):
        system = f.stem
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        pq = {}
        for r in rows:
            q = r["mission"]
            gains = {m: labels.grade(q, m) or 0 for m in labels.missions if m != q}
            rel = {m for m, g in gains.items() if g >= 2}
            ranking = [m for m in r["mission_ranking"] if m != q and m in labelled]
            page_gain = {}
            for m, g in gains.items():
                if g >= 1:
                    for page in labels.factor_pages(m, labels.shared(q, m)):
                        page_gain[page] = max(page_gain.get(page, 0), g)
            p_gain = {pid: page_gain[key] for key, pids in units_by_page.items() if key in page_gain for pid in pids}
            gold = {pid for pid, g in p_gain.items() if g >= 2}
            pids = [p["id"] for p in r["passages"]
                    if missions_of is None or labelled & set(missions_of.get(p["id"], ()))]
            pq[r["query_id"]] = {
                "mission_ndcg@5": M.ndcg_at_k(ranking, gains, 5), "mission_ndcg@10": M.ndcg_at_k(ranking, gains, 10),
                "mission_recall@5": M.recall_at_k(ranking, rel, 5), "mission_mrr": M.mrr(ranking, rel),
                "passage_normrecall@100": M.norm_recall_at_k(pids, gold, 100),
                "passage_ndcg@100": M.ndcg_at_k(pids, p_gain, 100),
                "n_relevant_missions": len(rel), "n_gold_passages": len(gold)}
        per_query[system] = pq
        keys = [k for k in next(iter(pq.values())) if not k.startswith("n_")] if pq else []
        summary[system] = {k: M.mean([v[k] for v in pq.values()]) for k in keys} | {
            "queries": len(pq), "queries_defined_ndcg@5": sum(v["mission_ndcg@5"] is not None for v in pq.values())}
    return per_query, summary


def compare(per_query: dict) -> dict:
    out, sec = {}, {}
    qids = sorted(next(iter(per_query.values())))
    def vec(s, metric): return [per_query[s][q][metric] for q in qids]
    a, b, metric = PRIMARY
    if a in per_query and b in per_query:
        out["primary"] = {"comparison": f"{a} vs {b}", "metric": metric,
                          "permutation": S.paired_permutation(vec(a, metric), vec(b, metric)),
                          "bootstrap95": S.bootstrap_ci(vec(a, metric), vec(b, metric))}
    for ref in ("B3", "P"):
        if ref not in per_query:
            continue
        for s in per_query:
            if s in (ref, "P" if ref == "B3" else None):
                continue
            for metric in ("mission_ndcg@5", "passage_normrecall@100"):
                key = f"{ref} vs {s} [{metric}]"
                sec[key] = {"permutation": S.paired_permutation(vec(ref, metric), vec(s, metric)),
                            "bootstrap95": S.bootstrap_ci(vec(ref, metric), vec(s, metric))}
    adj = S.holm({k: v["permutation"]["p"] for k, v in sec.items()})
    for k in sec:
        sec[k]["p_holm"] = adj.get(k)
    out["secondary"] = sec
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--eval-id", required=True)
    ap.add_argument("--labels", default=None)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--pilot", action="store_true",
                    help="human pilot labels: draft field maps are accepted and recorded as a limitation")
    args = ap.parse_args(argv)
    run = Path(args.run)
    from bench.labels import IncompleteLabels
    try:
        labels = Labels(Path(args.labels)) if args.labels else Labels()
    except IncompleteLabels as err:
        print("REFUSED: human labels incomplete:", err)
        return 2
    cfg = json.loads((run / "config.json").read_text(encoding="utf-8"))
    problems, limitations = [], []
    pilot = (labels.base / "PILOT.json").exists()
    if pilot and not args.pilot:
        problems.append("pilot labels: run with --pilot")
    if labels.synthetic:
        problems.append("SYNTHETIC pseudo-labels (evalutation/benchmark/synthetic): proof of concept only")
    if cfg.get("dev_run"):
        if args.pilot and pilot and cfg["args"].get("queries"):
            limitations.append("field maps are drafts (not yet human-reviewed)")
        else:
            problems.append("retrieval run is a DEV run (draft field maps or automatic queries)")
    try:
        t1 = labels.queries_t1()
        run_q = [json.loads(l) for l in open(run / "queries.jsonl", encoding="utf-8")]
        if {q["query_id"]: q["text"] for q in t1} != {q["query_id"]: q["text"] for q in run_q}:
            problems.append("run queries differ from the human D2q queries")
    except Exception as err:                       # noqa: BLE001
        problems.append(str(err))
    if problems and not args.dev:
        print("REFUSED:", problems)
        return 2
    sys.path.append(str(ROOT / "src"))
    from retrieval.corpus import load_units
    units_by_page, missions_of = {}, {}
    for u in load_units(None):
        units_by_page.setdefault((u.doc_id, u.page), []).append(u.id)
        missions_of[u.id] = u.missions
    per_query, summary = evaluate_run(run, labels, units_by_page, missions_of)
    out = new_run_dir(args.eval_id, prefix="eval")
    write_json(out / "metrics.json", {"DEV_NOT_REPORTABLE": bool(problems), "SYNTHETIC_LABELS_NOT_REPORTABLE": labels.synthetic,
                                      "PILOT_HUMAN_LABELS": pilot, "labelled_missions": labels.missions,
                                      "limitations": limitations,
                                      "labels_dir": str(labels.base), "problems": problems, "run": str(run),
                                      "labels_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                        for p in sorted(labels.base.glob("*.csv"))},
                                      "summary": summary})
    write_json(out / "per_query.json", per_query)
    write_json(out / "comparisons.json", compare(per_query))
    for s, v in summary.items():
        print(f"{s:14s} " + " ".join(f"{k}={v[k]:.3f}" for k in v if isinstance(v[k], float)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
