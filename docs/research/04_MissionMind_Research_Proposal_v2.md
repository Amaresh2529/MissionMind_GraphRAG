# MissionMind — Research Proposal v2

Oct 12, 2026 · @yash

Supersedes the v1 proposal of the same date, which is preserved unchanged. Changes follow from the literature verification in *MissionMind — Literature Verification, Novelty and Publication Strategy*. **Status: proposal only. No experiment has been run, and the project is not experimentally validated or publication-ready.**

## 1. Title and positioning

**MissionMind: A Benchmark and Evidence-Anchored Graph-Augmented Retrieval Study for Cross-Mission Causal Analogy in Spaceflight Mishap Investigation Reports**

The title changed from v1. The v1 title led with "Evidence-Anchored Causal-Factor Graphs" as if the method were the main contribution. Verification showed that provenance-anchored LLM extraction (AEVS \[10\]) and cross-accident causal knowledge graphs (Xiang *et al.* \[9\]) already exist. v2 therefore leads with the parts that are not covered by reviewed work: the **task** (cross-mission causal analogy retrieval) and the **benchmark**. The method is presented as an adaptation evaluated rigorously.

## 2. Abstract

Spaceflight mishap investigation reports record why missions failed. They are few, very long, unstructured, and written by different agencies across decades, so causally similar failures in separate missions are rarely connected. Knowledge-graph retrieval-augmented generation (KG-RAG) has been applied to aviation fault diagnosis, aviation accident causation and maritime accident root-cause analysis \[1\], \[3\], \[9\], \[11\]. Provenance-anchored LLM extraction has been demonstrated on sentence-level benchmarks \[10\]. To our knowledge, within the search scope documented in the verification report, no work defines or evaluates *cross-mission causal analogy retrieval* against human judgement, and none applies these techniques to spaceflight mishap reports.

We propose (i) a reproducible corpus of 25–35 public spaceflight mishap reports, and a human-annotated benchmark of page-anchored causal factors, graded mission-pair analogy judgements and a categorised question set with unanswerable items; (ii) an adapted pipeline that extends anchor-and-verify extraction to whole reports with page provenance, and adds a typed causal-factor graph channel to the multi-field hybrid retrieval of our 2026 IEEE base paper \[1\]; and (iii) a controlled study against LLM-only, lexical, dense, multi-field hybrid, unverified-graph and published GraphRAG baselines. The study uses ablations, inter-annotator agreement, paired significance tests and validation of metadata proxies and LLM judges against human labels.

*No results exist yet.* Hypotheses and pre-registered primary comparisons are stated in Section 13. A null result for the graph channel will be reported as such.

## 3. Introduction and motivation

A mishap investigation is most useful when its lessons reach the next mission. Analysts ask "which earlier failures had the same causal pattern as this one?" Answering that requires reading many long reports. Ariane 5 Flight 501 (1996) and Mars Climate Orbiter (1999), for example, were both traced to software and interface assumptions that verification did not catch. Their reports share almost no vocabulary, and they differ about thirty-fold in length from Columbia's CAIB Volume I (about 6,000 vs about 175,000 words in our extracted text).

Recent KG-RAG work in related domains shows the ingredients exist:

- Aviation causation graphs from NTSB reports \[9\]
- Avionics diagnosis over long multimodal datasheets \[3\]
- Hybrid graph + vector + BM25 retrieval for aircraft troubleshooting \[11\]
- Precedent retrieval over maritime tribunal records \[1\]
- Provenance-anchored extraction \[10\]

The same literature also shows the risks:

- LLM summaries of accident reports hallucinate, and standard metrics do not detect it \[5\].
- Graph RAG helps corpus-wide questions but not necessarily fine-grained ones \[12\].
- LLM-built graphs can propagate extraction errors \[14\].

What is missing is evidence about whether these ingredients actually help the analyst's core question in the spaceflight setting, and a benchmark on which that can be measured. MissionMind is designed to provide that evidence, and to report it whichever way it falls.

## 4. Problem statement and task definition

Given a corpus D of N long, unstructured, multi-agency mishap reports, MissionMind addresses two tasks. Both are defined so they can be scored against human labels.

**T1. Cross-mission causal analogy retrieval.** For a query mission m\_q, rank the other N−1 missions by causal analogy. Two missions are analogous when at least one causal factor at the same taxonomy level played a root or contributing role in both, *as stated by the respective boards*. Relevance is graded by humans:

- 0 = no shared causal factor
- 1 = shared factor at L1 only
- 2 = shared factor at L2 with a comparable mechanism

Each ranked mission must be accompanied by evidence passages, with pages, from both reports.

**T2. Evidence-cited question answering.** For a question q in categories C1–C5 (Section 14), return an answer whose every factual claim cites a passage `[doc:page]` that supports it. If D does not support an answer, abstain.

Three properties make these tasks hard, and the evaluation must demonstrate each:

1. **Lexical divergence.** The same causal factor is described in unrelated words across agencies and eras.
2. **Structural heterogeneity.** There are no shared report fields, so field-aware retrieval \[1\] needs fields recovered from structure.
3. **Verifiability.** An uncited causal link is unacceptable in a safety context, so provenance must survive from extraction to answer.

## 5. Literature review

The closest prior work splits into three groups:

- Accident-report RAG and KGs: \[1\], \[2\], \[5\], \[9\], \[29\].
- Aerospace KG-RAG for diagnosis: \[3\], \[6\], \[11\], \[12\].
- Methods for grounded or uncertainty-aware graph construction and retrieval: \[8\], \[10\], \[14\].

The access level column shows how much could be verified. "n/s" means not stated in the material read. "n/a" means the full text was not accessible.

