"""
field_map_tool.py — helpers for the curated field maps (src/pipeline/field_maps.py).

  outline  <doc_id>            page-by-page heading outline (to write/check a map)
  apply    [--docs ...]        writes data/processed/fields/<doc_id>.jsonl for every
                               document that has a map; fails on invalid maps
  sample   --n 100 --seed S    draws the HELD-OUT test sheet (passages sampled uniformly,
                               sections of the DEV sheet excluded) for blind human labelling
  score    --run-id ID         scores mapped fields (and the Stage 2 heading rules, 4 labels)
                               against the labelled test sheet

The test sheet is written to evalutation/fixtures/field_test_sheet.csv with an
empty "label" column; the key (passage ids, doc ids) stays in the same file but
no predicted field is shown to the labeller.
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
from config import get_settings  # noqa: E402
from pipeline.field_maps import FIELDS, FROM_SIX, assign_fields, load_map, maps_dir, validate_map  # noqa: E402

DEV_SHEET = ROOT / "evalutation" / "fixtures" / "pseudo_field_sheet.jsonl"
TEST_SHEET = ROOT / "evalutation" / "fixtures" / "field_test_sheet.csv"


def _manifest() -> dict:
    return {d["doc_id"]: d for d in json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]}


def _passages(doc_id: str) -> list[dict]:
    path = get_settings().processed_dir / "passages" / f"{doc_id}.jsonl"
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def outline(doc_id: str) -> None:
    pages = [json.loads(l) for l in open(get_settings().processed_dir / "pages" / f"{doc_id}.jsonl", encoding="utf-8")]
    for p in pages:
        heads = [p["text"][b["start"]:b["end"]] for b in p["blocks"] if b["kind"] == "heading"]
        first = next((p["text"][b["start"]:b["end"]] for b in p["blocks"] if b["kind"] == "body"), "")
        print(f"p{p['page']:4d} | " + " || ".join(h[:70] for h in heads)[:220] + f"   ~ {first[:60]!r}")


def apply(docs: list[str] | None) -> int:
    manifest, bad = _manifest(), 0
    out_dir = get_settings().processed_dir / "fields"
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(maps_dir().glob("*.json")):
        doc = path.stem
        if docs and doc not in docs:
            continue
        m = load_map(doc)
        problems = validate_map(m, manifest.get(doc, {}).get("pages"))
        if problems:
            print(f"INVALID {doc}: {problems}")
            bad += 1
            continue
        rows = assign_fields(doc, _passages(doc), m)
        with open(out_dir / f"{doc}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        counts = {k: sum(r["field"] == k for r in rows) for k in FIELDS}
        print(f"{doc[:45]:45s} {m['status']:8s} {len(rows):5d} passages {counts}")
    return 1 if bad else 0


def sample(n: int, seed: int) -> int:
    if TEST_SHEET.exists():
        print(f"{TEST_SHEET.name} exists; refusing to redraw the held-out sample")
        return 1
    manifest = _manifest()
    dev = {(s["doc_id"], s["section"], s["chapter"]) for s in map(json.loads, open(DEV_SHEET, encoding="utf-8"))}
    pool, excluded = [], 0
    for doc, d in sorted(manifest.items()):
        if d["role"] != "primary" or not (get_settings().processed_dir / "passages" / f"{doc}.jsonl").exists():
            continue
        for p in _passages(doc):
            if (doc, p["section"] or "(no heading yet)", p["chapter"] or "") in dev:
                excluded += 1
                continue
            pool.append(p)
    rng = random.Random(seed)
    chosen = rng.sample(pool, n)
    with open(TEST_SHEET, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "passage_id", "report", "page", "section_heading", "text", "label"])
        for i, p in enumerate(chosen, 1):
            w.writerow([f"T{i:03d}", p["passage_id"], manifest[p["doc_id"]]["title"], p["page"],
                        p["section"] or "", p["text"], ""])
    meta = {"n": n, "seed": seed, "pool_passages": len(pool), "excluded_dev_passages": excluded,
            "documents": sorted({p["doc_id"] for p in pool}),
            "sha256_sheet_blank": hashlib.sha256(TEST_SHEET.read_bytes()).hexdigest()}
    TEST_SHEET.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    return 0


def score(run_id: str | None) -> int:
    from runlog import new_run_dir, write_json
    rows = list(csv.DictReader(open(TEST_SHEET, encoding="utf-8-sig")))
    labelled = [r for r in rows if r["label"].strip()]
    bad = [r["id"] for r in labelled if r["label"].strip().lower() not in FIELDS]
    if bad or not labelled:
        print(f"unlabelled sheet or invalid labels: {bad[:10]}")
        return 2
    by_doc, pred_map, pred_rules, words = {}, {}, {}, {}
    for r in labelled:
        doc = r["passage_id"].split("::")[0]
        by_doc.setdefault(doc, None)
    maps = {doc: load_map(doc) for doc in by_doc}
    status = {doc: (m or {}).get("status") for doc, m in maps.items()}
    for doc in by_doc:
        ps = {p["passage_id"]: p for p in _passages(doc)}
        for r in labelled:
            if r["passage_id"].startswith(doc + "::"):
                p = ps[r["passage_id"]]
                words[r["id"]] = p["n_words"]
                pred_rules[r["id"]] = FROM_SIX[p["pseudo_field"]]
                pred_map[r["id"]] = assign_fields(doc, [p], maps[doc])[0]["field"] if maps[doc] else None
    result = {}
    for name, pred in (("field_maps", pred_map), ("heading_rules_4way", pred_rules)):
        ok = [pred[r["id"]] == r["label"].strip().lower() for r in labelled]
        w = [words[r["id"]] for r in labelled]
        per_doc = {}
        for r, k in zip(labelled, ok):
            d = per_doc.setdefault(r["passage_id"].split("::")[0], [0, 0])
            d[0] += k
            d[1] += 1
        result[name] = {"n": len(ok), "accuracy": round(sum(ok) / len(ok), 4),
                        "word_weighted_accuracy": round(sum(a * b for a, b in zip(ok, w)) / sum(w), 4),
                        "per_document": {d: {"correct": c, "n": n} for d, (c, n) in per_doc.items()}}
    confusion = {}
    for r in labelled:
        k = f"{r['label'].strip().lower()} -> {pred_map[r['id']]}"
        confusion[k] = confusion.get(k, 0) + 1
    map_hashes = {doc: hashlib.sha256((maps_dir() / f"{doc}.json").read_bytes()).hexdigest()
                  for doc in by_doc if maps[doc]}
    run_dir = new_run_dir(run_id, prefix="field_test")
    write_json(run_dir / "field_test_accuracy.json", {"results": result, "confusion_gold_vs_map": confusion,
                                                       "map_status": status, "map_sha256": map_hashes,
                                                       "unlabelled": len(rows) - len(labelled)})
    print(json.dumps({k: {x: v[x] for x in ("n", "accuracy", "word_weighted_accuracy")} for k, v in result.items()}, indent=1))
    if any(s != "reviewed" for s in status.values()):
        print("WARNING: some maps are not 'reviewed':", {d: s for d, s in status.items() if s != "reviewed"})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("outline").add_argument("doc_id")
    a = sub.add_parser("apply")
    a.add_argument("--docs", nargs="*")
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--seed", type=int, required=True)
    sc = sub.add_parser("score")
    sc.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)
    if args.cmd == "outline":
        outline(args.doc_id)
        return 0
    if args.cmd == "apply":
        return apply(args.docs)
    if args.cmd == "sample":
        return sample(args.n, args.seed)
    return score(args.run_id)


if __name__ == "__main__":
    sys.exit(main())
