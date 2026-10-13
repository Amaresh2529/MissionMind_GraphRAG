"""
evaluate_answers.py — D3 answer quality for B0 / B3 / P (QA runs from run_retrieval.py --qa).

    python scripts/d3_queries.py                      # D3 sheet -> evalutation/benchmark/d3_queries.jsonl
    python scripts/run_retrieval.py --run-id <run> --queries evalutation/benchmark/d3_queries.jsonl \
           --systems B3 --proposed P --qa B0 B3 P
    python scripts/evaluate_answers.py --run runs/<run> --eval-id <id>

Metrics per system (answerable questions unless stated):
  key_point_recall     share of gold key points judged covered by the answer (LLM judge, yes/no per point;
                       judge = local model, recorded; validated on a human-rated sample, RQ5)
  citation_page_prec   share of cited chunks lying on a gold evidence page (doc_id, page)
  abstain_correct      unanswerable questions: share abstained; answerable: share NOT abstained
Also exports human_rating_sheet.csv (random 40 questions x systems, blind, shuffled) for RQ5.
"""

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from bench import metrics as M, stats as S  # noqa: E402
from bench.labels import Labels  # noqa: E402
from runlog import new_run_dir, write_json  # noqa: E402
from retrieval import rca_generation as rg  # noqa: E402

JUDGE_SYSTEM = 'You check whether an answer states a given fact. Respond with ONLY {"covered": true} or {"covered": false}.'
JUDGE = 'FACT: {point}\n\nANSWER: """{answer}"""\n\nDoes the answer state this fact (same meaning, any wording)?'


def judge(point: str, answer_text: str) -> bool:
    from config import get_settings
    r = rg._chat(JUDGE.format(point=point, answer=answer_text), get_settings().llm_model, JUDGE_SYSTEM)
    try:
        return bool(json.loads(r["raw"]).get("covered"))
    except (json.JSONDecodeError, AttributeError):
        return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--eval-id", required=True)
    args = ap.parse_args(argv)
    run = Path(args.run)
    labels = Labels(require_complete=False)
    qs = {r["qid"]: r for r in labels.questions_d3()}
    if not qs:
        print("REFUSED: D3 questions not written")
        return 2
    from retrieval.corpus import load_units
    page_of = {u.id: (u.doc_id, u.page) for u in load_units(None)}
    results, per_q = {}, {}
    for f in sorted((run / "qa").glob("*.jsonl")):
        s = f.stem
        rows = {r["query_id"]: r for r in map(json.loads, open(f, encoding="utf-8"))}
        kp, cp, ab = [], [], []
        per_q[s] = {}
        for qid, q in qs.items():
            r = rows.get(qid)
            if r is None:
                continue
            ans = r["answer"] or {}
            abstained = bool(ans.get("abstain")) or not ans
            answerable = q["answerable"] == "yes"
            ab.append(abstained != answerable)
            rec = {"abstained": abstained, "abstain_correct": abstained != answerable}
            if answerable:
                text = ans.get("answer", "") + " " + " ".join(k.get("point", "") for k in ans.get("key_points", []) if isinstance(k, dict))
                points = [p.strip() for p in q["key_points"].split(";") if p.strip()]
                cov = [judge(p, text) for p in points] if text.strip() else [False] * len(points)
                rec["key_point_recall"] = sum(cov) / len(points) if points else None
                kp.append(rec["key_point_recall"])
                gold_pages = {(e.rpartition(":")[0], int(e.rpartition(":")[2])) for e in q["evidence"].split(";") if e.strip()}
                cited = [r["chunk_map"].get(rg.norm_cite(c)) for k in ans.get("key_points", []) if isinstance(k, dict)
                         for c in (k.get("evidence") or []) if rg.norm_cite(c) in r["chunk_map"]]
                if cited:
                    rec["citation_page_prec"] = sum(page_of.get(c) in gold_pages for c in cited) / len(cited)
                    cp.append(rec["citation_page_prec"])
            per_q[s][qid] = rec
        results[s] = {"key_point_recall": M.mean(kp), "citation_page_prec": M.mean(cp),
                      "abstain_correct": M.mean(ab), "questions": len(per_q[s])}
    comps = {}
    qids = sorted(qs)
    for a, b in (("P", "B3"), ("P", "B0"), ("B3", "B0")):
        if a in per_q and b in per_q:
            va = [per_q[a].get(q, {}).get("key_point_recall") for q in qids]
            vb = [per_q[b].get(q, {}).get("key_point_recall") for q in qids]
            comps[f"{a} vs {b} [key_point_recall]"] = {"permutation": S.paired_permutation(va, vb),
                                                       "bootstrap95": S.bootstrap_ci(va, vb)}
    out = new_run_dir(args.eval_id, prefix="eval_answers")
    write_json(out / "answer_metrics.json", {"run": str(run), "judge": "local LLM (see env), yes/no per key point",
                                             "d3_sha256": hashlib.sha256((labels.base / "D3_questions.csv").read_bytes()).hexdigest(),
                                             "results": results, "comparisons": comps})
    write_json(out / "per_question.json", per_q)
    # blind human-rating sample (RQ5)
    rng = random.Random(20261013)
    sample = rng.sample(qids, min(40, len(qids)))
    items = []
    for qid in sample:
        for s in per_q:
            r = {x["query_id"]: x for x in map(json.loads, open(run / "qa" / f"{s}.jsonl", encoding="utf-8"))}.get(qid)
            if r:
                items.append((qid, s, (r["answer"] or {}).get("answer", "") or "[abstained]"))
    rng.shuffle(items)
    with open(out / "human_rating_sheet.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "qid", "question", "answer", "correctness_1to5", "groundedness_1to5", "note"])
        key = []
        for i, (qid, s, text) in enumerate(items, 1):
            w.writerow([f"R{i:03d}", qid, qs[qid]["question"], text, "", "", ""])
            key.append({"item": f"R{i:03d}", "system": s})
    write_json(out / "human_rating_key.json", key)
    print(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