| Ref | Problem | Domain and data | Method | Evaluation | Limitations / future work (only if stated) | Relationship to MissionMind | Access |
| --- | --- | --- | --- | --- | --- | --- | --- |
| \[1\] Kim & Kim, IEEE CASE 2026 | Precedent retrieval and RCA drafting | Maritime; 13,329 KMST tribunal reports → 37,007 field chunks | Per-field BM25 + bge-m3, RRF (k = 60); Qwen3-80B generator | Proxy NormRecall@100 0.18 → 0.55; LLM judge 3.34 → 3.72; no significance test | Proxy labels; rule-based tags; judge bias. Future: regulations, graph-based reasoning | **Base paper**; method = baseline B3; its future work = our graph channel; its limitations = our RQ4 | Full text |
| \[2\] Sanyaolu & Josyula, IEEE ICSC 2026 | KG from safety narratives | Aviation; 6,193 NTSB reports | Schema-constrained LLM extraction; GCN severity prediction | Extraction F1 0.87 across 8 categories; 82.5% severity accuracy | Provenance tracking and contradiction heuristics used as mitigations | Schema-guided extraction design | Abstract |
| \[3\] An *et al.*, IEEE TR 2026 (ADRAG) | Diagnosis from multimodal datasheets | Avionics; "specialized avionics dataset" (size n/a) | Hierarchical semantic tree guides KG; multi-agent tree + graph querying; adaptive fallback | Outperforms RAG baselines (numbers n/a) | n/a | Closest aerospace KG-RAG; supports structure-aware parsing | Abstract |
| \[4\] Fu *et al.*, IEEE TR 2026 | Adaptive KG retrieval for maintenance | Port equipment O&M + HotpotQA | Topic-inferred context; dynamic-programming traversal; multi-objective node selection | Beats RAG baselines; robust under degraded KG | n/a | Optional degraded-graph robustness test | Abstract |
| \[5\] Yuan *et al.*, IEEE TETCI 2026 (early access) | Hallucination in LLM summaries of accident reports | Maritime accident reports; MARHAS dataset | Hallucination taxonomy; multi-LLM analysis; factuality benchmarking | Standard metrics do not correlate with hallucination; full-document context crucial | n/a | Justifies human and claim-level evaluation; full-document baseline | Abstract |
| \[6\] Liu *et al.*, IEEE TII 2024 | Fault localisation in assembly testing | Aviation assembly (industrial) | KG embedding → LLM prefix-tuning; retrieval-augmented fusion | 98.5% accuracy | n/a | Different task; cited for completeness | Abstract |
| \[7\] Gao *et al.*, IEEE TASE 2025 | Representing aviation terms for report retrieval | Aviation safety reports; more than 500k auto-generated pairs | Semantic encoding algorithm for domain terms | Classification and retrieval with revised metrics | n/a | Report similarity exists with *automatic* labels; ours are human, causal. Embedder ablation | Abstract |
| \[8\] Qi *et al.*, IEEE TKDE 2026 (DUAL-Know) | Safe GraphRAG in high-stakes QA | Anesthesiology QA | Description augmentation; uncertainty-aware path ranking; conflict arbitration | Beats strong baselines | n/a | Uncertainty-aware GraphRAG exists; abstention is evaluation only | Abstract |
| \[9\] Xiang *et al.*, *Aerospace* 2026 | Causation extraction and cross-accident chains | NTSB Part 121, 2000 onward; 343 (abstract) / 348 (text) reports | DeepSeek-V3.1 + RAG + prompts; causation schema; causation KG; risk indicators | Manual check of 50 reports: \~95% causation and >98% relation accuracy; no recall, IAA or baselines | Future: finer schema; add source reports to nodes and edges; more reports | **Largest overlap**; motivates provenance and human relevance labels | Full text |
| \[10\] Yang *et al.*, *Computers* 2026 (AEVS) | LLM triple hallucination | WebNLG, REBEL, Wiki-NRE | Anchor discovery → grounded extraction → restoration verification → supplement | Beats trained and LLM baselines; 2.83–4.28 LLM calls per sample | Sentence or passage level only. Future: document-level extraction, RAG integration, calibration | Adopted as extraction baseline; we extend it to document level with pages | Full text (sections) |
| \[11\] Xie *et al.*, *Sci. Rep.* 2025 | Aircraft troubleshooting | Aircraft maintenance (size n/a) | KG + vector + BM25 hybrid; agent assistant | ≥ +4% F1; >7% fewer hallucinations | n/a | Hybrid graph fusion is established | Abstract |
| \[12\] Ai *et al.*, arXiv 2025 (KEO), preprint | KG-RAG for maintenance QA | Aviation OMIn dataset | KG integrated into RAG; local LLMs, LLM judges | KG helps global sensemaking; chunk RAG better for fine-grained tasks | n/a | Independent support for H3 | Abstract |
| \[13\] Andrade & Walsh, NASA presentation 2022 | Knowledge access in safety reports | Aerial wildfire mishap reports | Topic modelling; fine-tuned NER for FMEA fields (MIKA) | n/s | n/s | NASA-side NLP on mishap reports | Abstract |
| \[14\] Wang *et al.*, IEEE ICDE 2026 (AGRAG) | Hallucination in LLM-built graphs | General benchmarks | Statistics-based graph construction; MCMI reasoning subgraphs | Benchmarks | n/a | Motivates verified construction | Abstract |

## 6. Research gap

Within the documented search scope, no reviewed work (i) defines and evaluates cross-case *causal analogy* retrieval against human judgement, or (ii) studies KG-RAG on spaceflight mishap reports. Several adjacent capabilities are established and are therefore not claimed as gaps.

| Gap (claimed, scoped) | Closest work and why it does not close the gap |
| --- | --- |
| G1. No human-judged benchmark for cross-case causal analogy | \[1\] evaluates precedent retrieval with a metadata proxy; \[7\] uses automatically generated similarity pairs; \[9\] analyses causal chains in aggregate without query-time retrieval or relevance labels |
| G2. Graph-based reasoning over precedents is untested against field-aware hybrid retrieval | Named as future work in \[1\]. \[11\] fuses graph + BM25 + vector, but for troubleshooting with no field-aware comparison |
| G3. Provenance-anchored extraction has not been carried to document level with page provenance through retrieval | \[10\] is sentence or passage level and lists document-level extraction and RAG integration as future work. \[9\] lists linking source reports to graph elements as future work |
| G4. No study of KG-RAG on long, heterogeneous, multi-agency spaceflight reports | \[2\], \[9\]: one agency (NTSB) with fixed sections; \[1\]: one tribunal; \[3\]: avionics datasheets |
| G5. Unknown validity of cheap proxies and LLM judges for this task | \[1\] states proxy and judge bias as limitations; \[5\] shows standard metrics miss hallucination in accident-report summaries |

