"""
compare_field_methods_dev.py — DEV comparison of pseudo-field methods on the
already-labelled 100-section sample (rules v4 errors were inspected, so this
sample is DEV data from now on; final accuracy is measured on a fresh sample).

Methods: rules (page_parser), llm (every section), hybrid (rules for explicit
front/back matter, LLM otherwise). Reports unweighted and word-weighted accuracy.
"""

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from runlog import new_run_dir, write_json  # noqa: E402
from pipeline.field_classifier import classify_section, rule_says_other, _cache_file  # noqa: E402

SHEET = ROOT / "evalutation" / "fixtures" / "pseudo_field_sheet.jsonl"
KEY = ROOT / "evalutation" / "fixtures" / "pseudo_field_key.json"


def main(run_id=None):
    sheet = [json.loads(l) for l in open(SHEET, encoding="utf-8")]
    rules = json.loads(KEY.read_text(encoding="utf-8"))
    manifest = {d["doc_id"]: d["title"] for d in json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    words, first = collections.Counter(), {}
    for doc in {s["doc_id"] for s in sheet}:
        for l in open(ROOT / "data" / "processed" / "passages" / f"{doc}.jsonl", encoding="utf-8"):
            p = json.loads(l)
            k = (doc, p["section"] or "(no heading yet)", p["chapter"] or "")
            words[k] += p["n_words"]
            first.setdefault(k, p)
    caches = {}
    preds = {"rules": {}, "llm": {}, "hybrid": {}}
    for s in sheet:
        k = (s["doc_id"], s["section"], s["chapter"])
        p = first[k]
        cache = caches.setdefault(s["doc_id"], json.loads(_cache_file(s["doc_id"]).read_text(encoding="utf-8"))
                                  if _cache_file(s["doc_id"]).exists() else {})
        llm = classify_section(s["doc_id"], manifest[s["doc_id"]], p["section"], p["chapter"], p["text"], cache)
        preds["rules"][s["id"]] = rules[s["id"]]
        preds["llm"][s["id"]] = llm
        preds["hybrid"][s["id"]] = "other" if rule_says_other(p["section"], p["chapter"]) else llm
    for doc, cache in caches.items():
        _cache_file(doc).parent.mkdir(parents=True, exist_ok=True)
        _cache_file(doc).write_text(json.dumps(cache), encoding="utf-8")
    result = {}
    for m, pr in preds.items():
        tot = cor = 0
        for s in sheet:
            w = words[(s["doc_id"], s["section"], s["chapter"])]
            tot += w
            cor += w * (pr[s["id"]] == s["gold"])
        result[m] = {"accuracy": sum(pr[s["id"]] == s["gold"] for s in sheet) / len(sheet),
                     "word_weighted_accuracy": round(cor / tot, 4)}
    run_dir = new_run_dir(run_id, prefix="field_methods_dev")
    write_json(run_dir / "dev_comparison.json", {"results": result, "predictions": preds})
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
