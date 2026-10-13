"""
pilot_complete_assistant.py — completes the 10-mission pilot D2a sheet at the owner's request (2026-10-13).

PROVENANCE (recorded in every row's `note` and in PILOT.json):
  owner rows (Columbia, Genesis, SOHO, WIRE, Starliner): factor selection, wording and quotes by the OWNER.
    The assistant only (a) mapped the owner's own codes to the 22 taxonomy codes, (b) mapped roles to
    root/contributing/observation (Proximate/Direct -> root, Indirect -> contributing), (c) corrected the
    page to the PDF page where the quote is found, (d) kept the first continuous fragment of quotes with "...".
  assistant rows (Challenger, MCO, Ariane 501, Apollo 13, Hitomi): written by the ASSISTANT (Claude) from the
    boards' own statements; every quote is verified verbatim against the page text. The assistant also built
    the method under test, so these labels may favour it: the pilot is reported as mixed/AI-assisted, not human.

The owner's original sheet is kept as D2a_mission_factors.owner_original.csv.
"""

import csv
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / "evalutation" / "benchmark" / "pilot"

# owner code -> taxonomy code, per mission (assistant mapping of the owner's categories)
CODE_MAP = {
    ("sts-107-columbia", "PHYS-01"): "T5",   # foam debris strike breached the TPS
    ("sts-107-columbia", "ORG-01"): "M2",    # organisational causes rooted in history and culture
    ("sts-107-columbia", "ORG-02"): "M1",    # schedule pressure
    ("sts-107-columbia", "ORG-03"): "M3",    # no effective checks and balances / independent safety program
    ("genesis", "PHYS-01"): "T1",            # G-switches installed in the opposite direction (design)
    ("genesis", "ORG-01"): "M4",             # no penetrating systems engineering process
    ("genesis", "ENG-01"): "T4",             # heritage broken, not understood
    ("genesis", "TEST-01"): "V1",            # no Test-As-You-Fly exceptions list
    ("soho-1998", "ENG-01"): "O2",           # omission in the modified command sequence
    ("soho-1998", "ENG-02"): "H1",           # rapid decision that Gyro B was faulty
    ("soho-1998", "ORG-01"): "M4",           # procedure modifications not controlled by configuration board
    ("soho-1998", "ORG-02"): "M1",           # aggressive operations plan driven by scheduling
    ("wire", "ENG-01"): "T1",                # digital logic design error in pyro electronics
    ("wire", "ENG-02"): "T1",                # oscillator start-up time not considered (design)
    ("wire", "ORG-01"): "V3",                # box design not peer reviewed
    ("wire", "TEST-01"): "V1",               # box-level testing not representative
    ("starliner-cft", "TEST-01"): "V1",      # lacked mission-representative testing
    ("starliner-cft", "PHYS-01"): "T5",      # Teflon poppet extrusion (thermal environment)
    ("starliner-cft", "PHYS-02"): "T1",      # seal material incompatible (design/material selection)
    ("starliner-cft", "ORG-01"): "M2",       # acceptance of unexplained anomalies
}
ROLE_MAP = {"root": "root", "proximate": "root", "direct": "root", "contributing": "contributing",
            "indirect": "contributing", "observation": "observation"}

# (mission, code, role, factor_short, doc_id, page, verbatim quote)
ASSISTANT_ROWS = [
    ("sts-51l-challenger", "T1", "root", "Faulty aft field joint design sensitive to temperature and other factors",
     "Challenger", 79, "The failure was due to a faulty design unacceptably sensitive to a number of factors"),
    ("sts-51l-challenger", "T5", "contributing", "Cold launch temperature degraded O-ring sealing",
     "Challenger", 79, "These factors were the effects of temperature"),
    ("sts-51l-challenger", "M2", "contributing", "Launch constraints waived at the expense of flight safety",
     "Challenger", 111, "The waiving of launch constraints appears to have been at the expense of flight safety"),
    ("sts-51l-challenger", "M5", "contributing", "Management structure let safety problems bypass key managers",
     "Challenger", 89, "a NASA management structure that permitted internal flight safety problems to bypass key Shuttle managers"),
    ("sts-51l-challenger", "M1", "contributing", "Overambitious flight rate without adequate resources",
     "Challenger", 170, "goal of two flights a month was overambitious"),
    ("mars-climate-orbiter", "T4", "root", "English instead of metric units in ground software file",
     "Mars_Climate_Orbiter", 16, "the failure to use metric units in the coding of a ground software file"),
    ("mars-climate-orbiter", "V2", "contributing", "Spacecraft velocity changes mismodelled",
     "Mars_Climate_Orbiter", 17, "MCO Contributing Cause No. 1: Modeling of Spacecraft Velocity Changes"),
    ("mars-climate-orbiter", "O3", "contributing", "Contingency manoeuvre TCM-5 discussed but never executed",
     "Mars_Climate_Orbiter", 19, "A request to perform a TCM-5 was discussed verbally shortly before the MOI onboard procedure was initiated, but was never executed"),
    ("mars-climate-orbiter", "M4", "contributing", "Systems engineering did not transition to operations",
     "Mars_Climate_Orbiter", 21, "the systems engineering process did not adequately transition from development to operations"),
    ("mars-climate-orbiter", "H3", "contributing", "Inadequate communication between project elements",
     "Mars_Climate_Orbiter", 22, "evidence of inadequate communications between the project elements"),
    ("mars-climate-orbiter", "M6", "contributing", "Navigation team understaffed",
     "Mars_Climate_Orbiter", 23, "the staffing of the operations navigation team was less than adequate"),
    ("ariane5-501", "T2", "root", "Specification and design errors in inertial reference software",
     "ESA_Ariane5_501_Inquiry_Board_Report", 16, "This loss of information was due to specification and design errors in the software of the inertial reference system"),
    ("ariane5-501", "V1", "contributing", "Reviews and tests lacked adequate analysis and testing of the SRI",
     "ESA_Ariane5_501_Inquiry_Board_Report", 16, "did not include adequate analysis and testing of the inertial reference system or of the complete flight control system"),
    ("ariane5-501", "T4", "contributing", "Ariane 4 software reused on a different Ariane 5 trajectory",
     "ESA_Ariane5_501_Inquiry_Board_Report", 8, "part of the trajectory of Ariane 5 differs from that of Ariane 4 and results in considerably higher horizontal velocity values"),
    ("apollo13", "T1", "root", "Combination of mistakes with a deficient and unforgiving tank design",
     "NASA_Apollo13_Review_Board", 174, "resulted from an unusual combination of mistakes, coupled with a somewhat deficient and unforgiving design"),
    ("apollo13", "T4", "root", "28 V thermostatic switches used with 65 V ground power",
     "NASA_Apollo13_Review_Board", 132, "could not open properly at 65 V"),
    ("apollo13", "V1", "contributing", "Qualification tests never checked switches opening under full current",
     "NASA_Apollo13_Review_Board", 132, "Qualification and test procedures for the heater assemblies and switches do not at any time test the capability of the switches to open while under full current conditions"),
    ("hitomi", "T2", "root", "Attitude control system wrongly determined the satellite was rotating",
     "JAXA_Hitomi_Experience_Report", 29, "caused incorrect determination of its attitude as rotating, although the satellite was not rotating actually"),
    ("hitomi", "O2", "root", "Inappropriate thruster control parameters accelerated the rotation",
     "JAXA_Hitomi_Experience_Report", 29, "by the inappropriate thruster control parameters"),
    ("hitomi", "T1", "contributing", "Anomaly detection relied only on attitude estimates (FDIR design)",
     "JAXA_Hitomi_Experience_Report", 60, "the satellite was designed to rely on only the ACFS estimates"),
    ("hitomi", "M3", "contributing", "Insufficient recognition of needs for safe operations",
     "JAXA_Hitomi_Experience_Report", 82, "There was insufficient recognition of the needs for safe satellite operations"),
]


def norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def page_texts(doc: str) -> dict:
    return {r["page"]: norm(r["text"]) for r in map(json.loads, open(ROOT / "data" / "processed" / "pages" / f"{doc}.jsonl", encoding="utf-8"))}


def main():
    src = P / "D2a_mission_factors.csv"
    backup = P / "D2a_mission_factors.owner_original.csv"
    if not backup.exists():
        shutil.copy(src, backup)
    owner = [r for r in csv.DictReader(open(backup, encoding="utf-8-sig")) if r["factor_code"].strip()]
    out, problems = [], []
    for r in owner:
        m, oc = r["mission"], r["factor_code"].strip()
        code = CODE_MAP[(m, oc)]
        role = ROLE_MAP[r["role"].strip().lower()]
        frag = re.split(r"\.\.\.|…", r["quote"].strip().strip('"').strip())
        # first continuous fragment with >= 5 words (else the longest fragment)
        long_enough = [f.strip() for f in frag if len(f.strip().split()) >= 5]
        quote = long_enough[0] if long_enough else max((f.strip() for f in frag), key=len)
        texts = page_texts(r["doc_id"])
        found = [p for p, t in texts.items() if norm(quote) in t]
        page = int(r["page"]) if r["page"].strip().isdigit() and int(r["page"]) in found else (found[0] if found else None)
        if page is None:
            problems.append(f"owner row {m} {oc}: quote not found")
            continue
        short = " ".join((r["factor_short"].strip() or r["note"].strip()).split()[:12])
        out.append([m, code, role, short, r["doc_id"], page, quote,
                    f"OWNER factor+quote; assistant mapped code {oc}->{code}, role {r['role'].strip()}->{role}"
                    + (f", page {r['page']}->{page}" if str(page) != r["page"].strip() else "")
                    + ("; quote cut at '...'" if "..." in r["quote"] or "…" in r["quote"] else "")])
    for m, code, role, short, doc, page, quote in ASSISTANT_ROWS:
        if norm(quote) not in page_texts(doc).get(page, ""):
            problems.append(f"assistant row {m} {code}: quote not on {doc} p.{page}")
            continue
        out.append([m, code, role, short, doc, page, quote, "ASSISTANT (Claude) from board statement; verified verbatim"])
    if problems:
        print("PROBLEMS:\n  " + "\n  ".join(problems))
        return 1
    order = json.loads((P / "PILOT.json").read_text(encoding="utf-8"))["missions"]
    out.sort(key=lambda r: order.index(r[0]))
    with open(src, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mission", "factor_code", "role", "factor_short", "doc_id", "page", "quote", "note"])
        w.writerows(out)
    meta = json.loads((P / "PILOT.json").read_text(encoding="utf-8"))
    meta["labels_by"] = "MIXED: owner (D2q for all 10 missions; D2a factors and quotes for Columbia, Genesis, SOHO, WIRE, "\
                        "Starliner) + assistant Claude (taxonomy codes/roles/page fixes for owner rows; D2a for Challenger, "\
                        "MCO, Ariane 501, Apollo 13, Hitomi). Not a human-only benchmark."
    meta["assistant_rows"] = sum(1 for r in out if r[7].startswith("ASSISTANT"))
    meta["owner_rows"] = sum(1 for r in out if r[7].startswith("OWNER"))
    (P / "PILOT.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"D2a written: {meta['owner_rows']} owner rows, {meta['assistant_rows']} assistant rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