**No longer claimed (changed from v1):**

- "Evidence-anchored graph construction" as a novel method (covered by \[10\]).
- "Cross-mission causal graphs" as new (covered in aviation by \[9\]).
- Uncertainty-aware retrieval as a contribution (covered by \[8\]).

The remaining residual risk is unsearched databases; see the verification report, Section 4.

## 7. Objectives and research questions

**Objectives**

1. **O1 Corpus.** 25–35 public spaceflight mishap reports (minimum usable: 20), with a manifest (URL, version, SHA-256, licence), page provenance and recovered section fields.
2. **O2 Benchmark.** About 350 page-anchored causal-factor passages (D1); graded analogy labels for all mission pairs (D2); about 150 categorised questions with evidence pages, including 20 unanswerable ones (D3). A second annotator labels at least 25% of items, and agreement is reported.
3. **O3 Pipeline.** Document-level anchor-and-verify causal extraction with page provenance; a typed causal-factor graph; graph-augmented multi-field hybrid retrieval; citation-constrained generation with abstention.
4. **O4 Study.** Pre-registered comparisons against baselines B0–B6, ablations, significance tests, and validation of proxies and LLM judges.

**Research questions**

| ID | Question | Primary evidence |
| --- | --- | --- |
| RQ1 | Does document-level anchor-and-verify extraction with page provenance raise causal-extraction precision over (a) unverified LLM extraction and (b) a sentence-level AEVS-style baseline \[10\] on long reports, and at what recall cost? | P/R/F1 vs D1 test |
| RQ2 | Does adding a verified causal-factor graph channel to the base paper's multi-field hybrid retrieval \[1\] improve cross-mission causal analogy retrieval? | Mission-level nDCG@5 on D2 (primary) |
| RQ3 | For which question categories does the graph help, hurt, or make no difference, and does it change citation precision and abstention? | Per-category results on D3 |
| RQ4 | How well do the base paper's metadata proxy and an LLM judge agree with human labels in this domain? | Spearman ρ and Cohen's κ vs human labels |

Changed from v1: RQ1 now includes the AEVS-style baseline, and RQ3 adds citation precision and abstention. Each RQ maps to exactly one primary table in the planned paper.

## 8. Base paper selection and justification

The base paper is unchanged from v1: S. Kim and S. Kim, "Multi-Field Hybrid Retrieval-Augmented Generation for Maritime Accident Root Cause Analysis," *2026 IEEE 22nd Int. Conf. Automation Science and Engineering (CASE)*, pp. 238–243, doi: 10.1109/CASE69030.2026.11704480. It was verified through Crossref and the IEEE DOI, and the full text was read on arXiv (2606.13249, CC BY 4.0).

**Why not one of the six IEEE journal papers.** Each was checked as a candidate base paper:

| Candidate | Reason it is not the base |
| --- | --- |
| \[3\] ADRAG (TR 2026) | Different task (single-case diagnosis from datasheets); full text not accessible, so its method cannot be reimplemented faithfully |
| \[4\] ContextKG-RAG (TR 2026) | Maintenance QA, not accident reports; full text not accessible |
| \[5\] To Err Are LLMs (TETCI 2026) | Summarisation and hallucination profiling, not retrieval; early access |
| \[6\], \[7\], \[8\] | Different task or domain; abstract only |

&#91;1\] remains the only verified 2026 IEEE paper that (a) addresses retrieval over official accident investigation reports, (b) is fully readable, (c) states graph-based reasoning as future work, and (d) defines a method we can reimplement as a fair, strong baseline (B3).

**Secondary anchors:**

- &#91;9\] is the closest causal-KG work, used to position against.
- &#91;10\] is the closest extraction method, used as a baseline.
- &#91;3\] is the closest aerospace KG-RAG work in an IEEE journal, cited as related.

## 9. Current project status (from the audit of commit `5d0219e`)

Nothing in this revision changes the repository. All audit findings remain valid. The project has working ingestion, broken query and evaluation layers, and no recorded experiment.

| Area | Status | Evidence |
| --- | --- | --- |
| PDF extraction + OCR fallback; 250-word chunking | Implemented; output exists (7 docs, 2,175 chunks) | Verified on disk |
| NER gate | Implemented; passes 13 of 2,175 chunks (0.6%), so 99.4% fall to the LLM fallback; case-sensitive gazetteer | Measured offline |
| Graph construction (Neo4j) | Implemented, never verified by a recorded run; `MERGE` by raw string creates spurious cross-mission links | Code review + offline check |
| Query layer (`src/graph/retriever.py`) | **Broken**: imports a `GraphRAGRetriever` class that no longer exists | Code review |
| Evaluation runner (`run_eval.py`) | **Broken**: imports a non-existent `extract_failure_data`; placeholder test data | Code review |
| Corpus | 5 failure documents (3 NASA, 2 ESA) + 2 ISRO annual reports. The ExoMars file is a journal article, not the ESA inquiry report; no ISRO failure report | Verified on disk |
| Text processing | Ligatures destroyed by ASCII stripping; structure and page numbers lost; Challenger OCR noise undetected | Verified on disk |
| Experimental results | **None** | No result files, logs or graph exports |

The v1 audit document holds the full evidence, with file and line references.

## 10. Methodology

Every component is kept only if it has a testable hypothesis and a defined evaluation. Two v1 components are downgraded: "uncertainty estimation" is now abstention-only, and verification is now an adapted method rather than a novel one. Two optional robustness checks are added.

