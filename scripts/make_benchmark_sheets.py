"""
make_benchmark_sheets.py — creates the BLANK human-annotation sheets for the
MissionMind benchmark (nothing is pre-filled with system output, so labels stay
independent of the methods being evaluated).

  evalutation/benchmark/D2a_mission_factors.csv  one block per mission: board-stated causal factors
  evalutation/benchmark/D2b_mission_pairs.csv    all unordered mission pairs: analogy grade 0-3
  evalutation/benchmark/D1_passage_factors.csv   sampled passages: causal factors stated in the passage
  evalutation/benchmark/D3_questions.csv         empty question template (questions are human-written)
  evalutation/benchmark/where_to_look.md         per mission: documents and page ranges of its
                                                 summary / analysis / recommendation sections (from the field maps)
  evalutation/benchmark/sheets.meta.json         seed, counts, SHA-256 of every blank sheet

Refuses to overwrite an existing sheet (labels may already be in it).

    python scripts/make_benchmark_sheets.py --seed 20261013 --d1-n 200
"""

import argparse
import csv
import hashlib
import itertools
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from retrieval.corpus import load_units, manifest  # noqa: E402

OUT = ROOT / "evalutation" / "benchmark"


def _write(path: Path, header: list[str], rows: list[list]) -> str:
    if path.exists():
        raise FileExistsError(f"{path.name} exists; refusing to overwrite (may contain labels)")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--d1-n", type=int, default=200)
    args = ap.parse_args(argv)
    man = manifest()
    units = load_units(None)
    missions = sorted({m for d in man.values() if d["role"] == "primary" for m in d["mission_ids"]})
    docs_of = {m: [d for d in man.values() if d["role"] == "primary" and m in d["mission_ids"]] for m in missions}
    meta = {"seed": args.seed, "missions": missions, "sha256_blank": {}}

    # D2a: mission factor sheet (5 empty rows per mission; annotators add rows as needed)
    rows = []
    for m in missions:
        for _ in range(5):
            rows.append([m, "", "", "", "", "", "", ""])
    meta["sha256_blank"]["D2a_mission_factors.csv"] = _write(
        OUT / "D2a_mission_factors.csv",
        ["mission", "factor_code", "role", "factor_short", "doc_id", "page", "quote", "note"], rows)

    # D2b: all unordered pairs, in random order (seeded) so grading order carries no system signal
    pairs = list(itertools.combinations(missions, 2))
    random.Random(args.seed).shuffle(pairs)
    meta["sha256_blank"]["D2b_mission_pairs.csv"] = _write(
        OUT / "D2b_mission_pairs.csv", ["pair_id", "mission_a", "mission_b", "grade", "shared_codes", "note"],
        [[f"P{i:03d}", a, b, "", "", ""] for i, (a, b) in enumerate(pairs, 1)])
    meta["n_pairs"] = len(pairs)

    # D1: passages sampled uniformly from Summary + Causes fields of all primary documents
    pool = [u for u in units if u.field in ("summary", "causes") and len(u.text.split()) >= 40]
    chosen = random.Random(args.seed + 1).sample(pool, args.d1_n)
    meta["sha256_blank"]["D1_passage_factors.csv"] = _write(
        OUT / "D1_passage_factors.csv",
        ["item_id", "passage_id", "mission", "report", "page", "text", "no_factor", "factors", "note"],
        [[f"E{i:03d}", u.id, "/".join(u.missions), man[u.doc_id]["title"], u.page, u.text, "", "", ""]
         for i, u in enumerate(chosen, 1)])
    meta["d1"] = {"n": args.d1_n, "pool": len(pool), "min_words": 40, "fields": ["summary", "causes"],
                  "passage_ids": [u.id for u in chosen]}

    # D3: empty template
    meta["sha256_blank"]["D3_questions.csv"] = _write(
        OUT / "D3_questions.csv",
        ["qid", "type", "question", "missions", "key_points", "evidence", "answerable", "author", "note"], [])

    # where to look (from the field maps; navigation aid only, not labels)
    fm = ROOT / "data" / "field_maps"
    lines = ["# Where to look — per mission", "",
             "Navigation aid generated from the field maps: page ranges of each report's summary/description,",
             "analysis (causes, findings) and recommendation sections. It is **not** a label source: read the",
             "report and record only what the board itself states.", ""]
    for m in missions:
        lines.append(f"## {m}")
        for d in docs_of[m]:
            mp = json.loads((fm / f"{d['doc_id']}.json").read_text(encoding="utf-8"))
            parts = {}
            for r in mp["ranges"]:
                if r["field"] != "other":
                    parts.setdefault(r["field"], []).append(f"pp. {r['pages'][0]}-{r['pages'][1]}")
            lines.append(f"- **{d['title']}** (`{d['file']}`, {d['pages']} pages): " +
                         "; ".join(f"{k}: {', '.join(v)}" for k, v in parts.items()))
        lines.append("")
    (OUT / "where_to_look.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "sheets.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "d1"} | {"d1_n": args.d1_n, "d1_pool": len(pool)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
