"""
make_synthetic_labels.py — SYNTHETIC pseudo-labels for an end-to-end proof-of-concept run.

    python scripts/make_synthetic_labels.py

Writes evalutation/benchmark/synthetic/ with the same sheet formats as the human kit, plus
SYNTHETIC.json (marker detected by every evaluator, which then stamps its output
"SYNTHETIC_LABELS_NOT_REPORTABLE") and t1_queries.jsonl / d3_queries.jsonl for the runner.

Requested by the project owner on 2026-10-13 because human labelling is scheduled for later.
These labels are NOT a benchmark. They are produced WITHOUT the method under test (no LLM, no
use of the P extractor's output) to avoid grading P against itself:
  D2a  keyword rules per taxonomy code over each mission's Causes/Summary passages; role from cue words
  D2b  derived from D2a with the guide's grading rule
  D2q  the mission's description-field sentences with cause/finding/recommendation sentences removed
       (copied text: favours lexical retrieval such as BM25 — a known bias of these pseudo-labels)
  D1   the same keyword rules applied to the 200 D1 passages
  D3   template questions from D2a (single, cross), Disposition passages (lesson) and missions absent
       from the corpus (unanswerable)
"""

import csv
import itertools
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from retrieval.corpus import load_units, manifest  # noqa: E402

KIT = ROOT / "evalutation" / "benchmark"
OUT = KIT / "synthetic"

KEYWORDS = {
    "T1": [r"design (flaw|deficien|error|inadequa)", r"inadequate design", r"design margin", r"joint design", r"flawed design"],
    "T2": [r"\bsoftware\b", r"specification error", r"\bexception\b", r"\bcode\b"],
    "T3": [r"manufactur", r"workmanship", r"contaminat", r"\bdefect", r"fabricat"],
    "T4": [r"\binterface", r"heritage", r"\breuse", r"english units", r"metric units", r"incompatib"],
    "T5": [r"\btemperature", r"\bcold\b", r"\bfoam\b", r"\bdebris\b", r"\bheating\b", r"aerodynamic load"],
    "T6": [r"\bvalve", r"\bthruster", r"\bbattery", r"\bgyro"],
    "V1": [r"not tested", r"\bqualification", r"\btesting\b", r"test program"],
    "V2": [r"\bmodel(ing|ling|s)?\b", r"\bsimulation", r"\banalyses\b"],
    "V3": [r"peer review", r"independent review", r"design review", r"\breviews?\b"],
    "O1": [r"\bprocedures?\b", r"checklist", r"not followed"],
    "O2": [r"\bparameter", r"\bcommand(s|ed)?\b", r"uplink"],
    "O3": [r"contingency", r"anomaly response"],
    "O4": [r"\btelemetry", r"\bmonitor", r"\bwarning"],
    "H1": [r"\bdecision", r"human error", r"\bjudg(e)?ment"],
    "H2": [r"\btraining\b", r"\btrained\b", r"inexperience"],
    "H3": [r"communicat"],
    "M1": [r"\bschedule", r"\bbudget", r"\bpressure"],
    "M2": [r"accepted risk", r"normaliz", r"acceptable risk", r"flight rationale"],
    "M3": [r"\bsafety\b", r"quality assurance", r"mission assurance"],
    "M4": [r"systems engineering", r"configuration management", r"configuration control", r"change control"],
    "M5": [r"\boversight", r"\binsight\b", r"\bresponsibilit", r"management structure"],
    "M6": [r"understaff", r"\bstaffing", r"\bworkforce", r"insufficient resources"],
}
PATTERNS = {c: re.compile("|".join(ps), re.I) for c, ps in KEYWORDS.items()}
ROOT_CUE = re.compile(r"root cause|proximate cause|primary cause|direct cause|cause of the (accident|failure|mishap|loss)", re.I)
CONTRIB_CUE = re.compile(r"contribut", re.I)
CAUSE_CUE = re.compile(r"\bcaus|because|due to|root|contribut|finding|recommend|conclu|determin|board|commission|factor", re.I)
SENT = re.compile(r"(?<=[.!?])\s+")
MAX_CODES_PER_MISSION, MIN_HITS = 6, 2
UNANSWERABLE = ["Mars Observer (1993)", "Mars Polar Lander (1999)", "Beagle 2 (2003)", "Phobos-Grunt (2011)",
                "CONTOUR (2002)", "Lewis spacecraft (1997)", "Deep Space 2 (1999)", "Mars 96",
                "Zenit-3SL Sea Launch NSS-8 (2007)", "Proton-M Glonass launch failure (2013)"]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT.split(re.sub(r"\s+", " ", text)) if len(s.split()) >= 6]