| Component | Status vs literature | Hypothesis it serves | Implementation cost (estimate) | How it is evaluated | Decision |
| --- | --- | --- | --- | --- | --- |
| M1 Corpus + manifest | Established practice | Prerequisite for reproducibility | Medium: 15–20 h search and verification | Manifest completeness; checksums | **Keep** |
| M2 Structure-aware parsing (NFKC, headings, pages, pseudo-fields) | Adapted from \[1\] (fields) and \[3\] (document structure) | H2/H3: field recovery enables field-aware retrieval on unstructured reports | Medium | Pseudo-field accuracy on 100 sections (target ≥ 90%); OCR character error rate on sampled pages; ablation "−fields" | **Keep** |
| M3 Typed causal schema (Mission, Event, Subsystem, Phase, CausalFactor L1/L2, Recommendation, Passage) | Adapted from causation schemas \[9\], HFACS \[26\], STAMP \[27\] and spacecraft subsystem categories \[25\] | H1, H2: typed shared factors enable analogy | Low–medium; frozen before test labels | Annotator agreement on L1/L2 | **Keep** (supervisor sign-off) |
| M4 Document-level anchor-and-verify extraction with page provenance | **Adapted from AEVS \[10\]**; extends to whole reports and pages (its stated future work) | H1: precision gain over unverified extraction, with quantified recall cost | Medium–high: about 3–5 LLM calls per section (AEVS reports 2.83–4.28 per sample) | RQ1 vs unverified and AEVS-style sentence-level baselines | **Keep, as adapted** |
| M5 Canonicalisation (merge by taxonomy ID, not string) | Established | Removes the spurious links found in the audit | Low | Duplicate-node rate; ablation | **Keep** |
| M6 Multi-field hybrid retrieval (BM25 + bge-m3, RRF) | Established \[1\], \[17\], \[19\] | Baseline strength | Low | B3 | **Keep as baseline** |
| M7 Causal-factor graph channel (idf-weighted factor overlap; evidence-passage expansion) | Adapted; answers \[1\]'s future work; related to \[11\] | **H2** (primary), H3 | Medium | RQ2 analogy nDCG@5; RQ3 per category | **Keep: core test** |
| M8 Citation-constrained generation + post-hoc citation check (NLI) | Adapted (claim-level checking \[21\]) | H4: fewer unsupported claims | Low–medium | Citation precision and recall; claim support rate | **Keep** |
| M9 Abstention when evidence is insufficient | Established (negative rejection \[24\]); uncertainty-aware GraphRAG exists \[8\] | H4 | Low | Correct and false abstention on D3 category C5 | **Keep as evaluation only; no novelty claim** |
| M10 Calibrated uncertainty estimation | Covered by \[8\], \[10\] (future work) | — | High | — | **Drop** (out of scope) |
| R1 Degraded-graph robustness (randomly drop 10/30/50% of verified edges) | Idea from \[4\] | Graph benefit degrades gracefully | Low | Analogy nDCG@5 vs drop rate | **Optional** |
| R2 Full-document long-context baseline on short reports only | Motivated by \[5\] | Retrieval vs full-context reading | Low, but limited by 8 GB VRAM and context length | Key-point recall on the subset of reports under about 24k tokens | **Optional, subset only** |

**Analogy scoring (M7).** F\_i is the set of verified L2 factors of mission m\_i, and idf(f) = log(N / n\_f), where n\_f is the number of missions whose reports cite factor f. The final mission score fuses this with the best passage-level dense similarity, using a weight λ tuned on dev missions only:

```latex
\mathrm{analogy}(m_i,m_j)=\frac{\sum_{f\in F_i\cap F_j}\mathrm{idf}(f)}{\sum_{f\in F_i\cup F_j}\mathrm{idf}(f)},\qquad \mathrm{RRF}(p)=\sum_{r\in R}\frac{1}{k+\mathrm{rank}_r(p)}
```

## 11. Architecture

&#91;embedded content: MissionMind v2 architecture · proposed, not implemented\]

Changed from v1: extraction is now labelled as adapted from \[10\], and the graph box is no longer marked as a contribution. Only the two components whose value RQ1–RQ3 must test are highlighted. Graph facts reach the answer only as cited passages, so a graph error can lower ranking quality but cannot insert an uncited claim. Each highlighted component has a matching ablation in Section 13.

## 12. Contributions and qualified novelty claims

The contributions are re-ranked so that the benchmark comes first and the method second. Every claim is conditional on the evidence listed.

| # | Contribution | Type | Wording allowed in a paper | Allowed only if |
| --- | --- | --- | --- | --- |
| C1 | Cross-mission causal analogy retrieval task and a human-annotated benchmark over spaceflight mishap reports (D1–D3), with manifest and guidelines | Task + benchmark | "To our knowledge, the first benchmark for …, within \[documented search scope\]" | ≥ 20 missions; agreement reported (target κ/α ≥ 0.6); release of labels and manifest subject to source licences |
| C2 | Extension of anchor-and-verify extraction \[10\] to whole reports with page provenance carried through retrieval | Adapted method | "We extend AEVS-style grounding to document-level …" (never "novel framework") | RQ1 shows a precision gain over both comparison extractors with the recall cost quantified; otherwise reported as neutral or negative |
| C3 | Graph channel (idf-weighted causal-factor overlap) added to multi-field hybrid retrieval \[1\] | Adapted method | "Adding a verified causal-factor channel to \[1\] improves … by X \[CI\]" | Pre-registered primary comparison significant; otherwise "no improvement was observed" |
| C4 | Empirical findings: per-category graph effects; validity of metadata proxy and LLM judge vs humans | Empirical study | Findings as observed, in either direction | Results reported with CIs |

**Removed or narrowed from v1:**

- "Evidence-anchored causal-factor graph construction" as a proposed combination: now explicitly adapted from \[10\] and positioned against \[9\].
- "First to link failures across missions": \[9\] links causes across accidents in aviation, so we claim only *human-judged analogy retrieval*.
- "Uncertainty-awareness": now evaluation only.
- Any claim of generality beyond the corpus and agencies actually represented.

## 13. Experimental design

The study has two pre-registered primary comparisons, both P vs B3: analogy nDCG@5 on D2, and key-point recall on D3. Everything else is secondary and corrected for multiple comparisons.

### 13.1 Systems

