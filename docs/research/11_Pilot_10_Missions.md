# MissionMind — 10-Mission Pilot (mixed owner / AI-assisted labels)

Date: 2026-10-13. Branch `stage1-repair`. Labels: `evalutation/benchmark/pilot/` (commit `3a9de92`).

> **Status of these results.** This is a **pilot**: 10 query missions, low statistical power, draft field maps. The labels
> are **mixed**: written partly by the project owner and partly by the AI assistant (Claude), which also built the
> method under test (see §1). The results may be cited in the project submission **as a pilot with AI-assisted
> labels**. They are **not** a human benchmark and do not support claims of superiority. Fully human labels are
> planned before the IEEE submission.


> **Correction (2026-10-14).** §4 below says 21 of 43 of P's cause/factor items are category names. The automatic check in `docs/research/12` shows that **all 43** are: the hand count missed code-prefixed items such as "O1 Procedure deficient or not followed". Second-generation results (P2, bias diagnostic) are in `docs/research/12_Review_Driven_Improvements.md`.

## 1. Labels and their provenance

| Sheet | Content | Written by |
|---|---|---|
| D2q (queries) | 10 descriptions of each mishap as first observed, 93–100 words, no board causes | **Owner** (all 10) |
| D2a (causal factors), 5 missions: Columbia, Genesis, SOHO, WIRE, Starliner | 20 factors: selection, wording and verbatim quotes | **Owner**. The assistant mapped the owner's own codes to the 22 taxonomy codes, normalised roles (Proximate/Direct → root, Indirect → contributing), corrected 9 pages to PDF page numbers, and cut 10 quotes at "…" to one continuous fragment |
| D2a, 5 missions: Challenger, MCO, Ariane 501, Apollo 13, Hitomi | 21 factors with verbatim board quotes | **Assistant** (Claude), from the boards' cause statements; every quote verified against the page text |
| D2b (pair grades) | 45 pairs | **Derived** from D2a by the guide's rule (15 × 3, 16 × 2, 14 × 0) |

Each row's provenance is in its `note` column. The owner's original sheet is preserved (`D2a_mission_factors.owner_original.csv`), and so is the completion script (`scripts/pilot_complete_assistant.py`).

**Risk:** the assistant also designed the taxonomy and P, so the assistant-written labels may favour P. This is why these results cannot be used as evidence for P.

## 2. Runs (all audited)

| Run | Content | Audit |
|---|---|---|
| `runs/pilot_t1` (commit `3a9de92`, clean tree) | 17 retrieval systems × 10 owner queries | `pilot_audit_t1_r2`: **PASS**. 0 own-mission leaks; **0/10 queries copied from the reports** (8-gram check); 17,000 passages' provenance verified; **170/170 nDCG@5 values recomputed independently, all equal** |
| `runs/pilot_eval_t1_r2` | Metrics and statistics (`pilot_eval_t1` superseded: identical numbers, wrong provenance flag) | — |
| `runs/pilot_t1_generation` | RCA drafts for B0, B3 and P on the 10 queries | `pilot_generation_audit`: PASS; `pilot_generation_check`: PASS |

## 3. Retrieval results (mission level: 9 candidates per query; passage level: top 100)

| System | nDCG@5 | nDCG@10 | R@5 | MRR | NormRecall@100 |
|---|---|---|---|---|---|
| B1 BM25 | 0.644 | 0.831 | 0.535 | 0.833 | 0.022 |
| B2 dense (bge-m3) | 0.644 | 0.806 | 0.571 | 0.733 | 0.047 |
| H-whole | 0.658 | 0.826 | 0.557 | 0.850 | 0.030 |
| SF-summary-hybrid | 0.675 | 0.835 | 0.564 | 0.833 | 0.039 |
| SF-causes-hybrid | 0.642 | 0.828 | 0.515 | 0.900 | 0.039 |
| **B3** (base paper) | **0.648** | 0.800 | 0.580 | 0.733 | 0.019 |
| B3-bal (√ weights) | 0.642 | 0.828 | 0.515 | 0.900 | 0.035 |
| **P** (proposed) | **0.638** | 0.816 | 0.540 | 0.833 | 0.023 |
| P-noverif | 0.672 | 0.831 | 0.555 | 0.900 | 0.019 |
| P-nofields | 0.630 | 0.804 | 0.540 | 0.783 | 0.040 |
| **P-graphonly** | **0.713** | 0.860 | 0.598 | 0.883 | 0.056 |
| P-noidf | 0.638 | 0.816 | 0.540 | 0.833 | 0.023 |
| P-noprf | 0.638 | 0.811 | 0.555 | 0.783 | 0.022 |

