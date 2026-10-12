# MissionMind — Literature Verification, Novelty and Publication Strategy

Oct 12, 2026 · @yash

Deliverables 1, 2, 3 and 5. The revised proposal (Deliverable 4) is a separate document, MissionMind — Research Proposal v2. The earlier audit and proposal are preserved unchanged.

## Decision summary

All six journal papers exist and are correctly attributed to their IEEE journals. Four details needed correction: one publication year, one publication status, one title and one author name. None of the six has an accessible full text. Verification also surfaced two closer competitors the earlier search missed. MissionMind's direction survives, but its **methodological** novelty is now modest. The defensible contribution is a new task and human-labelled benchmark, plus a rigorous empirical study, built on an adapted rather than new method.

**What changed**

- **Corrections.** The TASE aviation-safety paper appeared online in March 2024 but is in volume 22 (2025). The TETCI maritime-hallucination paper is an Early Access article without volume or issue. The port-maintenance paper's exact title differs from the earlier shorthand.
- **Evidence-anchored extraction is not new.** AEVS (*Computers*, 2026) already grounds each LLM-extracted triple in character positions and verifies it against the source. Our component becomes an adaptation: from sentence level to whole reports, with page provenance carried through retrieval. AEVS itself lists document-level extraction and RAG integration as future work.
- **Cross-accident causal knowledge graphs are not new.** Xiang et al. (*Aerospace*, 2026; online December 2025) build a causation graph from NTSB reports (343 in the abstract, 348 in the methods text) and analyse causal chains across accidents. MissionMind therefore cannot claim cross-case causal graphs. It can claim *query-time causal analogy retrieval evaluated against human judgement* on spaceflight reports, which none of the verified works does.
- **Uncertainty-aware GraphRAG exists** (DUAL-Know, *IEEE TKDE*, 2026). Abstention stays as an evaluation dimension, not a claimed contribution.

**Recommendation**

- **Strategy C, results-gated.** Finish Stages 1–6, then choose the venue by a pre-committed rule.
- **Default outcome: an IEEE conference paper first.** CASE, RAMS, AERO or ICSC, chosen by result profile.
- **Journal: IEEE Transactions on Reliability**, but only after a substantially extended second study. That journal's official policy rejects extensions that add only a case study.

## 1. Verification of the six IEEE journal papers

All six were checked against three independent records: the DOI resolver's redirect to IEEE Xplore, Crossref citation metadata (via DOI content negotiation), and OpenAlex plus Semantic Scholar. Abstracts come from Semantic Scholar or OpenAlex. All six are closed access, and no preprint was found on arXiv or by web search. **No full text was read, so methods, data and results below are limited to what the abstracts state.**

