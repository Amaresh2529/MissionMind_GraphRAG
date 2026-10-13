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
