# MissionMind — Review-Driven Improvements (second-generation design)

Date: 2026-10-13/14. Branch `stage1-repair`. Design frozen in commit `e999e42` **before** any of these runs.
All retrieval results use the 10-mission pilot with **AI-assisted labels** (see `docs/research/11`); they are exploratory.

## 1. External reviews and what was adopted

The project guide was reviewed by Gemini and ChatGPT. Their suggestions and the decisions:

| Suggestion | Decision |
|---|---|
| Graph signal diluted as 1 of 7 RRF lists (both) | **Adopted**: P2 gives the graph list the same total weight as the six text lists (weight 6, pre-specified) |
| Generic categories in queries and answers (both) | **Adopted**: generic-code filter (codes in ≥ 80% of missions; removes T4 only) and a specific-mechanism generation prompt with enforcement |
| Quote existence ≠ causal support (ChatGPT) | **Adopted**: LLM support check over all accepted factors + D4 human review sheet (100 accepted, 50 rejected) |
| Control for document length/type (ChatGPT) | **Adopted**: label-free bias diagnostic; results by query document type |
| Freeze design before final evaluation (ChatGPT) | **Adopted**: protocol §9; results also reported on the 12 missions not used in the pilot |
| Position as "controlled reproduction and adaptation" (ChatGPT) | **Adopted** |
| Extraction P/R/F1 vs human D1 (Gemini) | Already implemented (`scripts/evaluate_extraction.py`); needs D1 labels |
| Complete human labelling (both) | Owner, after the project submission |
| Drop the 3-field lists; fuse the graph only with B3-bal (Gemini) | **Not adopted**: it would choose a design because it scored well on the pilot (tuning on evaluation data) |

Two statements in the Gemini review were corrected:
- **"Zero hallucinations":** verification proves only that a quote exists, not that it supports the cause.
- **"Proves the core theory":** the graph-only advantage is not significant.

## 2. Retrieval: second-generation variants (pilot, 10 queries)

| System | nDCG@5 | nDCG@10 | Recall@5 | MRR | NormRecall@100 |
|---|---|---|---|---|---|
| B3 (base paper) | 0.648 | 0.800 | 0.580 | 0.733 | 0.019 |
| P (primary proposed) | 0.638 | 0.816 | 0.540 | 0.833 | 0.023 |
| **P2** (weighted graph + filter) | **0.678** | 0.847 | 0.545 | 0.883 | 0.055 |
| P2-nofilter | 0.677 | 0.848 | 0.534 | 0.883 | 0.047 |
| P-graphonly | 0.713 | 0.860 | 0.598 | 0.883 | 0.056 |

Run: `runs/pilot_t1_v2` → `pilot_eval_t1_v2`. Audit `pilot_audit_t1_v2`: **PASS**. Systems also present in the first pilot run give identical numbers.

| Comparison (nDCG@5) | Difference | 95% CI | p (permutation) | p (Holm) |
|---|---|---|---|---|
| P2 − B3 | +0.030 | [−0.091, +0.148] | 0.65 | 1.0 |
| P2 − P | +0.040 | [−0.035, +0.120] | 0.37 | 1.0 |
| P-graphonly − P | +0.076 | [+0.011, +0.146] | 0.06 | 1.0 |

- The weighting moves P towards the graph-only result, as expected.
- **None of the differences is significant on 10 queries.**
- The generic filter has almost no effect: it removes only T4.
- The primary comparison (P vs B3) is unchanged and remains the pre-registered test.

## 3. Length / document-type bias (label-free, `runs/pilot_bias_t1_v2`)

Spearman correlation between how often a mission appears in other queries' top 5 and its size in the corpus:

| System | ρ vs indexed passages | ρ vs factor-profile size | Top-5 rate: full reports | Top-5 rate: short documents |
|---|---|---|---|---|
| B1 BM25 | 0.62 | 0.57 | 0.34 | 0.09 |
| B2 dense | 0.44 | 0.28 | 0.34 | 0.09 |
| B3 | 0.56 | 0.43 | 0.37 | 0.06 |
| P | 0.45 | 0.34 | 0.36 | 0.07 |
| P2 | 0.22 | 0.07 | 0.27 | 0.18 |
| P-graphonly | **0.03** | **−0.05** | 0.21 | 0.25 |

**Correction of an earlier statement.** `docs/research/10` §5.3 and the project guide said "the analogy score favours long reports". Pairwise analogy scores *are* highest between long reports. But in the **rankings**, the text-based systems are the ones strongly biased towards long reports (they rarely rank a short document's mission in the top 5). The graph-only channel shows no length bias, and P2 reduces it. Part of the text systems' scores may therefore reflect report length rather than causal similarity. That is a hypothesis the human-labelled benchmark must test with the stratified results (`summary_by_query_doctype`).

## 4. Generation: specific mechanisms (10 pilot queries)

| System | Cause/factor items proposed by the model | Only a category name | Kept after enforcement |
|---|---|---|---|
| B3 | 31 | 0 | 31 (no enforcement) |
| P | 43 | **43 (100%)** | 43 (P keeps generic items) |
| **P2** | 41 | 28 (68%) | **12, all specific** |

**Correction of an earlier figure.** The pilot report and guide said 21 of 43 P items were category names. The automatic check (`grounded_generation.is_generic`) shows that **all 43** are category names. The earlier hand count missed items prefixed with a code ("O1 Procedure deficient or not followed").

P2's prompt alone reduces generic items only partly (68%). The enforcement removes the rest, leaving 12 specific mechanisms such as "Frangible joint on one of the forward side fairing rails did not fracture" (Glory precedent) or "Foreign Object Debris (FOD) introduction to the E15 LO2 turbopump" (Antares precedent). The cost is shorter answers: for some queries no root cause survives (for example MCO), while precedents remain. B3's answers name mechanisms without enforcement.

Run `runs/pilot_t1_generation_v2`; audit `pilot_generation_audit_v2`: **PASS**.

## 5. Support check of verified factors

Run `runs/stage4_support_check` (`scripts/support_check.py`): the local LLM judged **1,712 of 2,038** accepted factors
(**84%**) as supported by their own quote and 326 (16%) as not supported (0 unparsed). This means quote verification
alone lets through a measurable share of factors whose quote exists but does not clearly support the claimed cause.
This is exactly the gap the reviews pointed out.

Caveat: the checker is the same model family as the extractor, so this is a weak self-check. The **D4 human sheet**
(`evalutation/benchmark/D4_factor_review.csv`; 100 accepted + 50 rejected factors, shuffled, key in `.key.json`) is the
real measurement: precision of accepted factors, and how many rejected factors were in fact correct. A variant
that builds the graph only from support-confirmed factors is a candidate for the full study and must be pre-registered
before the human labels are used.

## 6. What this means for the full study

1. P2 is a pre-registered **secondary** system. The primary comparison stays P vs B3.
2. Reported results must include the 12 held-out missions and the document-type strata, because text-based systems are length-biased.
3. Generation needs either a stronger generator or a two-step design (extract the mechanism from the cited chunk, then write). Prompting alone did not remove generic answers.
