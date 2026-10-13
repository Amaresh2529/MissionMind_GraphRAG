# 10-mission pilot — what to fill (about 4 hours)

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
