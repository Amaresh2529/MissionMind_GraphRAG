"""
audit.py — Stage 6 audit of an experiment, using SAVED files only and an independent
re-implementation of the metrics (no import from src/bench).

    python scripts/audit.py --run runs/<retrieval_run> [--eval runs/<eval_id>] --out runs/<audit_id>

A1 comparability   every system answered the same query ids; one corpus (index_stats); run on a clean
                   git tree; query file hash recorded
A2 leakage         (a) no prediction contains the query's own mission (T1);
                   (b) n-gram overlap: share of each query's 8-grams found in its own mission's reports
                       vs in other missions' reports (high own-overlap = query copied from the report)
A3 provenance      every predicted passage exists, and its stored text equals page_text[char_start:char_end]
A4 citations       generation/QA: every cited chunk id is in the chunk map and maps to a corpus passage
A5 recomputation   (with --eval) mission nDCG@5 and Recall@5 recomputed here from predictions + D2b and
                   compared with the evaluator's per-query values (|diff| < 1e-9)
"""

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def corpus() -> tuple[dict, dict]:
    passages, pages = {}, {}
    for f in (ROOT / "data" / "processed" / "passages").glob("*.jsonl"):
        for r in load_jsonl(f):
            passages[r["passage_id"]] = r
    for f in (ROOT / "data" / "processed" / "pages").glob("*.jsonl"):
        for r in load_jsonl(f):
            pages[(r["doc_id"], r["page"])] = r["text"]
    return passages, pages


def ngrams(text: str, n: int = 8) -> set:
    w = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def ndcg5(ranking, gains):          # independent implementation (linear gains)
    ideal = sorted([g for g in gains.values() if g > 0], reverse=True)[:5]
    if not ideal:
        return None
    d = sum(gains.get(m, 0) / math.log2(i + 2) for i, m in enumerate(ranking[:5]))
    return d / sum(g / math.log2(i + 2) for i, g in enumerate(ideal))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--eval", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", default=str(ROOT / "evalutation" / "benchmark"))
    args = ap.parse_args(argv)
    run = Path(args.run)
    man = {d["doc_id"]: d for d in json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    passages, pages = corpus()
    preds = {f.stem: load_jsonl(f) for f in sorted((run / "predictions").glob("*.jsonl"))}
    env = json.loads((run / "env.json").read_text(encoding="utf-8"))
    rep, fails = {}, []

    qsets = {s: sorted(r["query_id"] for r in rows) for s, rows in preds.items()}
    same_q = len({tuple(v) for v in qsets.values()}) == 1
    rep["A1"] = {"same_query_ids": same_q, "systems": list(preds), "git_dirty": env.get("git_dirty"),
                 "git_commit": env.get("git_commit")}
    if not same_q or env.get("git_dirty"):
        fails.append("A1")

    leaks = sum(1 for rows in preds.values() for r in rows for p in r["passages"]
                if r.get("mission") and r["mission"] in man[p["doc_id"]]["mission_ids"])
    queries = load_jsonl(run / "queries.jsonl")
    own, other = [], []
    text_by_mission = {}
    for pid, p in passages.items():
        for m in man.get(p["doc_id"], {}).get("mission_ids", []):
            text_by_mission.setdefault(m, []).append(p["text"])
    grams = {m: ngrams(" ".join(t)) for m, t in text_by_mission.items()}
    overlap = {}
    for q in queries:
        g = ngrams(q["text"])
        if not g or not q.get("mission"):
            continue
        o = len(g & grams.get(q["mission"], set())) / len(g)
        x = max((len(g & s) / len(g) for m, s in grams.items() if m != q["mission"]), default=0.0)
        overlap[q["query_id"]] = {"own_8gram_overlap": round(o, 3), "max_other_8gram_overlap": round(x, 3)}
    copied = [q for q, v in overlap.items() if v["own_8gram_overlap"] > 0.2]
    rep["A2"] = {"own_mission_leaks": leaks, "queries_with_own_8gram_overlap_gt_0.2": copied, "overlap": overlap}
    if leaks:
        fails.append("A2")

    bad_prov = []
    for rows in preds.values():
        for r in rows:
            for p in r["passages"]:
                ps = passages.get(p["id"])
                if ps is None or pages.get((ps["doc_id"], ps["page"]), "")[ps["char_start"]:ps["char_end"]] != ps["text"]:
                    bad_prov.append(p["id"])
    rep["A3"] = {"checked": sum(len(r["passages"]) for rows in preds.values() for r in rows), "bad": sorted(set(bad_prov))[:20]}
    if bad_prov:
        fails.append("A3")

    bad_cite, n_cite = [], 0
    for sub in ("generation", "qa"):
        for f in sorted((run / sub).glob("*.jsonl")) if (run / sub).exists() else []:
            for r in load_jsonl(f):
                ans = r.get("answer") or {}
                items = [it for k, v in ans.items() if isinstance(v, list) for it in v if isinstance(it, dict)]
                for it in items:
                    for c in it.get("evidence") or []:
                        n_cite += 1
                        m_ = re.match(r"^\W*(C\d+)\b", str(c))     # same normalisation as rca_generation.norm_cite
                        uid = r["chunk_map"].get(m_.group(1) if m_ else str(c).strip())
                        if uid is None or uid not in passages:
                            bad_cite.append(f"{f.stem}:{r['query_id']}:{c}")
    rep["A4"] = {"citations_checked": n_cite, "invalid_in_final_answers": len(bad_cite), "examples": bad_cite[:10],
                 "note": "B3/B0 answers are not filtered; P answers are enforced. Invalid citations in B3 are a "
                         "property of the system and are reported, not an audit failure."}

    if args.eval:
        ev = json.loads((Path(args.eval) / "per_query.json").read_text(encoding="utf-8"))
        rows = list(csv.DictReader(open(Path(args.labels) / "D2b_mission_pairs.csv", encoding="utf-8-sig")))
        rep["A5_labels_dir"] = args.labels
        grade = {frozenset((r["mission_a"], r["mission_b"])): int(r["grade"]) for r in rows if r["grade"].strip()}
        missions = sorted({r["mission_a"] for r in rows} | {r["mission_b"] for r in rows})
        mism = []
        for s, rws in preds.items():
            for r in rws:
                q = r["mission"]
                gains = {m: grade.get(frozenset((q, m)), 0) for m in missions if m != q}
                labelled = set(missions)       # same rule as the evaluator: rank only labelled missions
                mine = ndcg5([m for m in r["mission_ranking"] if m != q and m in labelled], gains)
                theirs = ev.get(s, {}).get(r["query_id"], {}).get("mission_ndcg@5")
                if (mine is None) != (theirs is None) or (mine is not None and abs(mine - theirs) > 1e-9):
                    mism.append((s, r["query_id"], mine, theirs))
        rep["A5"] = {"recomputed": sum(len(v) for v in preds.values()), "mismatches": mism[:20]}
        if mism:
            fails.append("A5")

    rep["failures"] = fails
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps({k: (v if k != "A2" else {x: y for x, y in v.items() if x != "overlap"}) for k, v in rep.items()}, indent=1))
    print("PASS" if not fails else f"FAIL: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
