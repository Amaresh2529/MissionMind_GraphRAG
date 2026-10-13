# MissionMind benchmark — annotation guide

**Who annotates:** the project owner (annotator A) and a second person (annotator B) for the agreement subsets.
The assistant that builds the system must **not** fill any label: the benchmark would then measure the
system against its own author.

**Rules**
1. Record only what the investigation board itself states. Do not add your own opinion of the cause.
2. Do not look at any MissionMind system output, prediction file or draft field map while labelling.
3. Do not edit a sheet after scoring has started. Corrections go in a new versioned file, with a note.
4. Keep the sheets as UTF-8 CSV when saving from Excel.

Taxonomy: `causal_taxonomy.json`. The codes are summarised at the end of this guide. **Review the taxonomy first** (step 0). Once
annotation starts it is frozen.

## Order of work and effort

| Step | Sheet | What | Annotator A | Annotator B (agreement) |
|---|---|---|---|---|
| 0 | `causal_taxonomy.json` | Review and freeze the 22 codes; set `"status": "frozen"` | 1–2 h | — |
| 1 | `D2a_mission_factors.csv` | Board-stated causal factors of each of the 22 missions | 15–20 h | 6 missions (≈ 4 h) |
| 2 | `D2b_mission_pairs.csv` | Analogy grade for 231 mission pairs (uses step 1) | 5–7 h | 60 pairs (≈ 1.5 h) |
| 3 | `D1_passage_factors.csv` | Causal factors stated in 200 sampled passages | 10–14 h | 50 passages (≈ 3 h) |
| 1b | `D2q_query_descriptions.csv` | A 100–200-word description of each mishap **as first observed** (no board causes) | 3–4 h | — |
| 4 | `D3_questions.csv` | Write ≈ 105 questions with key points and evidence | 15–20 h | review 30 questions (≈ 2 h) |

Agreement subsets for annotator B: in D2a, the first 6 missions in alphabetical order; in D2b, `P001`–`P060`; in D1,
`E001`–`E050`. B works in a **copy** of the sheet named `*_B.csv`.

## Step 1 — D2a: mission causal factors

For each mission, read the report's executive summary and its cause/findings chapters (`where_to_look.md` lists the
page ranges). Add one row per causal factor the board states:

| Column | Content |
|---|---|
| `factor_code` | Taxonomy subcategory, e.g. `V1`. If one statement covers two codes, write two rows |
| `role` | `root` (root/primary/proximate cause), `contributing` (contributing, intermediate, significant factor), or `observation` (a deficiency noted but not said to cause the mishap) |
| `factor_short` | Up to 12 words in your own wording, e.g. "O-ring resiliency lost at low temperature" |
| `doc_id`, `page` | Where the board states it (PDF page number, as shown by the viewer) |
| `quote` | A short verbatim excerpt (≤ 30 words) |

Add or delete the empty rows as needed; every mission needs at least one `root` row. Typical: 3–10 rows per mission.

## Step 1b — D2q: query descriptions (main retrieval test queries)

For each mission, write 100–200 words describing the mishap as an investigator would know it in the first days:
the vehicle and mission phase, what was observed (telemetry, events, damage), and when. **Do not state the board's
causes, findings or recommendations**, and do not copy sentences from the report. These texts are the queries
of the main test (T1). A system that only matches words of the board's findings must not be rewarded.

## Step 2 — D2b: mission-pair analogy grade

For each pair, compare the two missions' factor rows from step 1 and give a grade:

| Grade | Meaning |
|---|---|
| 3 | Share a **root** cause subcategory **and** a similar mechanism (e.g. both: qualification tests did not cover flight conditions) |
| 2 | Share a subcategory where it is root or contributing in **both** missions |
| 1 | Share a subcategory only as an observation, or only at the top-level group (e.g. both "Management") |
| 0 | No shared causal factor |

Write the shared codes in `shared_codes` (e.g. `V1;M2`). Grade from the factor sheet, not from overall mission
similarity: two launch failures with unrelated causes get 0.

## Step 3 — D1: passage causal factors

For each passage, mark the causal factors **this passage states**, using its text only (the report and page are
context).

- `no_factor` = `x` if the passage states no cause or contributing factor (narrative, background, lists, OCR noise).
- `factors`: one entry per factor, separated by `;`, each `code|role|exact quote`. Example: `V1|root|the joint was
  never tested at the temperatures experienced`.
- The quote must be copied exactly from the passage text (it is checked automatically).

## Step 4 — D3: questions

Write about 105 questions a mishap investigator might ask. Each needs reference key points and evidence.

| `type` | Target count | Example |
|---|---|---|
| `single` (cause of one mission) | 40 | "What led to the loss of the Mars Climate Orbiter?" |
| `cross` (analogy across missions) | 35 | "Which other missions lost a vehicle because qualification testing did not reflect flight conditions?" |
| `lesson` (recommendations / lessons) | 15 | "What did boards recommend about independent review of heritage software?" |
| `unanswerable` (not covered by the corpus) | 15 | "What caused the loss of Mars Observer?" (no report in the corpus) |

| Column | Content |
|---|---|
| `missions` | Mission ids involved, separated by `;` |
| `key_points` | 2–5 short statements a correct answer must contain, separated by `;` |
| `evidence` | `doc_id:page` for each key point, separated by `;` |
| `answerable` | `yes` or `no` |
| `author` | Your initials |

Spread `single` questions over at least 15 missions. For `cross` questions, use the D2b grades ≥ 2 to find true
analogies; every mission listed must be supported by a factor row in D2a.

## Taxonomy codes (draft v0.1)

| Group | Codes |
|---|---|
| T Technical | T1 hardware design · T2 software/requirements · T3 manufacturing/workmanship · T4 interface/heritage mismatch · T5 environment beyond design · T6 component failure |
| V Verification | V1 testing/qualification · V2 analysis/modelling · V3 review/independent assessment |
| O Operations | O1 procedure · O2 configuration/parameter error · O3 anomaly response/contingency · O4 monitoring/telemetry |
| H Human factors | H1 decision/skill error · H2 training/qualification · H3 communication |
| M Management | M1 schedule/cost pressure · M2 risk acceptance/normalisation of deviance · M3 safety & mission assurance · M4 systems engineering/config. mgmt · M5 oversight/roles · M6 staffing/resources |

After each step, run `python scripts/check_annotations.py` (format and quote checks; it does **not** score any system).
