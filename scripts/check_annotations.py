"""
check_annotations.py — format and consistency checks for the human benchmark sheets,
plus inter-annotator agreement when the *_B.csv copies exist. Never scores a system.

    python scripts/check_annotations.py [--out runs/<id>]

Checks
  D2a  codes/roles valid; mission known; doc belongs to the mission; page within the document;
       quote found on that page (whitespace/case-insensitive); >= 1 root factor per labelled mission
  D2b  grade in 0-3; shared codes valid
  D1   no_factor XOR factors; each factor "code|role|quote" with the quote found in the passage text
  D3   type, answerable, missions and evidence (doc_id:page) valid
Agreement (if B sheets exist)
  D2b  quadratic-weighted Cohen's kappa on grades of pairs graded by both
  D1   per-item code-set agreement (mean Jaccard) and Cohen's kappa on "has a factor"
  D2a  per-mission code-set Jaccard
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "evalutation" / "benchmark"
ROLES = {"root", "contributing", "observation"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _rows(name: str) -> list[dict] | None:
    p = B / name
    return list(csv.DictReader(open(p, encoding="utf-8-sig"))) if p.exists() else None


def _codes() -> set[str]:
    t = json.loads((B / "causal_taxonomy.json").read_text(encoding="utf-8"))
    return {c["code"] for g in t["categories"] for c in g["children"]}


def _page_texts() -> dict:
    cache = {}
    def get(doc, page):
        if doc not in cache:
            p = ROOT / "data" / "processed" / "pages" / f"{doc}.jsonl"
            cache[doc] = {r["page"]: r["text"] for r in map(json.loads, open(p, encoding="utf-8"))} if p.exists() else {}
        return cache[doc].get(page)
    return get


def kappa(a: list, b: list, weights: str | None = None) -> float | None:
    cats = sorted(set(a) | set(b))
    if len(a) < 2 or len(cats) < 2:
        return None
    k, n = len(cats), len(a)
    idx = {c: i for i, c in enumerate(cats)}
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1 / n
    pa = [sum(r) for r in obs]
    pb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    def w(i, j):
        if weights == "quadratic":
            return ((i - j) / (k - 1)) ** 2
        return 0.0 if i == j else 1.0
    do = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k))
    de = sum(w(i, j) * pa[i] * pb[j] for i in range(k) for j in range(k))
    return None if de == 0 else round(1 - do / de, 4)


def check() -> dict:
    man = {d["doc_id"]: d for d in json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]}
    missions = {m for d in man.values() if d["role"] == "primary" for m in d["mission_ids"]}
    codes, page_text, rep = _codes(), _page_texts(), {}

    d2a = _rows("D2a_mission_factors.csv") or []
    errs, filled, roots = [], [r for r in d2a if r["factor_code"].strip()], {}
    for i, r in enumerate(filled, 2):
        tag = f"D2a {r['mission']} row"
        if r["mission"] not in missions: errs.append(f"{tag}: unknown mission")
        if r["factor_code"].strip() not in codes: errs.append(f"{tag}: code {r['factor_code']!r}")
        if r["role"].strip() not in ROLES: errs.append(f"{tag}: role {r['role']!r}")
        d = man.get(r["doc_id"].strip())
        if not d or r["mission"] not in d["mission_ids"]:
            errs.append(f"{tag}: doc {r['doc_id']!r} not a document of this mission"); continue
        try:
            page = int(r["page"])
        except ValueError:
            errs.append(f"{tag}: page {r['page']!r}"); continue
        text = page_text(d["doc_id"], page)
        if text is None: errs.append(f"{tag}: page {page} not in document")
        elif r["quote"].strip() and _norm(r["quote"]) not in _norm(text):
            errs.append(f"{tag}: quote not found on {d['doc_id']} p.{page} (OCR differences? check)")
        if r["role"].strip() == "root": roots[r["mission"]] = roots.get(r["mission"], 0) + 1
    labelled = {r["mission"] for r in filled}
    rep["D2a"] = {"rows": len(filled), "missions_labelled": len(labelled), "missions_total": len(missions),
                  "missions_without_root": sorted(labelled - set(roots)), "errors": errs}

    d2b = _rows("D2b_mission_pairs.csv") or []
    errs, graded = [], [r for r in d2b if r["grade"].strip()]
    for r in graded:
        if r["grade"].strip() not in {"0", "1", "2", "3"}: errs.append(f"D2b {r['pair_id']}: grade {r['grade']!r}")
        bad = [c for c in re.split(r"[;, ]+", r["shared_codes"].strip()) if c and c not in codes]
        if bad: errs.append(f"D2b {r['pair_id']}: codes {bad}")
    rep["D2b"] = {"graded": len(graded), "total": len(d2b), "errors": errs}

    d1 = _rows("D1_passage_factors.csv") or []
    errs, done = [], [r for r in d1 if r["no_factor"].strip() or r["factors"].strip()]
    for r in done:
        if r["no_factor"].strip() and r["factors"].strip(): errs.append(f"D1 {r['item_id']}: both no_factor and factors")
        for f in filter(None, (x.strip() for x in r["factors"].split(";"))):
            parts = f.split("|", 2)
            if len(parts) != 3: errs.append(f"D1 {r['item_id']}: {f[:40]!r} is not code|role|quote"); continue
            c, ro, q = (p.strip() for p in parts)
            if c not in codes: errs.append(f"D1 {r['item_id']}: code {c!r}")
            if ro not in ROLES: errs.append(f"D1 {r['item_id']}: role {ro!r}")
            if _norm(q) not in _norm(r["text"]): errs.append(f"D1 {r['item_id']}: quote not in passage")
    rep["D1"] = {"labelled": len(done), "total": len(d1), "errors": errs}

    d3 = _rows("D3_questions.csv") or []
    errs = []
    for r in d3:
        if r["type"] not in {"single", "cross", "lesson", "unanswerable"}: errs.append(f"D3 {r['qid']}: type {r['type']!r}")
        if r["answerable"] not in {"yes", "no"}: errs.append(f"D3 {r['qid']}: answerable {r['answerable']!r}")
        for m in filter(None, (x.strip() for x in r["missions"].split(";"))):
            if m not in missions: errs.append(f"D3 {r['qid']}: mission {m!r}")
        for e in filter(None, (x.strip() for x in r["evidence"].split(";"))):
            doc, _, page = e.rpartition(":")
            if doc not in man or not page.isdigit() or not 1 <= int(page) <= man[doc]["pages"]:
                errs.append(f"D3 {r['qid']}: evidence {e!r}")
    rep["D3"] = {"questions": len(d3), "by_type": {t: sum(r["type"] == t for r in d3) for t in
                                                  ("single", "cross", "lesson", "unanswerable")}, "errors": errs}

    agreement = {}
    b2 = _rows("D2b_mission_pairs_B.csv")
    if b2:
        ga = {r["pair_id"]: r["grade"].strip() for r in d2b if r["grade"].strip()}
        both = [(ga[r["pair_id"]], r["grade"].strip()) for r in b2 if r["grade"].strip() and r["pair_id"] in ga]
        agreement["D2b_quadratic_kappa"] = {"n": len(both), "kappa": kappa([int(a) for a, _ in both], [int(b) for _, b in both], "quadratic")}
    b1 = _rows("D1_passage_factors_B.csv")
    if b1:
        def cs(r): return {f.split("|")[0].strip() for f in r["factors"].split(";") if f.strip()}
        A = {r["item_id"]: r for r in done}
        both = [(A[r["item_id"]], r) for r in b1 if (r["no_factor"].strip() or r["factors"].strip()) and r["item_id"] in A]
        jac = [len(cs(a) & cs(b)) / len(cs(a) | cs(b)) if cs(a) | cs(b) else 1.0 for a, b in both]
        agreement["D1"] = {"n": len(both), "mean_code_jaccard": round(sum(jac) / len(jac), 4) if jac else None,
                           "has_factor_kappa": kappa([bool(cs(a)) for a, _ in both], [bool(cs(b)) for _, b in both])}
    b2a = _rows("D2a_mission_factors_B.csv")
    if b2a:
        def mc(rows, m): return {r["factor_code"].strip() for r in rows if r["mission"] == m and r["factor_code"].strip()}
        ms = sorted({r["mission"] for r in b2a if r["factor_code"].strip()})
        agreement["D2a_code_jaccard"] = {m: round(len(mc(filled, m) & mc(b2a, m)) / max(1, len(mc(filled, m) | mc(b2a, m))), 3) for m in ms}
    rep["agreement"] = agreement
    rep["ok"] = not any(rep[k]["errors"] for k in ("D2a", "D2b", "D1", "D3"))
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    rep = check()
    if args.out:
        out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
        (out / "annotation_check.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    for k in ("D2a", "D2b", "D1", "D3"):
        r = rep[k]
        print(k, {x: v for x, v in r.items() if x != "errors"}, f"errors={len(r['errors'])}")
        for e in r["errors"][:15]:
            print("   ", e)
    if rep["agreement"]:
        print("agreement", json.dumps(rep["agreement"]))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