| ID | System | Purpose |
| --- | --- | --- |
| B0 | LLM only | Parametric knowledge; contamination check |
| B1 | BM25 \[18\] over passages | Lexical floor |
| B2 | Dense (bge-m3) over passages | Vector RAG |
| B3 | Multi-field BM25 + dense, RRF \[1\] | **Base-paper method (key comparison)** |
| B4 | Repaired current MissionMind (vector + unverified graph facts) | Shows what the redesign changes |
| B5 | LightRAG \[16\] (Microsoft GraphRAG \[15\] on a subset if compute allows) | Published GraphRAG |
| B6 | Full-document long context (optional, short reports only) | Motivated by \[5\] |
| **P** | B3 + verified causal-factor graph channel + citation-constrained generation | Proposed |

**Extractors (RQ1):** case-insensitive gazetteer NER · LLM unverified · AEVS-style sentence-level anchoring \[10\] · P (document-level anchor + span + NLI, with pages).

**Ablations of P:** −graph channel · −verification · −canonicalisation · −fields · graph only · idf off · embedder swap (MiniLM / E5 \[30\] / bge-m3) · generator swap (Llama-3.1-8B / Qwen2.5-7B) · R1 degraded graph (optional).

### 13.2 Hypotheses (measurable; none observed yet)

| ID | Hypothesis | Test | Refuted if |
| --- | --- | --- | --- |
| H1 | P's extractor has higher precision than unverified and AEVS-style extractors on D1 | Paired bootstrap on per-passage F1 components | 95% CI of the difference includes 0 |
| H2 | P > B3 on analogy nDCG@5 | Paired permutation over query missions | p ≥ 0.05 or CI includes 0 |
| H3 | Graph gains concentrate in cross-mission and aggregation categories (consistent with \[12\]) | Per-category paired tests, Holm-corrected | Uniform or no gains |
| H4 | P has a higher claim-support rate and better abstention than B2 and B4 | Paired bootstrap | No difference |
| H5 | The metadata proxy and the LLM judge agree only moderately with humans | Spearman ρ, Cohen's κ | High agreement (reported as support for \[1\]) |
| H6 | B0 scores high on famous missions and low on others | Per-mission breakdown | No difference |

### 13.3 Metrics

| Level | Metrics |
| --- | --- |
| Annotation | Cohen's κ, Krippendorff's α, % agreement |
| Extraction | Micro and macro P/R/F1 at L1 and L2; role accuracy; page-anchor validity; rejection rate per check |
| Passage retrieval | Recall@{5, 10, 20}, nDCG@10, MRR |
| Analogy retrieval | nDCG@5 (primary), P@3, MAP |
| Answers | Key-point recall (human-scored), claim support rate \[21\], citation precision and recall |
| Abstention | Correct-abstention rate on C5; false-abstention rate on C1–C4 |
| Validity | Judge vs human (ρ, κ); proxy vs human (ρ); judge from a different model family than the generator, given known LLM-judge biases \[22\] |
| Cost | Indexing time, LLM calls, query latency, peak VRAM |

ROUGE, SBERT similarity and RAGAS \[20\] scores are reported only as secondary, because \[5\] reports they do not track hallucination in accident-report summaries.

### 13.4 Statistics and fairness

- Paired bootstrap with 10,000 resamples for 95% CIs \[23\]; paired permutation tests; Holm–Bonferroni correction for secondary metrics; effect sizes reported.
- About 30% dev / 70% test split. The test set is hashed and frozen before any tuning, and analogy tuning uses dev missions only.
- Every system gets the same corpus version, passages, generator, prompt template, context budget and tuning budget.
- Three seeds for robustness runs; the main runs use temperature 0.
- A power note is reported: with about 105 test questions and 20–35 query missions, only moderate effects are detectable.
- All numbers are regenerated from logged runs by one script.

## 14. Dataset and annotation strategy

The benchmark is the main contribution, so its construction follows a written protocol fixed before labelling starts. Corpus figures below are targets. Only 4 of the existing documents qualify as primary sources today.

### 14.1 Corpus

- **Inclusion:** official investigation, inquiry-board or failure-analysis documents (full report or official public summary) for spaceflight losses or major anomalies; publicly accessible; English or official translation; causal findings stated. Journal articles are excluded as primary sources.
- **Valid now (4):** Challenger (Rogers Commission Vol. 1), Columbia (CAIB Vol. I), Mars Climate Orbiter (MIB Phase I), Ariane 5 Flight 501.
- **Replace (1):** the ExoMars journal article → ESA *Schiaparelli Anomaly Inquiry* (DG-I/2017/546/TTN).
- **Candidates, availability unverified:**
  - NASA: Mars Polar Lander, Genesis, CONTOUR, DART, WIRE, NOAA-N Prime, OCO, Glory, Mars Observer, Lewis, Apollo 13, Apollo 204
  - ESA and partners: SOHO, Beagle 2, Vega VV15 and VV17 summaries
  - JAXA: Hitomi
  - ISRO: GSLV-F10 FAC statement
- **Distractors:** the two ISRO annual reports, used only to test whether retrieval avoids non-failure text.
- **Known imbalance:** NASA-heavy; the Chandrayaan-2 FAC report is not public. The agency distribution is reported, and no cross-agency claim exceeds it.

### 14.2 Annotation protocol

| Set | Unit | Labels | Size | Double-labelled |
| --- | --- | --- | --- | --- |
| D1 | Passage (stratified by pseudo-field and mission) | L1/L2 causal factor(s), role (root / contributing / proximate as stated by the board), subsystem, phase, page-anchored supporting span | \~350 | ≥ 25% |
| D2 | Mission pair, judged from 1-page mission cards that cite pages | 0 / 1 / 2 causal analogy (Section 4) | All pairs: 190 (20 missions) to 595 (35) | ≥ 25% |
| D3 | Question | Category C1 single-mission factual (30), C2 single-mission causal (30), C3 cross-mission comparison (30), C4 analogy or aggregation (40), C5 unanswerable (20); key points; evidence pages | \~150 | All reviewed; ≥ 25% re-answered |

**Procedure:**

1. Write the guideline with worked examples.
2. Pilot on 10% of items with two annotators.
3. Compute agreement, revise the guideline **once**, and log the changes.
4. Label the full sets.
5. Adjudicate disagreements and keep the raw labels.

Test items are written from the reports before any system output is seen. The taxonomy and guideline are frozen and hashed before Stage 4. Annotator identities and time spent are recorded for the paper.

