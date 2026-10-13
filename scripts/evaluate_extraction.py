"""
evaluate_extraction.py — RQ1: reliability of evidence-anchored extraction vs its recall cost,
against the HUMAN D1 labels.

    python scripts/evaluate_extraction.py --eval-id <id> [--dev]

Variants (from data/processed/factors, produced by scripts/extract_factors.py):
  verified    accepted factors (deterministic quote/code/role verification)
  noverif     accepted + rejected proposals with a valid code ("-verification" ablation)
Metrics on the D1 passages: micro precision/recall/F1 over (passage, code) pairs, the same with
roles, and accuracy of "passage states a factor". Bootstrap 95% CIs over passages.
Refuses unless D1 is completely labelled (or --dev, which marks output DEV).
"""

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from bench import metrics as M  # noqa: E402
from bench.labels import IncompleteLabels, Labels  # noqa: E402
from config import get_settings  # noqa: E402
from extension.factor_extractor import codes  # noqa: E402
from runlog import new_run_dir, write_json  # noqa: E402


def predictions() -> dict:
    valid, out = set(codes()), {"verified": {}, "noverif": {}}
    for f in (get_settings().processed_dir / "factors").glob("*.jsonl"):
        for r in map(json.loads, open(f, encoding="utf-8")):
            acc = {(x["code"], x["role"]) for x in r["accepted"]}
            rej = {(x["code"], x["role"]) for x in r["rejected"] if x.get("code") in valid}
            out["verified"][r["passage_id"]] = acc
            out["noverif"][r["passage_id"]] = acc | rej
    return out


def score(gold: dict, pred: dict, with_role: bool) -> dict:
    g = {(p, c if not with_role else (c, r)) for p, s in gold.items() for c, r in s}
    q = {(p, c if not with_role else (c, r)) for p, s in pred.items() if p in gold for c, r in s}
    return M.prf(q, g)


def bootstrap_f1(gold: dict, pred: dict, n: int = 2000, seed: int = 20261013) -> list[float]:
    ids, rng, f1s = sorted(gold), random.Random(seed), []
    for _ in range(n):
        sample = [rng.choice(ids) for _ in ids]
        gg = {}
        pp = {}
        for k, pid in enumerate(sample):           # resampled passages keep duplicates distinct
            gg[(pid, k)] = gold[pid]
            pp[(pid, k)] = pred.get(pid, set())
        f1s.append(score(gg, pp, False)["f1"])
    f1s.sort()
    return [f1s[int(0.025 * n)], f1s[int(0.975 * n) - 1]]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-id", required=True)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--labels", default=None)
    args = ap.parse_args(argv)
    try:
        lab = Labels(Path(args.labels), require_complete=False) if args.labels else Labels(require_complete=False)
        gold, none = lab.d1()
    except IncompleteLabels as err:
        print("REFUSED: human labels incomplete:", err)
        return 2
    preds, res = predictions(), {}
    missing = [p for p in gold if p not in preds["verified"]]
    for v, pred in preds.items():
        res[v] = {"code": score(gold, pred, False), "code+role": score(gold, pred, True),
                  "has_factor_accuracy": sum(bool(pred.get(p)) == bool(gold[p]) for p in gold) / len(gold),
                  "f1_bootstrap95": bootstrap_f1(gold, pred)}
    if lab.synthetic and not args.dev:
        print("REFUSED: synthetic labels need --dev")
        return 2
    out = new_run_dir(args.eval_id, prefix="eval_extraction")
    write_json(out / "extraction_metrics.json", {"SYNTHETIC_LABELS_NOT_REPORTABLE": lab.synthetic, "labels_dir": str(lab.base),
                                                 "n_passages": len(gold), "gold_no_factor": len(none),
                                                 "passages_not_extracted": missing, "results": res})
    for v, r in res.items():
        print(v, {k: round(r["code"][k], 3) for k in ("precision", "recall", "f1")}, "CI", r["f1_bootstrap95"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
