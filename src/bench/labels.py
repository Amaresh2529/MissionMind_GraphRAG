"""
labels.py — loads the completed human benchmark sheets (evalutation/benchmark).

  grades(q_mission, m)    D2b analogy grade 0-3 (symmetric)
  shared(q_mission, m)    D2b shared taxonomy codes
  factor_pages(m, codes)  D2a evidence (doc_id, page) of mission m for the given codes
  d1()                    D1 gold: {passage_id: set of (code, role)} and the no-factor set
  queries_t1()            D2q query descriptions
  questions_d3()          D3 questions
`require_complete=True` raises if a sheet is missing labels, so partial labels
cannot silently produce a result.
"""

import csv
import re
from pathlib import Path

B = Path(__file__).resolve().parent.parent.parent / "evalutation" / "benchmark"


class IncompleteLabels(RuntimeError):
    pass


def _rows(name: str, base: Path = B) -> list[dict]:
    p = base / name
    if not p.exists():
        raise IncompleteLabels(f"{name} missing")
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def _codes(s: str) -> set[str]:
    return {c for c in re.split(r"[;, ]+", s.strip()) if c}


class Labels:
    def __init__(self, base: Path = B, require_complete: bool = True):
        self.base = base
        d2b = _rows("D2b_mission_pairs.csv", base)
        missing = [r["pair_id"] for r in d2b if not r["grade"].strip()]
        if require_complete and missing:
            raise IncompleteLabels(f"D2b: {len(missing)} pairs ungraded")
        self._grade, self._shared = {}, {}
        for r in d2b:
            if r["grade"].strip():
                k = frozenset((r["mission_a"], r["mission_b"]))
                self._grade[k] = int(r["grade"])
                self._shared[k] = _codes(r["shared_codes"])
        self.d2a = [r for r in _rows("D2a_mission_factors.csv", base) if r["factor_code"].strip()]
        self.missions = sorted({r["mission_a"] for r in d2b} | {r["mission_b"] for r in d2b})

    def grade(self, a: str, b: str) -> int | None:
        return self._grade.get(frozenset((a, b)))

    def shared(self, a: str, b: str) -> set[str]:
        return self._shared.get(frozenset((a, b)), set())

    def factor_pages(self, mission: str, codes: set[str]) -> set[tuple[str, int]]:
        return {(r["doc_id"].strip(), int(r["page"])) for r in self.d2a
                if r["mission"] == mission and r["factor_code"].strip() in codes and r["page"].strip().isdigit()}

    def queries_t1(self) -> list[dict]:
        rows = _rows("D2q_query_descriptions.csv", self.base)
        empty = [r["query_id"] for r in rows if not r["text"].strip()]
        if empty:
            raise IncompleteLabels(f"D2q: {len(empty)} descriptions missing")
        return [{"query_id": r["query_id"], "mission": r["mission"], "kind": "T1_human", "text": r["text"].strip()}
                for r in rows]

    def questions_d3(self) -> list[dict]:
        return _rows("D3_questions.csv", self.base)

    def d1(self) -> tuple[dict, set]:
        rows = _rows("D1_passage_factors.csv", self.base)
        todo = [r["item_id"] for r in rows if not (r["no_factor"].strip() or r["factors"].strip())]
        if todo:
            raise IncompleteLabels(f"D1: {len(todo)} passages unlabelled")
        gold, none = {}, set()
        for r in rows:
            if r["no_factor"].strip():
                none.add(r["passage_id"])
            gold[r["passage_id"]] = {(f.split("|")[0].strip(), f.split("|")[1].strip())
                                     for f in r["factors"].split(";") if f.strip()}
        return gold, none