**Licensing.** Release annotations as offsets plus the manifest. Redistribute PDFs only where the source licence allows (US government works are generally public domain; ESA and JAXA terms must be checked per document).

## 15. Limitations and threats to validity

The largest threats are small scale, single-site annotation and LLM pre-training exposure to famous accidents. Each is mitigated, not eliminated, and each will be stated in the paper.

| Threat | Type | Mitigation | Residual risk |
| --- | --- | --- | --- |
| 20–35 missions; about 105 test questions | External / statistical | Within-corpus claims only; CIs; power note; pre-registered primaries | High: no broad generalisation |
| Annotation by the student plus one second annotator | Internal / construct | Guideline, pilot, agreement statistics, adjudication log | Medium |
| Graded "causal analogy" may not match investigators' notion | Construct | Definition tied to board-stated factors; examples in the guideline | Medium; an expert user study is future work |
| LLM pre-training contamination (Challenger, Columbia) | Internal | B0 per-mission check; unanswerable items; less-known missions | Medium |
| Tuning leakage | Internal | Frozen, hashed test set; dev-only tuning | Low |
| NASA-heavy corpus; ISRO reports unavailable | External | Report the distribution; no cross-agency generality claim | High for agency balance |
| OCR noise in older scans | Internal | CER sampling; re-OCR; flag pages | Low–medium |
| Single small generator family on an 8 GB GPU | External | Two generator families; report model tags | Medium: results may differ with larger models |
| LLM judge bias | Construct | Different-family judge; human validation (RQ4) | Low–medium |
| Prompt injection or poisoning via documents | Security | Official sources only; checksums; note risks \[28\], \[29\] | Low for a closed corpus |
| Literature search scope (IEEE Xplore, Scopus not searched directly) | Novelty | Logged search before submission | Medium until done |

## 16. Future work

Only directions stated in sources actually read are attributed to those sources. The rest are our own proposals.

| Direction | Source of the direction | Scope |
| --- | --- | --- |
| Graph-based reasoning over precedents | \[1\], stated future work | **In scope (C3)** |
| Document-level grounded extraction; carrying provenance into RAG | \[10\], stated future work | **In scope (C2)** |
| Linking source reports to graph nodes and edges; finer causation schema | \[9\], stated future work | **In scope** (page provenance; L2 taxonomy) |
| Uncertainty-aware evaluation | \[1\], discussion | Partly in scope (abstention only) |
| Confidence calibration of extracted facts | \[10\], stated future work | Future |
| Second corpus (NTSB aviation or NASA lessons-learned records) to test generalisation | Our proposal; required for a TR-level journal extension | Future: journal stage |
| Linking factors and recommendations to standards (NASA or ECSS), analogous to \[1\]'s regulations idea | \[1\], adapted | Future |
| Multimodal evidence (figures, tables, telemetry) | Our proposal; related to \[3\] | Future |
| Expert user study with mishap investigators | Our proposal (construct validity) | Future |

## 17. Roadmap and approval gates

&#91;embedded content: Stage plan v2 · planning estimate, weeks after approval\]

Gate G0 is approval of this proposal and the venue decision rule (Section 19). Each later gate produces a stage report: what was done, the acceptance check, and unresolved issues. The next stage starts only after your explicit approval. S4 is one week longer than in v1 because anchor-and-verify extraction costs more LLM calls.

| Stage | Objective and key tasks | Deliverables | Acceptance criteria (at gate) | Main risk → corrective action |
| --- | --- | --- | --- | --- |
| S1 Repair + baseline | Restore the retriever; fix the evaluation runner; packaging, lock file, env-only secrets, configs, seeds, tests; one end-to-end run on the current corpus; measure throughput | Working pipeline; run log; measured costs | One command rebuilds the index and answers a query; tests pass; artefacts saved; Section 18 estimates replaced by measurements | Environment issues → Docker compose file |
| S2 Corpus + parsing | Verify candidates; manifest with SHA-256; NFKC; page- and section-aware parsing; pseudo-fields; OCR CER sampling | Manifest; `passages.jsonl`; parsing report | ≥ 20 usable missions (target 25–35) or a documented shortfall; pseudo-field accuracy ≥ 90% on 100 sections; every passage has doc + page | Too few reports → include official summaries; apply decision rule 3 |
| S3 Taxonomy + annotation | Freeze schema (supervisor sign-off); guidelines; pilot; D1–D3; second annotator on ≥ 25%; logged IEEE Xplore and Scopus search | Guidelines; D1–D3; agreement report; frozen and hashed test split; search log | κ/α reported (target ≥ 0.6); test set hashed before S4; no new competitor invalidates C1 (else return to G0) | Low agreement → one guideline revision, then L1 |
| S4 Extraction + graph | Document-level anchor-and-verify extraction; AEVS-style and unverified baselines; canonicalisation; graph load | Verified and rejected records; graph; RQ1 dev results | Every edge resolves to a page span; all four extractors run on dev | Recall collapse → tune on dev; span-only variant |
| S5 Retrieval + baselines | B0–B6 and P; router; cited generation; citation check; logging | Config-driven systems; dev results | Fairness controls verified by config diff; equal tuning budget | GraphRAG cost → subset run, reported |
| S6 Experiments | Single test run; ablations; statistics; RQ4 validity; error analysis; **G6: apply the venue rule** | Results regenerated from logs; venue decision memo | Primary comparisons reported with CIs, whatever the direction; no metric switching | Null result → decision rule 2 |
| S7 Paper + release | Write for the chosen venue; threats to validity; artefacts; demo | Draft; repository release | Every number traced to a logged run; claims match Section 12 conditions; supervisor review | Page limit → appendix or repository |
| S8 (optional) Journal extension | Second corpus (e.g. NTSB or NASA lessons-learned records) and new results | Journal manuscript | Substantial new technical content per target journal policy; overlap within limits | Insufficient novelty → stay with the conference paper |

## 18. Resources

The study is planned to fit the existing machine: an RTX 4060 Laptop GPU with 8 GB VRAM and CUDA available (verified). It uses only local open models. All figures are planning estimates, and Stage 1 replaces them with measured throughput.

