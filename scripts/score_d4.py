"""
score_d4.py — scores the HUMAN D4 factor review (evalutation/benchmark/D4_factor_review.csv) against the
extractor's accept/reject decisions and the LLM support check (protocol section 10).

    python scripts/score_d4.py --eval-id <id>

Human columns: factor_correct_yes_no (is the claimed causal factor correct for this passage?) and
quote_supports_yes_no (does the quote support it?). Reported:
  precision of ACCEPTED factors        share of accepted items judged correct by the human
  correct-but-rejected share           share of REJECTED items the human judged correct (recall cost of verification)
  LLM support check vs human           agreement and Cohen's kappa on accepted items (quote_supports)
  false accepts / false rejects        counts, with item ids for inspection
Refuses until every row has both human verdicts.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "scripts"))
sys.path.append(str(ROOT / "src"))
from check_annotations import kappa  # noqa: E402
from runlog import new_run_dir, write_json  # noqa: E402

SHEET = ROOT / "evalutation" / "benchmark" / "D4_factor_review.csv"


def yes(v: str) -> bool | None:
    v = v.strip().lower()
    return True if v in ("yes", "y", "1", "true") else False if v in ("no", "n", "0", "false") else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-id", required=True)
    args = ap.parse_args(argv)
    rows = list(csv.DictReader(open(SHEET, encoding="utf-8-sig")))
    todo = [r["item"] for r in rows if yes(r["factor_correct_yes_no"]) is None or yes(r["quote_supports_yes_no"]) is None]
    if todo:
        print(f"REFUSED: {len(todo)} of {len(rows)} items lack a yes/no verdict (e.g. {todo[:5]})")
        return 2
    key = {k["item"]: k for k in json.loads(SHEET.with_suffix(".key.json").read_text(encoding="utf-8"))["items"]}
    support = {}
    sp = ROOT / "data" / "processed" / "factor_support" / "support.jsonl"
    if sp.exists():
        for r in map(json.loads, open(sp, encoding="utf-8")):
            support.setdefault((r["passage_id"], r["code"], r["role"]), r["supported"])
    acc = [r for r in rows if key[r["item"]]["status"] == "accepted"]
    rej = [r for r in rows if key[r["item"]]["status"] == "rejected"]
    res = {
        "n_accepted": len(acc), "n_rejected": len(rej),
        "precision_accepted": round(sum(yes(r["factor_correct_yes_no"]) for r in acc) / len(acc), 4),
        "quote_supports_accepted": round(sum(yes(r["quote_supports_yes_no"]) for r in acc) / len(acc), 4),
        "correct_but_rejected_share": round(sum(yes(r["factor_correct_yes_no"]) for r in rej) / len(rej), 4),
        "false_accepts": [r["item"] for r in acc if not yes(r["factor_correct_yes_no"])],
        "correct_rejects_reasons": {}, "llm_support_vs_human": None,
    }
    for r in rej:
        if yes(r["factor_correct_yes_no"]):
            reason = key[r["item"]].get("reason")
            res["correct_rejects_reasons"][reason] = res["correct_rejects_reasons"].get(reason, 0) + 1
    pairs = [(support.get((key[r["item"]]["passage_id"], r["code"], r["role"])), yes(r["quote_supports_yes_no"])) for r in acc]
    pairs = [(a, b) for a, b in pairs if a is not None]
    if pairs:
        res["llm_support_vs_human"] = {"n": len(pairs), "agreement": round(sum(a == b for a, b in pairs) / len(pairs), 4),
                                       "kappa": kappa([a for a, _ in pairs], [b for _, b in pairs])}
    out = new_run_dir(args.eval_id, prefix="eval_d4")
    write_json(out / "d4_metrics.json", res)
    print(json.dumps({k: v for k, v in res.items() if k != "false_accepts"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
