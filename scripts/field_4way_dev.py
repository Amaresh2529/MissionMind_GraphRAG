"""
field_4way_dev.py — re-scores the saved DEV predictions (runs/stage2_field_methods_dev)
under the coarser 4-way scheme: description (summary+narrative), analysis
(findings+causes), recommendations, other. No new predictions are made.
"""

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from runlog import new_run_dir, write_json  # noqa: E402

FOUR = {"summary": "description", "narrative": "description", "findings": "analysis",
        "causes": "analysis", "recommendations": "recommendations", "other": "other"}


def main(run_id=None):
    sheet = [json.loads(l) for l in open(ROOT / "evalutation" / "fixtures" / "pseudo_field_sheet.jsonl", encoding="utf-8")]
    preds = json.loads((ROOT / "runs" / "stage2_field_methods_dev" / "dev_comparison.json").read_text(encoding="utf-8"))["predictions"]
    words = collections.Counter()
    for doc in {s["doc_id"] for s in sheet}:
        for l in open(ROOT / "data" / "processed" / "passages" / f"{doc}.jsonl", encoding="utf-8"):
            p = json.loads(l)
            words[(doc, p["section"] or "(no heading yet)", p["chapter"] or "")] += p["n_words"]
    result = {}
    for m, pr in preds.items():
        ok = [FOUR[pr[s["id"]]] == FOUR[s["gold"]] for s in sheet]
        w = [words[(s["doc_id"], s["section"], s["chapter"])] for s in sheet]
        result[m] = {"accuracy": sum(ok) / len(sheet),
                     "word_weighted_accuracy": round(sum(x * y for x, y in zip(ok, w)) / sum(w), 4)}
    run_dir = new_run_dir(run_id, prefix="field_4way_dev")
    write_json(run_dir / "four_way_dev.json", {"mapping": FOUR, "results": result})
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
