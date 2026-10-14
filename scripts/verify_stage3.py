"""
verify_stage3.py — checks Stage 3 criteria C3-C6 from SAVED run files only
(independent of the code that produced them).

    python scripts/verify_stage3.py runs/<run_a> [runs/<run_b>] --out runs/<check_id>

C3  every query of every system has 100 passages (or all allowed units if fewer), each with
    doc_id/page/field; B3 has exactly 6 lists; mission ranking present
C4  no passage belongs to the query's mission (manifest mission_ids of its document)
C5  (with run_b) predictions/*.jsonl byte-identical; generation/*.jsonl identical apart from the
    "cached" flag (reported separately: cached answers prove the cache, not model determinism)
C6  generation: parse rate, schema validity, invalid citations, chunks used
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b", nargs="?")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    a = Path(args.run_a)
    man = {d["doc_id"]: set(d["mission_ids"]) for d in
           json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    report, failures = {"C3": {}, "C4": {}, "C6": {}}, []
    for f in sorted((a / "predictions").glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        short = [r["query_id"] for r in rows if len(r["passages"]) != 100]
        missing = sum(1 for r in rows for p in r["passages"] if not (p.get("doc_id") and p.get("page") and p.get("field")))
        leaks = [(r["query_id"], p["id"]) for r in rows for p in r["passages"] if r["mission"] in man[p["doc_id"]]]
        mission_leaks = [r["query_id"] for r in rows if r["mission"] in r["mission_ranking"]]
        lists = sorted({len(r["lists"]) for r in rows})
        report["C3"][f.stem] = {"queries": len(rows), "queries_not_100": short, "missing_provenance": missing,
                                "n_lists": lists, "empty_mission_ranking": sum(not r["mission_ranking"] for r in rows)}
        report["C4"][f.stem] = {"leaked_passages": len(leaks), "leaked_missions": mission_leaks}
        if short or missing or leaks or mission_leaks or (f.stem == "B3" and lists != [6]):
            failures.append(f.stem)
    for f in sorted((a / "generation").glob("*.jsonl")) if (a / "generation").exists() else []:
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        n = len(rows)
        report["C6"][f.stem] = {
            "queries": n,
            "parsed": sum(r["answer"] is not None for r in rows),
            "schema_ok": sum(r["checks"]["schema_ok"] for r in rows),
            "items": sum(r["checks"]["items"] for r in rows),
            "citations": sum(r["checks"]["citations"] for r in rows),
            "invalid_citations": sum(r["checks"]["invalid_citations"] for r in rows),
            "uncited_items": sum(r["checks"]["uncited_items"] for r in rows),
            "chunks_used_min_max": [min(r["chunks_used"] for r in rows), max(r["chunks_used"] for r in rows)],
            "prompt_tokens_max": max((r["prompt_eval_count"] or 0) for r in rows),
        }
        enf = [r["enforcement"] for r in rows if r.get("enforcement") and "cause_items_raw" in r["enforcement"]]
        if enf:                                  # retention after enforcement (protocol section 10)
            raw_n, kept_n = sum(e["cause_items_raw"] for e in enf), sum(e["cause_items_kept"] for e in enf)
            report["C6"][f.stem].update({"cause_items_raw": raw_n, "cause_items_kept": kept_n,
                                         "retained_share": round(kept_n / raw_n, 4) if raw_n else None,
                                         "generic_dropped": sum(e.get("generic_dropped", 0) for e in enf),
                                         "abstained": sum(e["abstain"] for e in enf),
                                         "mechanisms_found": sum(len(r.get("mechanisms") or {}) for r in rows)})
    if args.run_b:
        b = Path(args.run_b)
        diff = {}
        for sub in ("predictions", "generation"):
            for f in sorted((a / sub).glob("*.jsonl")) if (a / sub).exists() else []:
                g = b / sub / f.name
                if sub == "predictions":
                    same = g.exists() and hashlib.sha256(f.read_bytes()).digest() == hashlib.sha256(g.read_bytes()).digest()
                else:   # generation: compare content; the "cached" flag only says where the answer came from
                    strip = lambda path: [{k: v for k, v in json.loads(l).items() if k != "cached"}
                                          for l in open(path, encoding="utf-8")]
                    same = g.exists() and strip(f) == strip(g)
                    report.setdefault("C5_cache_flags", {})[f.name] = {
                        "a_cached": sum(json.loads(l)["cached"] for l in open(f, encoding="utf-8")),
                        "b_cached": sum(json.loads(l)["cached"] for l in open(g, encoding="utf-8")) if g.exists() else None}
                diff[f"{sub}/{f.name}"] = same
        report["C5"] = {"run_b": str(b), "identical": diff, "all_identical": all(diff.values())}
        if not all(diff.values()):
            failures.append("C5")
    report["failures"] = failures
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "stage3_check.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    print("PASS" if not failures else f"FAIL: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
