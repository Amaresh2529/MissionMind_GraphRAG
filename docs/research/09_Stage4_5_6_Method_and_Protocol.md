# MissionMind — Stages 4–6: Proposed Method, Experimental Protocol and Audit

Date: 2026-10-13. Branch `stage1-repair`. This document is written **before any benchmark label exists**. It fixes
the method, the comparisons, the metrics and the statistics in advance (pre-registration), so that no choice can be
made after seeing test results. Changes after labelling starts must be listed in §7 with date and reason.

## 1. Decisions taken on 2026-10-13 (defaults recommended in the Stage 3 report; the user asked to proceed)

| # | Decision | Reason |
|---|---|---|
| 1 | Faithful **B3** stays the key baseline. **B3-bal** (field-balanced RRF) is added as a secondary baseline | Stage 3 found B3's top-100 is 45% Disposition passages |
| 2 | The ISRO distractor reports are **not indexed** in the main experiments | They have no fields; including them would change only B1/B2 |
| 3 | T1 test queries are the **human-written D2q descriptions**; automatic dev queries never produce a reported number | The audit (A2) shows dev queries overlap their own reports |
| 4 | **B5 (LightRAG) is dropped** from the main study | Needs a new package download and many hours of LLM indexing on the 8 GB GPU. The proposal listed it as "if feasible". Can be re-opened |
| 5 | **B4** (Stage 1 system: vector search plus unverified free-text graph) is evaluated **at mission level only** if rebuilt on the full corpus | Its chunks carry no page provenance, so passage metrics are undefined. The rebuild costs about 3 h of LLM time (§6) |
| 6 | Generator, judge and extractor: local llama3 8B (Q4_0); all outputs cached, reported outputs come from the cache | Stages 1 and 3: the model is not reproducible across sessions |

## 2. Proposed method P (implemented: `src/extension/`)

1. **Evidence-anchored extraction** (`factor_extractor.py`). The LLM proposes causal factors for each Summary/Causes passage (≥ 20 words), each with:
   - a code from the 22-code taxonomy (`evalutation/benchmark/causal_taxonomy.json`);
   - a role (root / contributing / observation);
   - a verbatim quote.

   **Deterministic verification** keeps a factor only if:
   - the code is valid;
   - the role is valid;
   - the quote has at least 5 words and occurs in the passage (after normalising whitespace, case and quote marks).

   The exact character span of each quote is stored. Rejected proposals are kept with their reason.
2. **Factor graph** (`factor_graph.py`):
   - a per-mission profile of codes, each with its evidence;
   - an idf weight per code over missions: ln(N/df) + 1;
   - mission analogy = the idf-weighted Jaccard of code sets (Proposal v2, Sec. 9);
   - stored in Neo4j as `(:Mission)-[:HAS_FACTOR]->(:FactorCategory)` and `(:Passage)-[:STATES_FACTOR {quote, char span}]->(:FactorCategory)`.
3. **Graph channel** (`proposed.py`):
   - query factors are extracted from the query text, with quotes verified against the query;
   - missions are ranked by analogy;
   - the evidence passages of shared codes form a 7th ranked list, fused with B3's 6 lists by the same RRF (k = 60);
   - with no query factor, P falls back to B3 (recorded per query).
4. **Citation-constrained generation** (`grounded_generation.py`, `qa.py`):
   - B3's context plus a factor-graph analogy block;
   - citations are normalised (`norm_cite`, identical for all systems);
   - invalid citations are removed and uncited items dropped;
   - P **abstains** when no root cause and no precedent remains (QA: when no cited key point remains).

**Ablations:**
- **P-noverif:** rejected proposals with a valid code are also used.
- **P-nofields:** the whole-index hybrid plus the graph list.
- **P-graphonly:** missions ranked by analogy alone.
- **P-noidf:** unweighted Jaccard.
- **Raw vs enforced** generation (both stored).

## 3. Benchmark (human labels; kit in `evalutation/benchmark/`)

| Set | Content | Used for |
|---|---|---|
| D2a | Board-stated causal factors per mission (code, role, page, quote) | Passage relevance; sanity of D2b |
| D2q | 100–200-word query description per mission, without causes | T1 queries |
| D2b | Analogy grade 0–3 for all 231 mission pairs | T1 relevance |
| D1 | Causal factors in 200 sampled passages (seed 20261013) | RQ1 extraction |
| D3 | ≈ 105 questions (single / cross / lesson / unanswerable) with key points and evidence pages | Answer quality, abstention |

Agreement subsets for annotator B:
- D2a: 6 missions;
- D2b: 60 pairs (quadratic-weighted κ);
- D1: 50 passages (code-set Jaccard; κ on "has a factor").

Target: κ ≥ 0.6 on D2b; below that, D2b results are reported as low-agreement and the guide is revised before re-labelling.

## 4. Comparisons and metrics (fixed)

