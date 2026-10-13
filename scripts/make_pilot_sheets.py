"""
make_pilot_sheets.py — blank sheets for the 10-mission HUMAN pilot (owner's decision 2026-10-13).

    python scripts/make_pilot_sheets.py          # creates evalutation/benchmark/pilot/ (refuses to overwrite)
    python scripts/pilot_derive.py               # after you filled D2a + D2q: pair grades + query file

The pilot uses the same formats and rules as the full benchmark (ANNOTATION_GUIDE.md), restricted to
10 missions with full board reports. You fill D2a (causal factors) and D2q (query descriptions); the
D2b pair grades are DERIVED from your D2a with the guide's grading rule (no assistant judgement).
"""

import csv
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "evalutation" / "benchmark"
OUT = KIT / "pilot"
MISSIONS = ["sts-51l-challenger", "sts-107-columbia", "mars-climate-orbiter", "ariane5-501", "apollo13",
            "genesis", "soho-1998", "wire", "hitomi", "starliner-cft"]


def main():
    if OUT.exists():
        print(f"{OUT} exists; refusing to overwrite (it may contain your labels)")
        return 1
    OUT.mkdir(parents=True)
    man = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["documents"]
    with open(OUT / "D2a_mission_factors.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mission", "factor_code", "role", "factor_short", "doc_id", "page", "quote", "note"])
        for m in MISSIONS:
            doc = next(d["doc_id"] for d in man if d["role"] == "primary" and d["mission_ids"] == [m])
            for _ in range(4):
                w.writerow([m, "", "", "", doc, "", "", ""])
    with open(OUT / "D2q_query_descriptions.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["query_id", "mission", "text", "author", "note"])
        for m in MISSIONS:
            w.writerow([f"T1-{m}", m, "", "", ""])
    shutil.copy(KIT / "causal_taxonomy.json", OUT / "causal_taxonomy.json")
    look = (KIT / "where_to_look.md").read_text(encoding="utf-8").split("\n## ")
    keep = [s for s in look[1:] if s.split("\n")[0].strip() in MISSIONS]
    (OUT / "where_to_look.md").write_text(look[0] + "\n## " + "\n## ".join(keep), encoding="utf-8")
    (OUT / "PILOT.json").write_text(json.dumps({"PILOT": True, "missions": MISSIONS, "created": "2026-10-13",
                                                "labels_by": "project owner (human)",
                                                "d2b": "derived from D2a by the guide's grading rule"}, indent=1),
                                    encoding="utf-8")
    (OUT / "PILOT_GUIDE.md").write_text(GUIDE, encoding="utf-8")
    print("created", OUT.relative_to(ROOT))
    return 0


GUIDE = """# 10-mission pilot — what to fill (about 4 hours)

Missions: Challenger, Columbia, Mars Climate Orbiter, Ariane 501, Apollo 13, Genesis, SOHO, WIRE, Hitomi, Starliner.
Open the PDFs in `data/raw/`; `where_to_look.md` gives the page ranges of each report's summary and cause chapters.
Full rules: `../ANNOTATION_GUIDE.md` (steps 1 and 1b). Do not look at any MissionMind output while labelling.

## 1. `D2a_mission_factors.csv` (about 15 min per mission)
Four rows per mission are prepared (the `doc_id` is filled in); add or delete rows. For each causal factor the
**board states**, fill:
- `factor_code`: one of the 22 codes (table below)
- `role`: `root` / `contributing` / `observation` (at least one `root` per mission)
- `factor_short`: up to 12 words in your own words
- `page`: the PDF page number shown by the viewer
- `quote`: a short verbatim excerpt (copy-paste, up to 30 words)
2–4 factors per mission is enough for the pilot.

## 2. `D2q_query_descriptions.csv` (about 8 min per mission)
For each mission, write 100–150 words in your own words describing the mishap **as first observed**: vehicle, mission
phase, what happened, what was seen in telemetry or on camera. **No causes, findings or recommendations**, and no
copied sentences.

## 3. Check and derive
    python scripts/check_annotations.py --dir evalutation/benchmark/pilot
    python scripts/pilot_derive.py
Then tell the assistant; the evaluation runs in about an hour.

| Group | Codes |
|---|---|
| T Technical | T1 hardware design · T2 software/requirements · T3 manufacturing/workmanship · T4 interface/heritage mismatch · T5 environment beyond design · T6 component failure |
| V Verification | V1 testing/qualification · V2 analysis/modelling · V3 review/independent assessment |
| O Operations | O1 procedure · O2 configuration/parameter error · O3 anomaly response/contingency · O4 monitoring/telemetry |
| H Human factors | H1 decision/skill error · H2 training/qualification · H3 communication |
| M Management | M1 schedule/cost pressure · M2 risk acceptance/normalisation of deviance · M3 safety & mission assurance · M4 systems engineering/config. mgmt · M5 oversight/roles · M6 staffing/resources |
"""


if __name__ == "__main__":
    sys.exit(main())