| Item | Estimate | Note |
| --- | --- | --- |
| Corpus | \~0.8–1.5 M words; \~4,000–7,000 passages | Current 5 failure reports = 326k words |
| Extraction (7–8B, 4-bit) | \~10–30 GPU-hours | Revised up from v1: anchor-and-verify uses about 3–5 calls per section (\[10\] reports 2.83–4.28 per sample) |
| AEVS-style baseline extraction | \~5–15 GPU-hours | On D1 passages and the analogy-relevant sections only |
| LightRAG / GraphRAG indexing | \~5–20 GPU-hours | Largest uncertainty; subset if needed |
| Generation + judging | \~10–15 h | About 8 systems × 150 questions × 3 seeds + ablations |
| Storage / RAM | < 5 GB / ≥ 16 GB recommended | RAM not yet verified on this machine |
| Human effort, student | \~90–110 h | Corpus 15–20 h; mission cards 15–20 h; D1 \~12 h; D2 5–10 h; D3 \~25 h; scoring \~15 h |
| Human effort, second annotator | \~12–15 h | Needed for C1 to be credible |

## 19. Publication strategy and venue selection

**Strategy C: complete the evaluation, then choose the venue by a rule fixed now.** With realistic results the rule leads to an IEEE conference first, and later a substantially extended IEEE Transactions on Reliability article built around a second corpus. The full analysis is in the verification report, Sections 7–8.

**Ranked shortlist**

| Rank | Venue | Route | Condition |
| --- | --- | --- | --- |
| 1 | IEEE CASE / RAMS / AERO / ICSC (conference) | First paper | Match to the strongest result: CASE for retrieval vs the base paper; ICSC for extraction or KG; RAMS or AERO for safety practice. Check 2027 calls for papers |
| 2 | IEEE Transactions on Reliability | Journal, after the conference | Significant new technical content, e.g. a second corpus plus new method results (a new case study alone does not qualify, per official policy); ≤ 15 pages; < 30% overlap |
| 3 | IEEE Access | Journal alternative | Benchmark + empirical study, including a negative result; similarity to the conference version < 35%, disclosed; APC $2,160 |
| 4 | IEEE T-ASE | Journal, conditional | Only with an automation-of-investigation framing and a Note to Practitioners |
| — | IEEE TKDE, IEEE TETCI | Not recommended now | Method novelty too modest (TKDE); scope not verified (TETCI) |

**Decision rule (applied at Gate G6)**

1. Significant P > B3 on a primary metric and κ ≥ 0.6: conference (by strongest result), then plan the TR extension.
2. No graph gain, but a reliable benchmark: conference or IEEE Access (Negative Result or Research Article).
3. κ < 0.6 or fewer than 20 missions: pilot or short paper only; extend the data first.

No acceptance is assumed at any venue.

## 20. References

Every DOI below was resolved or matched to a Crossref, OpenAlex, Semantic Scholar, arXiv or NTRS record on 2026-10-12. The access tag shows what was read: **\[F\]** full text, **\[S\]** relevant sections, **\[A\]** abstract only, **\[M\]** metadata only. \[5\] is early access, so check its final volume and pages before submission. \[18\], \[26\] and \[27\] are standard texts not resolved by DOI here; check them against the physical source.

