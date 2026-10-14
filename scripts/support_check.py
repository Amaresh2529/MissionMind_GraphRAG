"""
support_check.py — does a verified quote actually SUPPORT the claimed causal factor? (2026-10-13)

Quote verification proves the quote exists in the report (textual provenance), not that it supports the claimed
cause (causal correctness). This script adds two checks:

  llm      the local LLM judges each accepted factor: {"supported": true|false} given quote + claimed statement +
           category + role (cached by prompt hash). Same model family as the extractor, so it is a weak check.
  sheet    D4 human review sheet: 100 accepted + 50 rejected factors (seeded sample) with an empty verdict column.
           The human verdicts are the real measurement (precision of accepted factors; how many rejected ones
           were actually right).

    python scripts/support_check.py --run-id stage4_support_check          # LLM check over all accepted factors
    python scripts/support_check.py --sheet                                 # create the D4 human sheet (once)
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from config import get_settings  # noqa: E402
from extension import factor_extractor as fx  # noqa: E402

SYSTEM = ('You check claims extracted from spaceflight mishap investigation reports. Respond with ONLY '
          '{"supported": true} or {"supported": false}.')
USER = """Quote from the report:
\"\"\"{quote}\"\"\"

Claimed causal factor: {statement}
Category: {code} {name}
Role claimed: {role} (root = stated root/primary/proximate cause; contributing = contributing factor; observation = deficiency noted)

Does the quote itself state or directly support this causal factor in this category? Answer false if the quote is only
background, chronology, a recommendation, or does not mention the claimed deficiency."""


def mentions():
    out = []
    for f in sorted((get_settings().processed_dir / "factors").glob("*.jsonl")):
        for r in map(json.loads, open(f, encoding="utf-8")):
            for k, items in (("accepted", r["accepted"]), ("rejected", r["rejected"])):
                for i, x in enumerate(items):
                    out.append({"status": k, "passage_id": r["passage_id"], "doc_id": r["doc_id"], "page": r["page"],
                                "idx": i, **x})
    return out


def run_llm(run_id: str) -> int:
    from runlog import new_run_dir, write_json, environment_info
    run = new_run_dir(run_id, prefix="support")
    write_json(run / "env.json", environment_info(include_services=True))
    names = {c: v["name"] for c, v in fx.codes().items()}
    model = get_settings().llm_model
    rows, n_sup = [], 0
    acc = [m for m in mentions() if m["status"] == "accepted"]
    for k, m in enumerate(acc, 1):
        user = USER.format(quote=m["quote"], statement=m["statement"], code=m["code"], name=names.get(m["code"], ""),
                           role=m["role"])
        raw, cached = fx._llm(SYSTEM, user, model)
        try:
            sup = bool(json.loads(raw).get("supported"))
        except (json.JSONDecodeError, AttributeError):
            sup = None
        n_sup += bool(sup)
        rows.append({"passage_id": m["passage_id"], "idx": m["idx"], "code": m["code"], "role": m["role"],
                     "supported": sup, "cached": cached})
        if k % 250 == 0:
            print(f"{k}/{len(acc)} checked, supported so far {n_sup}", flush=True)
    out_dir = get_settings().processed_dir / "factor_support"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "support.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    by_code = {}
    for r in rows:
        d = by_code.setdefault(r["code"], [0, 0])
        d[0] += bool(r["supported"])
        d[1] += 1
    stats = {"accepted_checked": len(rows), "supported": n_sup, "not_supported": sum(r["supported"] is False for r in rows),
             "unparsed": sum(r["supported"] is None for r in rows), "supported_share": round(n_sup / len(rows), 4),
             "by_code": {c: {"supported": a, "n": n} for c, (a, n) in sorted(by_code.items())},
             "note": "LLM self-check (same model family as the extractor); validate with the D4 human sheet"}
    write_json(run / "support_stats.json", stats)
    print(json.dumps({k: v for k, v in stats.items() if k != "by_code"}))
    return 0


def make_sheet(seed: int = 20261013) -> int:
    path = ROOT / "evalutation" / "benchmark" / "D4_factor_review.csv"
    if path.exists():
        print(f"{path.name} exists; refusing to overwrite")
        return 1
    ms = mentions()
    rng = random.Random(seed)
    acc = rng.sample([m for m in ms if m["status"] == "accepted"], 100)
    rej = rng.sample([m for m in ms if m["status"] == "rejected" and m.get("code")], 50)
    items = acc + rej
    rng.shuffle(items)                                       # reviewer does not see which were accepted
    texts = {}
    for d in {m["doc_id"] for m in items}:
        for r in map(json.loads, open(get_settings().processed_dir / "passages" / f"{d}.jsonl", encoding="utf-8")):
            texts[r["passage_id"]] = r["text"]
    key = []
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item", "passage_text", "claimed_statement", "code", "role", "quote",
                    "factor_correct_yes_no", "quote_supports_yes_no", "note"])
        for i, m in enumerate(items, 1):
            w.writerow([f"F{i:03d}", texts.get(m["passage_id"], ""), m.get("statement", ""), m.get("code", ""),
                        m.get("role", ""), m.get("quote", ""), "", "", ""])
            key.append({"item": f"F{i:03d}", "passage_id": m["passage_id"], "status": m["status"],
                        "reason": m.get("reason")})
    (path.with_suffix(".key.json")).write_text(json.dumps({"seed": seed, "items": key}, indent=1), encoding="utf-8")
    print(f"{path.relative_to(ROOT)}: 150 items (100 accepted, 50 rejected, shuffled; key in .key.json)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id")
    ap.add_argument("--sheet", action="store_true")
    args = ap.parse_args(argv)
    if args.sheet:
        return make_sheet()
    if not args.run_id:
        ap.error("--run-id required for the LLM check")
    return run_llm(args.run_id)


if __name__ == "__main__":
    sys.exit(main())