def role_of(s: str) -> str:
    return "root" if ROOT_CUE.search(s) else "contributing" if CONTRIB_CUE.search(s) else "observation"


def quote_of(s: str, n: int = 30) -> str:
    return " ".join(s.split()[:n])


def match(text: str) -> list[tuple[str, str, str]]:
    """[(code, role, sentence)] for every keyword hit in a cause-bearing sentence."""
    out = []
    for s in sentences(text):
        if not CAUSE_CUE.search(s):
            continue
        for code, pat in PATTERNS.items():
            if pat.search(s):
                out.append((code, role_of(s), s))
    return out


def w(path: Path, header: list[str], rows: list[list]):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)                 # synthetic labels are regenerated deterministically
    OUT.mkdir(parents=True)
    man, units = manifest(), load_units(None)
    name = {m: d["mission"] for d in man.values() if d["role"] == "primary" for m in d["mission_ids"] if len(d["mission_ids"]) == 1}
    missions = sorted({m for u in units for m in u.missions})

    # D2a
    hits = defaultdict(lambda: defaultdict(list))
    for u in units:
        if u.field not in ("causes", "summary"):
            continue
        for code, role, s in match(u.text):
            for m in u.missions:
                hits[m][code].append((role, s, u))
    d2a, prof = [], {}
    for m in missions:
        ranked = sorted(((c, h) for c, h in hits[m].items() if len(h) >= MIN_HITS), key=lambda x: (-len(x[1]), x[0]))
        prof[m] = {}
        for code, h in ranked[:MAX_CODES_PER_MISSION]:
            roles = Counter(r for r, _, _ in h)
            role = "root" if roles["root"] else "contributing" if roles["contributing"] else "observation"
            role_s, s, u = next(x for x in h if x[0] == role)
            prof[m][code] = role
            d2a.append([m, code, role, f"{code} keyword evidence", u.doc_id, u.page, quote_of(s), "SYNTHETIC"])
    w(OUT / "D2a_mission_factors.csv", ["mission", "factor_code", "role", "factor_short", "doc_id", "page", "quote", "note"], d2a)

    # D2b (guide rule)
    pairs = list(itertools.combinations(missions, 2))
    d2b, grade = [], {}
    for i, (a, b) in enumerate(pairs, 1):
        shared = set(prof[a]) & set(prof[b])
        strong = {c for c in shared if prof[a][c] in ("root", "contributing") and prof[b][c] in ("root", "contributing")}
        g = 3 if any(prof[a][c] == prof[b][c] == "root" for c in shared) else 2 if strong else 1 if shared else 0
        grade[frozenset((a, b))] = g
        d2b.append([f"P{i:03d}", a, b, g, ";".join(sorted(shared)), "SYNTHETIC"])
    w(OUT / "D2b_mission_pairs.csv", ["pair_id", "mission_a", "mission_b", "grade", "shared_codes", "note"], d2b)

    # D2q (description sentences without cause/finding/recommendation cues, single-mission documents)
    d2q, t1 = [], []
    for m in missions:
        us = sorted((u for u in units if u.missions == (m,) and u.field == "summary"), key=lambda u: (u.doc_id, u.page, u.char_start))
        kept = [s for u in us for s in sentences(u.text) if not CAUSE_CUE.search(s)]
        text = " ".join(" ".join(kept).split()[:160])
        if len(text.split()) < 40:     # missions without description text: fall back to Causes-field sentences w/o cues
            us = sorted((u for u in units if m in u.missions and u.field == "causes"), key=lambda u: (u.page, u.char_start))
            kept = [s for u in us for s in sentences(u.text) if not CAUSE_CUE.search(s)]
            text = " ".join(" ".join(kept).split()[:160])
        d2q.append([f"T1-{m}", m, text, "SYNTHETIC", "SYNTHETIC"])
        t1.append({"query_id": f"T1-{m}", "mission": m, "kind": "T1_synthetic", "text": text})
    w(OUT / "D2q_query_descriptions.csv", ["query_id", "mission", "text", "author", "note"], d2q)

    # D1 (same rules on the D1 passages)
    by_id = {u.id: u for u in units}
    rows = list(csv.DictReader(open(KIT / "D1_passage_factors.csv", encoding="utf-8-sig")))
    d1 = []
    for r in rows:
        u = by_id.get(r["passage_id"])
        found = {}
        for code, role, s in match(u.text if u else r["text"]):
            if code not in found:
                # quote must be an exact substring of the passage text
                q = s if s in r["text"] else next((x for x in sentences(r["text"]) if x[:40] in s), "")
                q = re.split(r"[;|]", q)[0].strip()      # ";" and "|" are field separators in the D1 sheet
                if q and q in r["text"]:
                    found[code] = f"{code}|{role}|{quote_of(q, 25) if quote_of(q, 25) in r['text'] else q}"
        d1.append([r["item_id"], r["passage_id"], r["mission"], r["report"], r["page"], r["text"],
                   "" if found else "x", ";".join(found.values()), "SYNTHETIC"])
    w(OUT / "D1_passage_factors.csv", ["item_id", "passage_id", "mission", "report", "page", "text", "no_factor", "factors", "note"], d1)

    # D3 (templates)
    codes = {c["code"]: c["name"] for g in json.loads((KIT / "causal_taxonomy.json").read_text(encoding="utf-8"))["categories"]
             for c in g["children"]}
    ev = {(r[0], r[1]): (r[4], r[5], r[6]) for r in d2a}
    d3, k = [], 0
    for m in missions:
        roots = [(c, ev[(m, c)]) for c, role in prof[m].items() if role in ("root", "contributing")][:3]
        if roots and m in name:
            k += 1
            d3.append([f"S{k:03d}", "single", f"What caused the {name[m]} mishap, according to the investigation board?", m,
                       ";".join(e[2][:160] for _, e in roots), ";".join(f"{e[0]}:{e[1]}" for _, e in roots), "yes", "SYNTHETIC", ""])
    by_code = defaultdict(list)
    for m in missions:
        for c, role in prof[m].items():
            if role in ("root", "contributing"):
                by_code[c].append(m)
    k = 0
    for c, ms in sorted(by_code.items(), key=lambda x: (-len(x[1]), x[0])):
        if len(ms) >= 2 and k < 15:
            k += 1
            sel = ms[:4]
            d3.append([f"C{k:03d}", "cross", f"Which missions' boards identified {codes[c].lower()} as a cause or contributing factor?",
                       ";".join(sel), ";".join(f"{name.get(x, x)}: {ev[(x, c)][2][:120]}" for x in sel),
                       ";".join(f"{ev[(x, c)][0]}:{ev[(x, c)][1]}" for x in sel), "yes", "SYNTHETIC", ""])
    k = 0
    for m in missions:
        recs = [u for u in units if u.missions == (m,) and u.field == "disposition" and re.search(r"recommend", u.text, re.I)]
        if recs and m in name and k < 10:
            k += 1
            u = recs[0]
            s = next((x for x in sentences(u.text) if re.search(r"recommend", x, re.I)), sentences(u.text)[0] if sentences(u.text) else u.text[:200])
            d3.append([f"L{k:03d}", "lesson", f"What did the {name[m]} investigation board recommend?", m, s[:200],
                       f"{u.doc_id}:{u.page}", "yes", "SYNTHETIC", ""])
    for k, x in enumerate(UNANSWERABLE, 1):
        d3.append([f"U{k:03d}", "unanswerable", f"What caused the loss of {x}?", "", "", "", "no", "SYNTHETIC", ""])
    w(OUT / "D3_questions.csv", ["qid", "type", "question", "missions", "key_points", "evidence", "answerable", "author", "note"], d3)

    with open(OUT / "t1_queries.jsonl", "w", encoding="utf-8") as f:
        for q in t1:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    with open(OUT / "d3_queries.jsonl", "w", encoding="utf-8") as f:
        for r in d3:
            f.write(json.dumps({"query_id": r[0], "mission": "", "exclude_missions": [], "kind": f"D3_{r[1]}", "text": r[2]},
                               ensure_ascii=False) + "\n")
    shutil.copy(KIT / "causal_taxonomy.json", OUT / "causal_taxonomy.json")
    meta = {"SYNTHETIC": True, "not_reportable": True, "created": "2026-10-13", "requested_by": "project owner",
            "method": "keyword rules + templates; no LLM; independent of the P extractor",
            "known_bias": "D2q queries are copied report sentences (favours lexical retrieval); keyword factors are coarse",
            "counts": {"D2a_rows": len(d2a), "D2b_pairs": len(d2b), "grade_hist": dict(Counter(grade.values())),
                       "D2q": len(d2q), "D1_with_factor": sum(1 for r in d1 if r[7]), "D3": dict(Counter(r[1] for r in d3))}}
    (OUT / "SYNTHETIC.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta["counts"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