| # | Exact title | Authors (as in Crossref) | Journal | Volume / issue / pages | Status | DOI · IEEE Xplore |
| --- | --- | --- | --- | --- | --- | --- |
| J1 | ADRAG: Avionics Diagnostic Retrieval-Augmented Generation by Fusing Hierarchical Semantic Trees and Knowledge Graphs | J. An, H. Chen, J. Zhao, Q. Tang, X. Gui, X. He, J. Ai | IEEE Transactions on Reliability | Vol. 75, pp. 2523–2535, 2026; issue not in metadata | Published with pagination | [10.1109/TR.2026.3704165](https://doi.org/10.1109/TR.2026.3704165) · doc. 11568736 |
| J2 | Improving the Reliability of Port Equipment Maintenance Decision Support via Context-Aware Knowledge Graph Retrieval-Augmented Generation | Z. Fu, H. Chen, H. Li, H. Yang, T. Bi, W. Zhao, D. Zhao | IEEE Transactions on Reliability | Vol. 75, pp. 2023–2036, 2026; issue not in metadata | Published with pagination | [10.1109/TR.2026.3696706](https://doi.org/10.1109/TR.2026.3696706) · doc. 11535030 |
| J3 | To Err Are LLMs: Profiling Hallucinations in Generated Summaries of Maritime Accident Reports | Y. Yuan, Q. Wang, C. Ma, W. Ding | IEEE Transactions on Emerging Topics in Computational Intelligence | No volume or issue; pp. 1–14; 2026 | **Early Access** (inferred from missing volume and issue) | [10.1109/TETCI.2026.3688150](https://doi.org/10.1109/TETCI.2026.3688150) · doc. 11515092 |
| J4 | Joint Knowledge Graph and Large Language Model for Fault Diagnosis and Its Application in Aviation Assembly | P. Liu, L. Qian, X. Zhao, B. Tao | IEEE Transactions on Industrial Informatics | Vol. 20, no. 6, pp. 8160–8169, Jun. 2024 | Published | [10.1109/TII.2024.3366977](https://doi.org/10.1109/TII.2024.3366977) · doc. 10463190 |
| J5 | Semantic Encoding Algorithm for Classification and Retrieval of Aviation Safety Reports | Y. Gao, G. Zhu, Y. Duan, J. Mao | IEEE Transactions on Automation Science and Engineering | Vol. 22, pp. 4643–4650, **2025** (online 18 Mar. 2024) | Published | [10.1109/TASE.2024.3359356](https://doi.org/10.1109/TASE.2024.3359356) · doc. 10474306 |
| J6 | DUAL-Know: A Description-Augmented and Uncertainty-Aware GraphRAG Framework for Anesthesiology Question Answering | H. Qi, J. Li, Y. Ge, H. Wu, Y. Cai, S. Che, T. Sheng, Q. Zhao, C. Chen | IEEE Transactions on Knowledge and Data Engineering | Vol. 38, no. 8, pp. 5015–5031, Aug. 2026 | Published | [10.1109/TKDE.2026.3700611](https://doi.org/10.1109/TKDE.2026.3700611) · doc. 11551860 |

**Corrections to the earlier search result**

| Item | Earlier statement | Verified | Effect |
| --- | --- | --- | --- |
| J5 year | "IEEE TASE, 2024" | Volume 22, 2025. The DOI and online date are 2024 | Cite as vol. 22, 2025 |
| J3 status | Listed as a 2026 journal paper | Early Access, with no volume or issue assigned | Cite as early access; recheck before submission |
| J2 title | "Context-Aware Knowledge Graph RAG for Port Equipment Maintenance" | Full title above | Use the exact title |
| J6 authors | OpenAlex lists "J D Li" | Crossref lists "Jianqiang Li" | Use Crossref |
| J1 abstract | Earlier reported as unavailable | The abstract is available from Semantic Scholar | Content now verified from the abstract |

IEEE Xplore record pages could not be rendered for automated reading. The document numbers come from the DOI resolver's redirects.

## 2. What each paper verifiably does (abstract-level only)

None of the six works with mishap or accident *investigation* reports in the spaceflight domain. Only J3 and J5 work with safety or accident reports at all. Their main effect on MissionMind is on evaluation design and baselines, not on the core gap.

| # | Problem (from abstract) | Method (from abstract) | Data and evaluation (from abstract) | Not knowable without full text | Relevance to MissionMind | Effect on novelty or method |
| --- | --- | --- | --- | --- | --- | --- |
| J1 ADRAG | Avionics fault diagnosis depends on expert reading of multimodal datasheets (text, schematics, timing diagrams); existing RAG gives diagnoses inconsistent with sources | Hierarchical semantic tree with recursive partitioning and quality-gated multimodal assembly guides KG construction; a multi-agent system combines tree traversal with graph queries; adaptive fallback when structure is missing | "Specialized avionics dataset"; reported to outperform RAG baselines, especially on cross-modal reasoning. No numbers in the abstract | Dataset size, metrics, baselines, statistics, limitations, future work | **High (aerospace domain).** Structure-guided KG over long technical documents, aimed at verifiability | Supports structure-aware parsing (our M2). Its domain is datasheets, not mishap reports, and it is not cross-case retrieval. Cite as closest aerospace KG-RAG |
| J2 ContextKG-RAG | Fixed retrieval strategies and single-metric ranking limit maintenance decision support | Topic modelling infers task context; dynamic programming adapts KG traversal depth and scope; multi-objective node selection for accuracy, diversity and relevance | HotpotQA plus a real port-equipment O&M dataset; outperforms RAG baselines on retrieval and response quality; robust under degraded KGs | Sizes, metrics, baselines, significance | Medium. Reliability-domain KG-RAG in the same journal we target | Suggests a robustness test on a degraded or incomplete graph. Adopted as an optional ablation |
| J3 To Err Are LLMs | LLM summaries of maritime accident reports hallucinate, which is risky in a safety-critical domain | Fine-grained hallucination taxonomy; statistical analysis across LLMs; MARHAS annotated dataset; Pareto analysis of human vs LLM; automated factuality benchmarking | Smaller open models degrade with more in-context examples; standard automatic quality metrics do not correlate with hallucination frequency; full-document context is crucial for fact grounding | Corpus size, annotation protocol, agreement, dataset licence | **High (evaluation).** Same document type: official accident reports | Strengthens our use of human and claim-level evaluation instead of ROUGE/SBERT. Motivates a full-document baseline where context length allows |
| J4 Joint KG + LLM | Fast fault localisation in aviation assembly testing | KG embeddings used for prefix-tuning an LLM; subgraph generation and retrieval-augmented knowledge fusion | Industrial scenario; 98.5% accuracy for fault diagnosis and troubleshooting schemes | Test-set size, baselines, definition of accuracy | Low–medium. Aviation KG + LLM, but a fine-tuned model on proprietary assembly data | No effect on the gap. Different task (symptom → fault) |
| J5 Semantic encoding | No public large aviation text-similarity dataset; general embeddings misrepresent technical terms | Automatically created similarity dataset of more than 500,000 pairs; a semantic encoding algorithm for aviation terms | Classification and retrieval of safety reports with revised metrics; claims superiority over baselines | Pair-labelling rule, test design, metrics | **Medium–high (retrieval).** Retrieval of similar safety reports | Shows report-to-report similarity retrieval exists in aviation, using *automatically generated* similarity. Our differentiation is human causal-analogy labels. Supports an embedder ablation |
| J6 DUAL-Know | GraphRAG in anesthesiology QA suffers from synonymy, logic drift and conflicts between evidence and parametric knowledge | Query and description augmentation; gated heterogeneous attention; uncertainty-aware path ranking; multi-metric conflict arbitration | Clinical QA; reported to outperform strong baselines. No numbers in the abstract | Datasets, metrics, calibration method | Medium (method). Uncertainty-aware GraphRAG in a high-stakes domain | **Removes uncertainty-aware GraphRAG as a novelty claim.** Our abstention stays as an evaluation dimension |

Limitations and future work are not reported for any of the six because none was stated in the abstracts. Inferring them would be speculation.

## 3. Closer competitors found during verification

Two non-IEEE papers overlap MissionMind more than any of the six IEEE journal papers: X1 (causal knowledge graphs across accidents) and X2 (provenance-anchored LLM extraction). Both were read in the full open-access text, X2 in its relevant sections.

| # | Work (verified record) | Access level | What it does | What it does *not* do | Effect on MissionMind |
| --- | --- | --- | --- | --- | --- |
| X1 | X. Xiang, X. Chen, J. Yang, "Knowledge Graph-Based Causal Analysis of Aviation Accidents: A Hybrid Approach Integrating RAG and Prompt Engineering," *Aerospace*, vol. 13, no. 1, Art. 16, 2026 (online 24 Dec. 2025), [doi](https://doi.org/10.3390/aerospace13010016) | **Full text read** | NTSB Part 121 reports from 2000 onward, with fixed narrative and probable-cause sections. DeepSeek-V3.1 extracts causes and relations; a Human / Aircraft / Environment / Organization causation schema (aircraft causes mapped to FAA JASC codes); a causation KG; high-risk causes and critical causal chains. Manual check of 50 reports: about 95% causation accuracy, over 98% relation accuracy | No recall, no inter-annotator agreement, no baselines or significance tests. No query-time retrieval of analogous accidents. KG nodes do not link back to source passages, which the authors name as future work ("integrating … their source accident reports into nodes or edges"). Report count is inconsistent: 343 in the abstract, 348 in Section 3.2 | **Largest overlap.** Removes "cross-case causal KG" as a novelty. Leaves open source provenance, retrieval of analogous cases, human relevance benchmarks, and multi-agency heterogeneous reports |
| X2 | Y. Yang, G. Chen, B. He, Y. Zhao, "Grounded Knowledge Graph Extraction via LLMs: An Anchor-Constrained Framework with Provenance Tracking," *Computers*, vol. 15, no. 3, Art. 178, 2026, [doi](https://doi.org/10.3390/computers15030178) | **Full text: method, datasets and future-work sections read** | AEVS: anchor discovery with character positions → grounded triple extraction → restoration-based verification → coverage supplement. Evaluated on WebNLG, REBEL, Wiki-NRE; 2.83–4.28 LLM calls per sample | Works per sentence or passage; no cross-sentence or document-level relations; general-domain benchmarks. Future work lists document-level extraction, RAG integration with provenance, and confidence calibration | **Removes "evidence-anchored extraction" as a new method.** MissionMind adapts it to long reports and page provenance, and carries provenance into retrieval (AEVS future work items 3 and 4). AEVS becomes a baseline extractor |
| X3 | X. Xie, X. Tang, S. Gu, L. Cui, "An intelligent guided troubleshooting method for aircraft based on HybirdRAG" \[sic\], *Sci. Rep.*, vol. 15, 2025, [doi](https://doi.org/10.1038/s41598-025-02643-2) | Abstract | Graph reasoning + vector + BM25 retrieval for aircraft fault diagnosis; at least +4% F1 and over 7% fewer hallucinations vs RAG baselines | Troubleshooting, not investigation reports or cross-case analogy | Hybrid lexical + dense + graph fusion is established. Our retrieval is an adaptation |
| X4 | K. Ai *et al.*, "KEO: Knowledge Extraction on OMIn via Knowledge Graphs and RAG for Safety-Critical Aviation Maintenance," arXiv:2510.05524, 2025 (preprint) | Abstract | KG-RAG over aviation maintenance records; QA benchmark; local LLMs with stronger LLM judges | Preprint; maintenance logs, not investigation reports | Independent evidence for our H3: KG helps global sensemaking, while text-chunk RAG remains effective for fine-grained tasks |
| X5 | S. Andrade, H. Walsh, "Natural Language Processing Techniques for Intelligent Knowledge Management of Safety Reports," NASA Data Science Summit presentation, 2022, [NTRS 20220016425](https://ntrs.nasa.gov/citations/20220016425) | Abstract | NASA MIKA toolkit: topic modelling and fine-tuned NER for failure modes, causes, effects and recommendations on aerial wildfire mishap reports | Not spaceflight; no graph-based retrieval; a presentation, not a peer-reviewed paper | NASA-side prior work on NLP over mishap reports. Cite as a presentation |
| X6 | J. Yang, X. Xiang, X. Chen, "A Retrieval-Augmented Generation-Based Method for Aviation Accident Data Analysis," *Proc. 4th ICAIRC*, 2024, pp. 868–874, [doi](https://doi.org/10.1109/ICAIRC64177.2024.10900039) | Abstract | RAG with an ATA100/AMM knowledge base to code aviation accident reports | Classification coding, not analogy retrieval | Minor; same group as X1 |
| X7 | D. Escribano Arias *et al.*, "Retrieval-Augmented Generation for Maritime Accident Report Analysis: Evaluating LLMs on Performance and Cybersecurity," *J. Mar. Sci. Eng.*, 2026, [doi](https://doi.org/10.3390/jmse14110983) | Abstract | RAG over UK MAIB reports; 9 LLMs; 18 prompt-injection techniques | Not graph-based; not analogy | Supports a security threat to validity (prompt injection via reports) |

Already in the v1 proposal and re-confirmed: Kim & Kim, IEEE CASE 2026 (base paper, full text read) and Sanyaolu & Josyula, IEEE ICSC 2026 (abstract only).

## 4. Search scope and residual uncertainty

The gap statement in this document means "not found within the scope below". It does not mean "proven absent".

| Source | Queries (summary) | Period | Coverage |
| --- | --- | --- | --- |
| OpenAlex, IEEE DOIs only (title search) | knowledge graph × {accident, aviation, aerospace, spacecraft, failure, fault, root cause}; retrieval-augmented × {accident, failure, fault, safety, aviation, aerospace}; GraphRAG; graph retrieval-augmented; LLM × {accident, aviation, aerospace, spacecraft}; {accident, incident, safety, failure} reports | 2021–2026 | All IEEE journal articles indexed by OpenAlex |
| OpenAlex, all publishers (title + abstract) | spacecraft or space-mission failure + LLM; NASA lessons learned; mishap reports KG; launch failure KG; analogous failure retrieval; case-based accident retrieval; accident investigation RAG; KG provenance verification; spaceflight anomaly NLP | 2022–2026 | Journals, proceedings, preprints indexed by OpenAlex |
| NASA Technical Reports Server API | LLM × {mishap, lessons learned, anomaly reports}; KG mishap; NLP mishap reports; RAG lessons learned | All | NASA-authored reports and presentations |
| Web search | Paper titles, preprints, venue policies | — | General web |

**Not searched, and therefore residual risk:**

- IEEE Xplore's own search (pages do not render for automated access).
- Scopus and Web of Science (no access).
- AIAA ARC full texts beyond indexed metadata.
- ESA, JAXA and ISRO internal repositories.
- Non-English literature, especially Chinese-language aerospace journals, where much aviation KG work appears.
- Very recent Early Access items not yet indexed by OpenAlex.

**Recommended mitigation before submission:**

- A librarian-assisted or self-run IEEE Xplore and Scopus search with the same strings, logged with date and hit counts.
- A forward-citation check on X1, X2, J1 and the base paper using Google Scholar "cited by".

## 5. Capability matrix against the six dimensions

Every dimension except D4 is at least partly covered by some prior work. D4 (human-labelled cross-case causal relevance) is not covered by any reviewed work. D6 is covered only partly, by single-agency corpora with fixed report sections. No single work combines more than two of the six dimensions.

Dimensions: **D1** KG + RAG for aerospace or spaceflight failure analysis · **D2** retrieval of causally analogous failures across separate cases · **D3** evidence-verified graph construction with source passages and page provenance · **D4** human-labelled cross-case causal relevance benchmark · **D5** uncertainty-aware retrieval or abstention · **D6** long, unstructured reports from different agencies and eras.

| Work | D1 | D2 | D3 | D4 | D5 | D6 | Basis |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Kim & Kim, IEEE CASE 2026 (base) | No (maritime) | **Yes**: precedent retrieval | No | No: metadata proxy | No | Partial: 55 years, one tribunal, short structured cards | Full text |
| Sanyaolu & Josyula, IEEE ICSC 2026 | Partial: aviation accident KG, no RAG stated | Not stated | Partial: "provenance tracking" stated | No: extraction F1 only | Partial: contradiction heuristics | Partial: one agency (NTSB) | Abstract |
| J1 ADRAG, IEEE TR 2026 | **Yes**: avionics diagnosis | No | Unknown | Unknown | Partial: adaptive fallback | No: datasheets | Abstract |
| J2 ContextKG-RAG, IEEE TR 2026 | No (port equipment) | No | Unknown | Unknown | Partial: robustness to degraded KG | No | Abstract |
| J3 To Err Are LLMs, IEEE TETCI 2026 | No (maritime, no KG) | No | No | Partial: human hallucination labels, not relevance | No | Partial: accident reports | Abstract |
| J4 Joint KG + LLM, IEEE TII 2024 | **Yes**: aviation assembly | No | Unknown | Unknown | No | No | Abstract |
| J5 Semantic encoding, IEEE TASE 2025 | Partial: aviation reports, no KG | Partial: similar-report retrieval | No | No: auto-generated pairs | No | Partial: one domain | Abstract |
| J6 DUAL-Know, IEEE TKDE 2026 | No (clinical) | No | Unknown | Unknown | **Yes** | No | Abstract |
| X1 Xiang *et al.*, *Aerospace* 2026 | **Yes**: aviation accident causation KG + RAG | Partial: cross-accident chains, aggregate only | No: named as future work | No: 50-report accuracy check | No | Partial: NTSB only, post-2000, fixed sections | Full text |
| X2 AEVS, *Computers* 2026 | No | No | **Yes** at sentence level; no pages | No | Partial: calibration named as future work | No | Full text (sections) |
| X3 HybridRAG, *Sci. Rep.* 2025 | **Yes**: aircraft troubleshooting | No | Unknown | Unknown | No | No | Abstract |
| **MissionMind v2 (proposed, not built)** | Yes (spaceflight) | **Yes** (human-judged) | Yes (document level, pages) | **Yes** | Partial: abstention, evaluated only | **Yes** | Plan |

"Unknown" means the abstract is silent and the full text could not be read. It must not be read as "No".

## 6. Novelty assessment and repositioned contribution

The direction remains defensible, but only if it is framed as a **task-and-benchmark contribution with an adapted method**, not as a new GraphRAG method. A pure method framing would overlap X1, X2, X3 and J1 too closely to survive review.

### 6.1 Already established (cite, do not claim)

- KG + RAG for aerospace fault and accident analysis: J1, J4, X1, X3, X4.
- Hybrid BM25 + dense + graph retrieval fused for diagnosis: X3; multi-field hybrid RRF: base paper.
- LLM causal extraction into a causation taxonomy, and causal-chain analysis across accidents: X1.
- Provenance-anchored LLM triple extraction with source verification: X2.
- Retrieval of similar safety reports: J5; precedent retrieval: base paper.
- Uncertainty-aware GraphRAG: J6; robustness to incomplete graphs: J2.
- Standard summary metrics fail to track hallucination in accident-report summaries: J3.
- KG-RAG helps corpus-wide sensemaking while chunk RAG helps local questions: X4 (preprint).

### 6.2 What MissionMind proposes to combine or improve

- Carry AEVS-style anchoring from sentences to **whole long reports with page-level provenance**, and keep that provenance through retrieval into cited answers. This is X2's own stated future work (document-level extraction; RAG integration).
- Link source passages to graph edges, which X1 names as its future work.
- Add a causal-factor graph channel to the base paper's multi-field hybrid retrieval, which is the base paper's stated future work (graph-based reasoning).
- Recover "fields" from unstructured reports by section segmentation, where the base paper relied on fixed tribunal fields.

### 6.3 What may qualify as a methodological contribution (modest)

- **Document-level, page-anchored causal extraction with verification**, if RQ1 shows a measurable precision gain over unverified extraction *and* over an AEVS-style sentence-level baseline on long reports, with the recall cost quantified.
- **IDF-weighted causal-factor overlap as a mission-analogy signal** fused with text retrieval, if it beats the base-paper method on human-judged analogy relevance.
- Both are adaptations. They should be described as "adapted" or "extended", never as "novel frameworks".

### 6.4 What may qualify as a dataset or benchmark contribution (strongest)

- A **cross-mission causal analogy retrieval task** defined over spaceflight mishap investigation reports. No reviewed work defines or evaluates this task.
- A **human-labelled benchmark**: causal-factor annotations with page anchors, graded analogy judgements for all mission pairs, and a categorised QA set including unanswerable questions, with inter-annotator agreement.
- A **meta-evaluation**: how well the base paper's metadata proxy and an LLM judge agree with human labels. This answers limitations the base paper itself states.

### 6.5 What requires experimental evidence before it can be claimed

| Claim | Evidence required | If not obtained |
| --- | --- | --- |
| Verification improves extraction precision on long reports | RQ1: P/R vs gold D1, compared with unverified and AEVS-style variants, with CIs | Report as a negative or neutral finding; drop C2 |
| The graph channel improves analogy retrieval | RQ2: P vs B3, paired test, pre-registered primary metric | Report a null result; C3 becomes "no gain observed" |
| Graph gains are question-type specific | RQ3: per-category results | Report as observed |
| Proxies and LLM judges are unreliable here | RQ4: correlations with human labels | Report as observed, either direction |
| The benchmark is reliable | Agreement statistics (κ or α), with 0.6 as the target | Report at the coarser L1 level, or as a pilot |

**Considered alternatives.** (a) A pure method paper: rejected, because the overlap with X1, X2 and X3 is too high. (b) A pure dataset paper: possible, but weaker without the empirical study. (c) Pivot to aviation NTSB data for scale: this loses the uncovered spaceflight angle, but it is a valuable **second corpus** for a later journal extension. The recommendation is to keep the spaceflight direction with the repositioned contribution.

## 7. Venue analysis

IEEE Transactions on Reliability is the best journal fit, but it is realistic only after a substantially larger study. A first paper fits an IEEE conference, or IEEE Access if a journal is required early. No impact factors, acceptance rates or deadlines are given, because none were verified from official sources.

| Venue | Scope fit (official wording where verified) | Policies verified | What a reviewer will expect | Recent relevant papers | Fit for MissionMind |
| --- | --- | --- | --- | --- | --- |
| **IEEE Transactions on Reliability** ([official page](https://rs.ieee.org/publications/transactions-on-reliability.html)) | Mission includes "mission success", "safety" and "various measures of effectiveness"; subcategory A6 "AI, Machine Learning, Trustworthy AI" | Page limit 15. Overlap with any prior text, including the authors' own, must be under 30%. Conference extensions welcome only "if there is a significant difference in the technical content"; adding a case study or related work does not qualify. Real-life case studies get priority for print publication. Three reviewers, single-anonymous. Open-access option at a discounted $2,495 | Solid contribution beyond incremental variation; real application; substantial related-work discussion | J1 ADRAG, J2 ContextKG-RAG (both 2026) | **Strong scope fit; maturity gap.** Needs the full study *plus* a second corpus or substantially new method results |
| **IEEE Access** ([guidelines](https://ieeeaccess.ieee.org/authors/submission-guidelines/), [preparing](https://ieeeaccess.ieee.org/authors/preparing-your-article/)) | Broad; scope not defined on the page | Article types include Research Article, Applied Research, Negative Result and Methods. APC $2,160 plus taxes, no page limit (stay under about 20 pages). Expanded versions of the authors' own referenced conference papers accepted if similarity is below 35%; must be disclosed | Sound methods and evidence; less emphasis on novelty than on rigour | Several GraphRAG papers (2025–2026) | **Realistic** for a benchmark + empirical study, including a null result (Negative Result type) |
| **IEEE T-ASE** ([author info](https://www.ieee-ras.org/publications/t-ase/information-for-authors-t-ase)) | Automation methods for efficiency, productivity, quality and reliability; planning, scheduling, enterprise operations | 100–300 word Note to Practitioners required. Overlength charges above about 10–12 pages (the page is inconsistent). Hybrid OA $2,800 from 2026. Must cite prior work and explain new contributions; no explicit numeric extension rule | Automation framing and practitioner impact | J5 (aviation safety report retrieval, 2025) | **Moderate.** Plausible only as "automating investigation support"; weaker than TR |
| **IEEE TETCI** | Official scope page not retrieved. Secondary sources describe emerging computational-intelligence topics | Not verified | — | J3 (maritime accident-report hallucination, Early Access 2026) | **Low–moderate.** Verify scope before considering |
| **IEEE TKDE** | Official author page did not render. Archived and secondary text: prior conference papers eligible with "substantial revision" | Not verified from an official page | Strong, general data-engineering methods with broad benchmarks | J6 DUAL-Know (2026) | **Low.** Our method novelty is adapted, and the corpus is small and domain-specific |
| IEEE CASE (conference; base-paper venue) | Automation science and engineering | CFP not checked for 2027 | Concise paper with an application | Base paper (2026) | **Good** for direct dialogue with the base paper |
| IEEE RAMS (conference) | Reliability and maintainability | CFP not checked | Practitioner-oriented reliability work | — | **Good** for the safety-engineering audience |
| IEEE Aerospace Conference (AERO) | Aerospace systems and missions | CFP not checked | Engineering relevance and case studies | — | **Good** for the domain audience |
| IEEE ICSC (conference) | Semantic computing, KGs | CFP not checked | KG + LLM methods | Sanyaolu & Josyula (2026) | **Good** if the extraction result (RQ1) is strongest |

**On republishing a conference paper as a journal paper.** IEEE practice permits it only with substantial new technical content and full citation of the conference version. TR states this explicitly and excludes a mere added case study. Access requires similarity under 35% and disclosure. A conference paper therefore cannot simply be resubmitted. The journal version needs new research (for example a second corpus, new method results, or a user study). The current IEEE PSPB Operations Manual could not be fetched (HTTP 418), so its section wording is not quoted here.

## 8. Publication strategy

**Recommended: Strategy C (evaluate first, then choose the venue), with a decision rule written down before results are seen.** Under realistic outcomes the rule leads to a conference paper first, which is Strategy A in practice. Writing the rule in advance prevents results-driven venue shopping.

| Strategy | Strengths | Risks for MissionMind | Verdict |
| --- | --- | --- | --- |
| A. Conference first, then an extended journal article | Faster feedback; matches a 25–35 report corpus; a conference in the base paper's venue family invites direct comparison | A journal version needs substantial new technical content (TR: a new case study is not enough; Access: under 35% similarity). Two writing cycles | Good default, but chosen before knowing whether results are strong or null |
| B. Directly to an IEEE journal | One publication, more space for the benchmark and statistics | Small single-domain corpus is weak for TR's expectations. A null graph result plus modest method novelty risks rejection after a long review. Cannot later reuse as a conference paper | **Not recommended now** |
| C. Run the evaluation, then choose | Venue matched to the actual evidence; null results can still go to Access (Negative Result type) or a conference | Delays venue-specific framing; needs discipline to avoid post-hoc rationalisation | **Recommended**, with the rule below |

**Decision rule (to approve now, apply after Stage 6)**

1. **Graph gain** (P > B3 on a pre-registered primary metric, 95% CI excluding 0) **and** κ ≥ 0.6: submit to a conference whose audience matches the strongest result. CASE for retrieval vs the base paper, ICSC for extraction or KG, RAMS or AERO for safety practice. Plan a TR journal extension around a second corpus (e.g. NTSB or NASA lessons-learned records) and new results.
2. **No graph gain, but a reliable benchmark and clear RQ3/RQ4 findings**: report the benchmark and the negative or conditional finding at a conference, or in IEEE Access as a Negative Result or Research Article.
3. **Agreement below 0.6 or fewer than 20 usable missions**: no journal submission. Report as a pilot study (workshop or conference short paper), or extend data collection first.

The corpus-size risk is accepted explicitly. 25–35 reports can support a carefully scoped benchmark and within-corpus findings. It cannot support broad generalisation claims, and no venue choice changes that.

## 9. Final audit and decision summary

Proposal v2 passed a mechanical consistency check. All 30 numbered references are cited in the body, every body citation resolves to a listed reference, and all section cross-references point to existing sections. Its stated project status matches the audit of commit `5d0219e`, and no code was changed.

### 9.1 Consistency checks performed

| Check | Method | Result |
| --- | --- | --- |
| Every cited paper against its DOI or publisher record | DOI redirects, Crossref, OpenAlex, Semantic Scholar, arXiv, NTRS | All 30 resolve. \[18\], \[26\] and \[27\] are standard texts not resolved by DOI |
| Literature claims against accessible sources | Claims about \[3\]–\[8\], \[11\]–\[14\] limited to abstracts; \[1\], \[9\] full text; \[10\] relevant sections | No method, limitation or future-work claim made beyond what was read |
| Novelty claims against the closest studies | Capability matrix (Section 5) | Three v1 claims removed or narrowed (below) |
| Experiments against objectives | RQ1→D1/extractors; RQ2→D2/P vs B3; RQ3→D3 categories; RQ4→proxy and judge vs human | Each RQ has one primary table and a hypothesis with a refutation condition |
| Expected improvements against measurable hypotheses | H1–H6 | All have a test and a "refuted if" condition |
| Project status against the audit | Proposal v2, Section 9 | Matches: broken query and evaluation layers, limited corpus, 0.6% NER gate, no results |
| Venue statements against official pages | TR (rs.ieee.org), Access (ieeeaccess.ieee.org), T-ASE (ieee-ras.org) | Verified. TKDE and TETCI author pages were not retrievable and are marked as such |
| Reference formatting | Author lists from Crossref; venues and pages from DOI metadata | Fixed: J5 year 2025; J3 early access; J6 author "J. Li" |

### 9.2 Claims removed or narrowed

- **Removed:** "evidence-anchored causal-factor graph construction" as a proposed novel combination. It is now an adaptation of AEVS \[X2\].
- **Narrowed:** cross-mission causal linking. The claim is now only *human-judged analogy retrieval*, because X1 already builds cross-accident causation graphs in aviation.
- **Removed:** uncertainty-awareness as a contribution (J6). Abstention is kept as an evaluation dimension.
- **Reworded:** the v1 title, abstract and contributions now lead with the task and benchmark, not the method.
- **Corrected:** the earlier search's J5 year, J3 status and J2 title.

### 9.3 What remains uncertain

- **Full texts of J1–J6 are unread.** Their datasets, metrics, limitations and future work are unknown.
- **Sanyaolu & Josyula (ICSC 2026)** is still read only from its abstract.
- **Literature not searched directly:** IEEE Xplore, Scopus, Web of Science and Chinese-language literature (residual risk to G1–G5).
- **Corpus availability and licences** for the candidate reports are not yet checked.
- **Venues not verified from official pages:** TKDE and TETCI policies; 2027 conference calls for papers and deadlines.
- **Resource estimates are unmeasured.** Every hour and GPU figure is an estimate until Stage 1.

### 9.4 Decisions requiring your approval (gate G0)

- [ ] **Repositioning.** Benchmark + empirical study with an adapted method (recommended), instead of a method paper.
- [ ] **Strategy C** with the three-branch decision rule (Section 8).
- [ ] **AEVS-style extractor as a baseline**, which adds about 5–15 GPU-hours.
- [ ] **Second annotator** named, able to commit about 12–15 hours.
- [ ] **Minimum corpus threshold** of 20 usable missions, below which the work is reported only as a pilot.
- [ ] **Logged IEEE Xplore and Scopus search** as an S3 acceptance criterion.
- [ ] **Optional components R1 and R2**: include them, or drop them to save time.

## Sources consulted

**Opened and read:**

- [Kim & Kim, arXiv 2606.13249](https://arxiv.org/abs/2606.13249) (full text)
- [Xiang *et al.*, *Aerospace* 13(1):16](https://www.mdpi.com/2226-4310/13/1/16) (full text)
- [Yang *et al.*, *Computers* 15(3):178](https://www.mdpi.com/2073-431X/15/3/178) (method, dataset and future-work sections)
- [IEEE Transactions on Reliability, official page](https://rs.ieee.org/publications/transactions-on-reliability.html)
- [IEEE Access submission guidelines](https://ieeeaccess.ieee.org/authors/submission-guidelines/) and [preparing your article](https://ieeeaccess.ieee.org/authors/preparing-your-article/)
- [IEEE T-ASE information for authors](https://www.ieee-ras.org/publications/t-ase/information-for-authors-t-ase)
- [NTRS 20220016425](https://ntrs.nasa.gov/citations/20220016425)

**Bibliographic records (metadata and abstracts):**

- DOI resolver ([doi.org](https://doi.org)) and Crossref citation metadata for every DOI.
- [OpenAlex API](https://api.openalex.org), [Semantic Scholar API](https://api.semanticscholar.org) and the [NTRS API](https://ntrs.nasa.gov).

**Six journal papers (DOI landing pages):**

- [J1](https://doi.org/10.1109/TR.2026.3704165)
- [J2](https://doi.org/10.1109/TR.2026.3696706)
- [J3](https://doi.org/10.1109/TETCI.2026.3688150)
- [J4](https://doi.org/10.1109/TII.2024.3366977)
- [J5](https://doi.org/10.1109/TASE.2024.3359356)
- [J6](https://doi.org/10.1109/TKDE.2026.3700611)

**Search-result summaries only** (not opened; must be confirmed before citing): IEEE PSPB Operations Manual §8.1.7 wording; TKDE and TETCI author policies.