**Primary (one test):** P vs B3 on **mission nDCG@5** over the 22 D2q queries:
- two-sided paired sign-flip permutation test (exact for n ≤ 16, else 20,000 seeded flips);
- 95% bootstrap CI of the mean difference.

Gains are linear (grade 0–3); queries with no relevant mission are excluded (reported).

**Secondary (Holm-adjusted):**
- P and B3 against every other system and ablation (B1, B2, H-whole, SF-*, B3-bal, P-*) on mission nDCG@5 and passage NormRecall@100;
- the paper's metrics, passage NormRecall@100 and nDCG@100: a passage is relevant when it lies on a D2a evidence page of an analogous mission for a shared code;
- RQ1: verified vs unverified extraction, micro P/R/F1 on (passage, code) with bootstrap CIs;
- D3: key-point recall (LLM judge, yes/no per point), citation page precision, abstention accuracy;
- RQ5: judge vs human ratings on 40 blind-shuffled questions.

**Power note:** with 22 query missions, only large effects are detectable. A non-significant primary result is reported as such, not re-tested on other metrics.

## 5. Stage 6 audit (`scripts/audit.py`, independent of `src/bench`)

| Check | What it verifies |
|---|---|
| A1 | Same query ids for every system; clean git tree |
| A2 | No own-mission leakage; query/report 8-gram overlap flags copied queries |
| A3 | Every predicted passage's provenance (text = page slice) |
| A4 | Every citation in final answers maps to a corpus passage |
| A5 | Independent recomputation of nDCG@5 against the evaluator's per-query values |

Trial run on Stage 3 run A: PASS. A2 flagged all 19 automatic dev queries as copied (>20% own 8-gram overlap), as expected, which confirms they are unusable as test queries.

## 6. Status and remaining cost

| Item | State |
|---|---|
| Annotation kit (taxonomy draft, sheets, guide, checker) | Done (`429f43e`, D2q added in `906f080`) |
| P implementation, ablations, B3-bal, QA mode | Done, unit-tested |
| Corpus-wide extraction | Running; results in §8 |
| Stage 5 evaluators (retrieval, extraction, answers) and statistics | Done; refuse to run without complete human labels |
| Stage 6 audit | Done; trial PASS |
| B4 full-corpus rebuild | Not done: about 3 h of LLM time plus Stage 1 text extraction of 19 new documents (HTML unsupported by the Stage 1 loader) |
| Human labels D1, D2a, D2q, D2b, D3; taxonomy and field-map review | **Not started (human work)** |
| Final experiments, audit, paper results | Blocked by the labels |

## 7. Changes after pre-registration

| Date | Change | Reason |
|---|---|---|
| 2026-10-13 | P query codes = direct query factors ∪ verified factors of B3's top-20 passages; ablation P-noprf added | Direct query factors were empty for 12/19 dev queries (symptoms, not causes). Decided on dev queries, before any human label |
| 2026-10-13 | Ariane 501: official ESA copy (user-approved) replaces the MIT mirror; blank D1 and field-test sheets regenerated with the same seeds | Official provenance; the sheets were still blank |
| 2026-10-13 | B3-bal weights changed from size-proportional to √(field size), normalised to mean 1 | Owner's decision before any human label; the size-proportional version made the top-100 100% Causes (structural observation, no labels involved) |
| 2026-10-13 | Synthetic pseudo-labels and a full proof-of-concept run (`docs/research/10`) | Requested by the owner; all outputs stamped SYNTHETIC_LABELS_NOT_REPORTABLE |
| 2026-10-13 | Citation ids normalised identically for every system (`norm_cite`) | Some B3 citations were the copied chunk header ("[C19] mission=…"). Stage 3 counts (9 invalid) were computed without it and are not changed |

## 8. Development results (NOT reportable)

See `docs/research/10_Proof_of_Concept_Synthetic_Labels.md`.

## 9. Second-generation design (frozen 2026-10-13, before any run of it)

**Trigger:** the 10-mission pilot (`docs/research/11`) and two external reviews (Gemini, ChatGPT) of the project guide.
Everything below was written and committed **before** the new variants were run once. The 10 pilot missions have now
influenced the design, so the final paper reports every result twice:
- on all 22 missions;
- on the **12 missions not used in the pilot** (held-out subset, `summary_heldout_non_pilot_missions` in `evaluate.py`).

| Change | Specification (no tuning) | Status in the final study |
|---|---|---|
| **P2**: weighted graph channel | RRF weight of the graph list = 6 (the number of B3 lists), i.e. graph and text get equal total voice | Secondary system |
| **P2** generic-code filter | Expanded query codes present in ≥ 80% of mission profiles are dropped unless stated in the query (removes T4, in 19/22 profiles) | Part of P2 |
| P2-nofilter | P2 without the filter | Ablation |
| P2 generation | Prompt requires the specific failed component/process and how it led to the mishap; items that are only a category name are dropped and counted (`generic_dropped`) | Secondary generation system |
| Support check | (a) LLM yes/no: does the quote support the claimed factor (weak self-check); (b) **D4 human review sheet**: 100 accepted + 50 rejected factors, shuffled, verdict columns | RQ1 secondary measurement |
| Length/type bias diagnostic | `scripts/diagnose_bias.py` (label-free): Spearman ρ between a mission's top-5 frequency and its corpus size / profile size; top-5 rate full reports vs short documents | Reported for every run |
| Results by query document type | `summary_by_query_doctype` in `evaluate.py` | Reported |

