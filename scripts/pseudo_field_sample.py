"""
pseudo_field_sample.py — Stage 2 criterion B5.

  sample : draws 100 sections (distinct doc+section) at random (seed 42) from
           the PRIMARY documents of data/manifest.json, writes a labelling
           sheet with the heading, chapter and the opening text of the
           section's first passage. The parser's prediction is NOT shown on
           the sheet (blind labelling); it is kept in a separate key file.
  score  : compares the filled-in 'gold' labels with the predictions and
           writes accuracy + confusion matrix to runs/<run_id>/.

Label set: summary, narrative, findings, causes, recommendations, other.
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from runlog import new_run_dir, write_json  # noqa: E402

SHEET = ROOT / "evalutation" / "fixtures" / "pseudo_field_sheet.jsonl"
KEY = ROOT / "evalutation" / "fixtures" / "pseudo_field_key.json"
LABELS = ["summary", "narrative", "findings", "causes", "recommendations", "other"]


def sample(n: int = 100, seed: int = 42):
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    primary = [d["doc_id"] for d in manifest["documents"] if d["role"] == "primary"]
    sections = {}
    for doc in primary:
        for line in open(ROOT / "data" / "processed" / "passages" / f"{doc}.jsonl", encoding="utf-8"):
            p = json.loads(line)
            key = (doc, p["section"] or "(no heading yet)", p["chapter"] or "")
            sections.setdefault(key, p)          # first passage of the section
    keys = sorted(sections)
    picked = sorted(random.Random(seed).sample(keys, min(n, len(keys))))
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    key_out = {}
    with open(SHEET, "w", encoding="utf-8") as f:
        for i, k in enumerate(picked):
            p = sections[k]
            sid = f"S{i:03d}"
            f.write(json.dumps({"id": sid, "doc_id": k[0], "page": p["page"], "section": k[1], "chapter": k[2],
                                "excerpt": p["text"][:400], "gold": None}, ensure_ascii=False) + "\n")
            key_out[sid] = p["pseudo_field"]
    KEY.write_text(json.dumps(key_out, indent=1), encoding="utf-8")
    print(f"{len(picked)} sections sampled from {len(keys)} ({primary})")


def score(run_id=None):
    sheet = [json.loads(l) for l in open(SHEET, encoding="utf-8")]
    key = json.loads(KEY.read_text(encoding="utf-8"))
    labelled = [s for s in sheet if s["gold"]]
    if len(labelled) < len(sheet):
        print(f"warning: {len(sheet) - len(labelled)} items unlabelled")
    bad = [s["id"] for s in labelled if s["gold"] not in LABELS]
    if bad:
        raise SystemExit(f"invalid labels in {bad}")
    correct = sum(key[s["id"]] == s["gold"] for s in labelled)
    confusion = collections.Counter((s["gold"], key[s["id"]]) for s in labelled)
    by_doc = collections.defaultdict(lambda: [0, 0])
    for s in labelled:
        by_doc[s["doc_id"]][0] += key[s["id"]] == s["gold"]
        by_doc[s["doc_id"]][1] += 1
    result = {"n": len(labelled), "correct": correct, "accuracy": round(correct / len(labelled), 4),
              "per_document": {d: {"correct": c, "n": n, "accuracy": round(c / n, 4)} for d, (c, n) in by_doc.items()},
              "confusion_gold_vs_pred": {f"{g} -> {p}": n for (g, p), n in sorted(confusion.items())},
              "errors": [{"id": s["id"], "doc": s["doc_id"], "section": s["section"][:80],
                          "gold": s["gold"], "pred": key[s["id"]]} for s in labelled if key[s["id"]] != s["gold"]]}
    run_dir = new_run_dir(run_id, prefix="pseudo_field_score")
    write_json(run_dir / "pseudo_field_accuracy.json", result)
    print(json.dumps({k: result[k] for k in ("n", "correct", "accuracy", "per_document")}, indent=1))
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["sample", "score"])
    ap.add_argument("--run-id", default=None)
    a = ap.parse_args()
    sample() if a.action == "sample" else score(a.run_id)