**Primary comparison (pre-registered): P vs B3 on nDCG@5: −0.010**
- 95% bootstrap CI [−0.068, +0.049];
- exact permutation p = 0.78, n = 10;
- **no difference detected.**

**Secondary comparisons:** none of 62 is significant after Holm correction.

**Exploratory observation (not a pre-registered test):** the factor-graph channel alone (P-graphonly) has the highest nDCG@5.
- vs P: +0.076, 95% CI [+0.011, +0.146], permutation p = 0.06, Holm-adjusted p = 1.0;
- per mission it is clearly better on Genesis (0.93 vs 0.61 for B3), Challenger (0.94 vs 0.70), WIRE (0.82 vs 0.54) and Ariane 501 (0.69 vs 0.44);
- it is worse on MCO, SOHO and Hitomi.

This suggests that fusing the graph list as 1 of 7 RRF lists dilutes it. The hypothesis must be tested on the full human benchmark, **not** adopted from this pilot.

| Query mission | Relevant (grade ≥ 2) | B3 | P | P-graphonly | B1 |
|---|---|---|---|---|---|
| Apollo 13 | 7 | 0.655 | 0.616 | 0.586 | 0.684 |
| Ariane 501 | 6 | 0.438 | 0.583 | 0.690 | 0.382 |
| Genesis | 8 | 0.612 | 0.617 | 0.929 | 0.612 |
| Hitomi | 8 | 0.850 | 0.841 | 0.783 | 0.850 |
| Mars Climate Orbiter | 4 | 0.794 | 0.635 | 0.635 | 0.724 |
| SOHO | 5 | 0.496 | 0.382 | 0.382 | 0.672 |
| Starliner CFT | 7 | 0.830 | 0.723 | 0.812 | 0.515 |
| Columbia | 4 | 0.559 | 0.559 | 0.559 | 0.538 |
| Challenger | 7 | 0.704 | 0.750 | 0.936 | 0.704 |
| WIRE | 6 | 0.538 | 0.669 | 0.818 | 0.756 |

## 4. Generation (RCA drafts, 10 queries)

| System | Valid JSON | Items | Citations | Invalid citations | Uncited items | Items that are only a taxonomy category name |
|---|---|---|---|---|---|---|
| B0 (no documents) | 10/10 | 57 | 0 | 0 | 57 | — |
| B3 | 10/10 | 65 | 141 | 0 | 7 | 0 / 31 causes+factors |
| P (citation-enforced) | 10/10 | 86 | 379 | 0 | 0 | **21 / 43** |

P enforces citations (0 uncited items; 3 items dropped, 2 citations removed), but **about half of its cause and factor items repeat taxonomy category names** ("Procedure deficient or not followed") rather than specific mechanisms. The graph block in the prompt appears to prime the model to copy category labels.

Leave-one-mission-out means neither system can name the query mission's own cause (e.g. MCO's unit mismatch); the drafts are hypotheses from precedents. **Citation validity is not correctness.** Answer quality needs human rating.

## 5. Limitations

- **Mixed labels:** about half of D2a is written by the AI assistant that built P.
- **Sample size:** n = 10 queries, so only large effects are detectable.
- **Draft field maps:** not yet human-reviewed.
- **Local models:** 8B Q4 generator and judge.
- **Grade distribution:** the derived grades contain no grade-1 pairs. Grade 1 requires a shared code that is only an `observation`, and no pilot factor uses that role. So the grades are effectively 0 / 2 / 3.
- **Generic query codes:** P's expanded query codes are dominated by generic codes (O1, T1, T5 appear for most queries), which limits the graph channel's discrimination.

## 6. What the pilot changes for the full study (to decide **before** human labelling)

1. Whether to add **P-graphonly** (or a weighted graph list) as a pre-registered **secondary** system. It must not replace P as the primary method on the basis of this pilot.
2. A generation prompt that asks for **specific mechanisms**, not category names. This is a design change, to be made before the D3 labels exist.
3. Down-weighting or removing generic codes (O1, T1, T5) in query expansion, e.g. idf over query-code frequency.