**Unchanged:** the primary comparison stays **P vs B3 on nDCG@5** (pre-registered). It is not replaced by P2 or P-graphonly on the basis of pilot results. The baseline is described as a **controlled reproduction and adaptation** of Kim & Kim (2026), not an exact replication (generator, context size, fields and evaluation split differ; Section 3 of docs/research/08).

**Not adopted:** dropping the 3-field lists and fusing the graph only with B3-bal (suggested by one review). Choosing a combination because it scored well on the pilot would be tuning on evaluation data. P-graphonly and P2 already cover the "stronger graph" hypothesis.

## 10. Third round (frozen 2026-10-14, before any run of it)

**Trigger:** a second round of external reviews of the 27-page guide.

| Change | Specification | Status |
|---|---|---|
| **Two-step generation (P2-2step)** | Step 1: for each packed chunk, the LLM copies the single sentence that states a specific failure mechanism (or NONE); the sentence must be found verbatim in the chunk, else discarded. Step 2: the P2 prompt also receives these verified mechanism sentences keyed by chunk id. Same enforcement as P2 (uncited and category-only items dropped) | Secondary generation system |
| P2 and P2-2step in QA (D3) | Same specificity rule and generic-item enforcement as RCA drafting | Lets key-point recall measure the coverage cost of enforcement |
| Retention metric | Share of generated cause/factor items kept after enforcement (`retained_share`), reported next to key-point recall | Reported for P, P2, P2-2step |
| D4 scoring | `scripts/score_d4.py`: precision of accepted factors, share of rejected factors that were correct, agreement of the LLM support check with the human verdicts (Cohen's κ), false accepts/rejects | Reported for RQ1 |

**Unchanged:** the primary test remains **P vs B3, nDCG@5**. P2 and P2-2step are secondary. No system is promoted to "final method" because it scored highest on the pilot.

### Pre-specified framing of the final paper (written before any human-labelled result exists)

| Final outcome on the human benchmark | Claim allowed |
|---|---|
| P − B3 significant (primary), CI > 0 | "The causal-factor graph channel improves cross-mission analogy retrieval over the reproduced base method" |
| Primary not significant, CI includes 0 | "P performs on par with the base method" (equivalence is NOT claimed unless the CI lies within ±0.05). Secondary results (P2, graph-only, bias diagnostic, citation enforcement, abstention) are reported as **secondary/exploratory**, with their measured numbers only |
| Bias diagnostic: graph ρ near 0, text ρ > 0.4 again | "Text-based retrieval favours missions with long reports; the graph channel did not show this bias in our corpus" — not "unbiased" |
| Support check / D4 | Report measured precision; never "hallucination-free" |

## 11. Precedent-attributed hypotheses (owner's decision 2026-10-14; frozen before running)

**Trigger:** two-step answers presented a precedent's mechanism as the queried mission's cause (Apollo 13 oxygen tank
offered for Mars Climate Orbiter). The owner decided, following two external reviews: causes must be stated as
hypotheses attributed to a named precedent.

**Variant P2-2step-hyp** (secondary; P2-2step results remain unchanged and reported):

| Element | Specification |
|---|---|
| Output schema | Each cause/factor item: `statement`, `type` ∈ {established, analogy_hypothesis, insufficient_evidence}, `precedent_mission`, `evidence` (chunk ids) |
| Deterministic enforcement | `established` is allowed only if a cited chunk belongs to the queried mission. Under leave-one-mission-out this never happens in T1, so such items are **relabelled** `analogy_hypothesis` and counted. `precedent_mission` is set from the cited chunks' missions: the model's value if it matches one, else the mission of the first cited chunk (counted as corrected). Uncited and category-only items are dropped (as P2) |
| Rendering | The final text of every analogy item is rebuilt by code: `By analogy with <precedent mission>: <statement>`, so a precedent's mechanism can never appear as a bare claim about the queried mission |
| Abstention | If no item remains, `insufficient_evidence` (abstain) |
| Measures | Retention; relabelled `established`; corrected precedent attributions; share of items whose precedent is among the system's own top-5 missions (consistency); human-rated correctness and usefulness (D3 and ratings) |

**Benchmark-size risk (external review):** 22 query missions give low power. Results are reported with CIs, per-mission
values and effect sizes. Extending the benchmark with independently labelled missions is listed as future work.

