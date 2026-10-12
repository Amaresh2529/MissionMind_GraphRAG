# Field labelling guideline (held-out test sheet)

File to fill in: `evalutation/fixtures/field_test_sheet.csv` (opens in Excel; keep it UTF-8 CSV when saving).
Fill in only the `label` column, with exactly one of the four labels below.

Label each passage by **what the passage itself mainly does**, using its text. The report title and
section heading are context only: an analysis chapter can contain a passage that only retells
events, and that passage is `description`. Do not look up the map or the predicted field before
labelling.

| Label | Use when the passage mainly… | Examples |
|---|---|---|
| `description` | summarises the report, describes the mission, vehicle, systems, organisation or history, or tells **what happened and when** (chronology, timeline, crew, preparations) | Executive summary; "At 73 seconds the vehicle broke up"; description of the Solid Rocket Booster |
| `analysis` | investigates or explains **why**: evidence, tests, data analysis, findings, causes, contributing factors, organisational/management analysis, testimony used as evidence | "The O-ring resiliency is degraded at low temperature"; "The Board found that the units mismatch…"; numbered findings |
| `recommendations` | recommends, prescribes or lessons-learns: recommendations, corrective actions, actions before return to flight, forward-looking advice | "R1. The Board recommends that…"; lists of corrective actions |
| `other` | is not report content: title page, contents, member/staff lists or biographies, acknowledgements, administrative letters, references/endnotes, acronym lists, figure/table residue with no readable statement, OCR noise | "ENDNOTES FOR CHAPTER 3 …"; "Table of Contents"; "Ann Merwarth NASA/GSFC-retired…" |

Tie-breaks:
1. Mixed passage → the label covering most of its words.
2. Numbered findings ("F3.2-1 …") → `analysis`; numbered recommendations ("R3.2-1 …") → `recommendations`.
3. A history of earlier flights or anomalies used to explain the cause → `analysis`; neutral background history → `description`.
4. Unreadable / mostly garbled OCR → `other`.

Expected effort: about 30 seconds per passage (≈ 1 hour for 100). If unsure, write the best
label and add `?` in a new `note` column; do not leave the label empty.
