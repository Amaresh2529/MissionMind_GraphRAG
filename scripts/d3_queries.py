"""
d3_queries.py — converts the human D3 question sheet into a runner query file.

    python scripts/d3_queries.py      # -> evalutation/benchmark/d3_queries.jsonl

D3 questions may ask about any mission, so no mission is excluded from retrieval
("exclude_missions": []).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from bench.labels import Labels  # noqa: E402


def main():
    qs = Labels(require_complete=False).questions_d3()
    if not qs:
        print("D3_questions.csv has no questions yet")
        return 2
    out = ROOT / "evalutation" / "benchmark" / "d3_queries.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps({"query_id": q["qid"], "mission": "", "exclude_missions": [], "kind": f"D3_{q['type']}",
                                "text": q["question"]}, ensure_ascii=False) + "\n")
    print(f"{len(qs)} questions -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