- &#91;1\] S. Kim and S. Kim, "Multi-field hybrid retrieval-augmented generation for maritime accident root cause analysis," in *Proc. 2026 IEEE 22nd Int. Conf. Automation Science and Engineering (CASE)*, Aug. 2026, pp. 238–243, doi: 10.1109/CASE69030.2026.11704480. \[F\]
- &#91;2\] W. Sanyaolu and D. P. Josyula, "LLM-augmented semantic integration: Scalable knowledge graph construction from unstructured safety-critical narratives," in *Proc. 2026 Int. Conf. Semantic Computing (ICSC)*, 2026, pp. 397–402, doi: 10.1109/ICSC67292.2026.00066. \[A\]
- &#91;3\] J. An, H. Chen, J. Zhao, Q. Tang, X. Gui, X. He, and J. Ai, "ADRAG: Avionics diagnostic retrieval-augmented generation by fusing hierarchical semantic trees and knowledge graphs," *IEEE Trans. Rel.*, vol. 75, pp. 2523–2535, 2026, doi: 10.1109/TR.2026.3704165. \[A\]
- &#91;4\] Z. Fu, H. Chen, H. Li, H. Yang, T. Bi, W. Zhao, and D. Zhao, "Improving the reliability of port equipment maintenance decision support via context-aware knowledge graph retrieval-augmented generation," *IEEE Trans. Rel.*, vol. 75, pp. 2023–2036, 2026, doi: 10.1109/TR.2026.3696706. \[A\]
- &#91;5\] Y. Yuan, Q. Wang, C. Ma, and W. Ding, "To err are LLMs: Profiling hallucinations in generated summaries of maritime accident reports," *IEEE Trans. Emerg. Topics Comput. Intell.*, early access, 2026, doi: 10.1109/TETCI.2026.3688150. \[A\]
- &#91;6\] P. Liu, L. Qian, X. Zhao, and B. Tao, "Joint knowledge graph and large language model for fault diagnosis and its application in aviation assembly," *IEEE Trans. Ind. Informat.*, vol. 20, no. 6, pp. 8160–8169, Jun. 2024, doi: 10.1109/TII.2024.3366977. \[A\]
- &#91;7\] Y. Gao, G. Zhu, Y. Duan, and J. Mao, "Semantic encoding algorithm for classification and retrieval of aviation safety reports," *IEEE Trans. Autom. Sci. Eng.*, vol. 22, pp. 4643–4650, 2025, doi: 10.1109/TASE.2024.3359356. \[A\]
- &#91;8\] H. Qi, J. Li, Y. Ge, H. Wu, Y. Cai, S. Che, T. Sheng, Q. Zhao, and C. Chen, "DUAL-Know: A description-augmented and uncertainty-aware GraphRAG framework for anesthesiology question answering," *IEEE Trans. Knowl. Data Eng.*, vol. 38, no. 8, pp. 5015–5031, Aug. 2026, doi: 10.1109/TKDE.2026.3700611. \[A\]
- &#91;9\] X. Xiang, X. Chen, and J. Yang, "Knowledge graph-based causal analysis of aviation accidents: A hybrid approach integrating retrieval-augmented generation and prompt engineering," *Aerospace*, vol. 13, no. 1, Art. no. 16, 2026, doi: 10.3390/aerospace13010016. \[F\]
- &#91;10\] Y. Yang, G. Chen, B. He, and Y. Zhao, "Grounded knowledge graph extraction via LLMs: An anchor-constrained framework with provenance tracking," *Computers*, vol. 15, no. 3, Art. no. 178, 2026, doi: 10.3390/computers15030178. \[S\]
- &#91;11\] X. Xie, X. Tang, S. Gu, and L. Cui, "An intelligent guided troubleshooting method for aircraft based on HybirdRAG," *Sci. Rep.*, vol. 15, 2025, doi: 10.1038/s41598-025-02643-2. \[A\] (title spelling as published)
- &#91;12\] K. Ai, J. A. Karr, M. Jiang, N. V. Chawla, and C. Wang, "KEO: Knowledge extraction on OMIn via knowledge graphs and RAG for safety-critical aviation maintenance," arXiv:2510.05524, 2025 (preprint). \[A\]
- &#91;13\] S. Andrade and H. Walsh, "Natural language processing techniques for intelligent knowledge management of safety reports," presented at NASA Data Science Summit, 2022, NTRS 20220016425. \[A\]
- &#91;14\] Y. Wang *et al.*, "AGRAG: Advanced graph-based retrieval-augmented generation for LLMs," in *Proc. IEEE Int. Conf. Data Eng. (ICDE)*, 2026, doi: 10.1109/ICDE65706.2026.00110. \[A\]
- &#91;15\] D. Edge *et al.*, "From local to global: A graph RAG approach to query-focused summarization," arXiv:2404.16130, 2024. \[M\]
- &#91;16\] Z. Guo, L. Xia, Y. Yu, T. Ao, and C. Huang, "LightRAG: Simple and fast retrieval-augmented generation," in *Findings Assoc. Comput. Linguistics: EMNLP 2025*, pp. 10746–10761, doi: 10.18653/v1/2025.findings-emnlp.568. \[M\]
- &#91;17\] G. V. Cormack, C. L. A. Clarke, and S. Buettcher, "Reciprocal rank fusion outperforms Condorcet and individual rank learning methods," in *Proc. 32nd Int. ACM SIGIR Conf.*, 2009, pp. 758–759, doi: 10.1145/1571941.1572114. \[M\]
- &#91;18\] S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Found. Trends Inf. Retr.*, vol. 3, no. 4, pp. 333–389, 2009.
- &#91;19\] J. Chen, S. Xiao, P. Zhang, K. Luo, D. Lian, and Z. Liu, "M3-Embedding: Multi-linguality, multi-functionality, multi-granularity text embeddings through self-knowledge distillation," in *Findings Assoc. Comput. Linguistics: ACL 2024*, pp. 2318–2335, doi: 10.18653/v1/2024.findings-acl.137. \[M\]
- &#91;20\] S. Es, J. James, L. Espinosa-Anke, and S. Schockaert, "RAGAs: Automated evaluation of retrieval augmented generation," in *Proc. EACL: System Demonstrations*, 2024, pp. 150–158, doi: 10.18653/v1/2024.eacl-demo.16. \[M\]
- &#91;21\] S. Min *et al.*, "FActScore: Fine-grained atomic evaluation of factual precision in long form text generation," in *Proc. EMNLP*, 2023, pp. 12076–12100, doi: 10.18653/v1/2023.emnlp-main.741. \[M\]
- &#91;22\] L. Zheng *et al.*, "Judging LLM-as-a-judge with MT-Bench and Chatbot Arena," in *Adv. Neural Inf. Process. Syst. (NeurIPS)*, 2023, pp. 46595–46623. \[M\]
- &#91;23\] P. Koehn, "Statistical significance tests for machine translation evaluation," in *Proc. EMNLP*, 2004, pp. 388–395. \[M\]
- &#91;24\] J. Chen, H. Lin, X. Han, and L. Sun, "Benchmarking large language models in retrieval-augmented generation," in *Proc. AAAI Conf. Artif. Intell.*, vol. 38, no. 16, 2024, pp. 17754–17762, doi: 10.1609/aaai.v38i16.29728. \[M\]
- &#91;25\] M. Tafazoli, "A study of on-orbit spacecraft failures," *Acta Astronaut.*, vol. 64, no. 2–3, pp. 195–205, 2009, doi: 10.1016/j.actaastro.2008.07.019. \[M\]
- &#91;26\] D. A. Wiegmann and S. A. Shappell, *A Human Error Approach to Aviation Accident Analysis: The Human Factors Analysis and Classification System*. Aldershot, U.K.: Ashgate, 2003.
- &#91;27\] N. G. Leveson, *Engineering a Safer World: Systems Thinking Applied to Safety*. Cambridge, MA, USA: MIT Press, 2012, doi: 10.7551/mitpress/8179.001.0001. \[M\]
- &#91;28\] J. Liang *et al.*, "GraphRAG under fire," in *Proc. IEEE Symp. Security and Privacy (SP)*, 2026, pp. 195–212, doi: 10.1109/SP63933.2026.00070. \[A\]
- &#91;29\] D. Escribano Arias, D. Gomez-Lendinez, B. Navas de Maya, and C. Velasco-Gallego, "Retrieval-augmented generation for maritime accident report analysis: Evaluating large language models on performance and cybersecurity," *J. Mar. Sci. Eng.*, 2026, doi: 10.3390/jmse14110983. \[A\]
- &#91;30\] L. Wang *et al.*, "Text embeddings by weakly-supervised contrastive pre-training," arXiv:2212.03533, 2022. \[M\]
- &#91;P\] Primary corpus sources (Rogers Commission 1986; CAIB 2003; MCO MIB 1999; Ariane 501 Inquiry Board 1996; ESA Schiaparelli Anomaly Inquiry DG-I/2017/546/TTN, 2017) are cited in the corpus manifest with URLs and checksums.
