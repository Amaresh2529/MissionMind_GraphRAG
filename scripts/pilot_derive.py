"""
pilot_derive.py — after the owner filled the pilot D2a and D2q sheets:
  - refuses if a mission has no factor rows, no `root` factor, or no query description;
  - D2b_mission_pairs.csv: grades for all 45 pairs DERIVED from the human D2a by the guide's rule
      3 = share a code that is root in both; 2 = share a code that is root/contributing in both;
      1 = share any code; 0 = nothing shared
  - t1_queries.jsonl for the retrieval runner (from D2q).

    python scripts/pilot_derive.py
"""

import csv
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "evalutation" / "benchmark" / "pilot"
STRONG = ("root", "contributing")


def main(argv=None):
    import argparse
    global P
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    args = ap.parse_args(argv)
    if args.dir:
        P = Path(args.dir)
    missions = json.loads((P / "PILOT.json").read_text(encoding="utf-8"))["missions"]
    d2a = [r for r in csv.DictReader(open(P / "D2a_mission_factors.csv", encoding="utf-8-sig")) if r["factor_code"].strip()]
    d2q = {r["mission"]: r for r in csv.DictReader(open(P / "D2q_query_descriptions.csv", encoding="utf-8-sig"))}
    prof, problems = {m: {} for m in missions}, []
    for r in d2a:
        c, role = r["factor_code"].strip(), r["role"].strip()
        best = prof[r["mission"]].get(c)
        order = {"root": 0, "contributing": 1, "observation": 2}
        if best is None or order.get(role, 3) < order.get(best, 3):
            prof[r["mission"]][c] = role
    for m in missions:
        if not prof[m]:
            problems.append(f"{m}: no D2a factor rows")
        elif "root" not in prof[m].values():
            problems.append(f"{m}: no root factor")
        if not d2q.get(m, {}).get("text", "").strip():
            problems.append(f"{m}: no D2q description")
    if problems:
        print("NOT READY:\n  " + "\n  ".join(problems))
        return 1
    rows = []
    for i, (a, b) in enumerate(itertools.combinations(missions, 2), 1):
        shared = set(prof[a]) & set(prof[b])
        if any(prof[a][c] == prof[b][c] == "root" for c in shared):
            g = 3
        elif any(prof[a][c] in STRONG and prof[b][c] in STRONG for c in shared):
            g = 2
        else:
            g = 1 if shared else 0
        rows.append([f"P{i:03d}", a, b, g, ";".join(sorted(shared)), "derived from human D2a (guide rule)"])
    with open(P / "D2b_mission_pairs.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pair_id", "mission_a", "mission_b", "grade", "shared_codes", "note"])
        w.writerows(rows)
    with open(P / "t1_queries.jsonl", "w", encoding="utf-8") as f:
        for m in missions:
            f.write(json.dumps({"query_id": f"T1-{m}", "mission": m, "kind": "T1_human_pilot",
                                "text": d2q[m]["text"].strip()}, ensure_ascii=False) + "\n")
    hist = {g: sum(r[3] == g for r in rows) for g in range(4)}
    print(f"{len(rows)} pair grades derived {hist}; queries -> {P / 't1_queries.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
