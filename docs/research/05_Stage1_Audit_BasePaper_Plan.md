# MissionMind — Current-State Audit, Base-Paper Selection and Stage 1 Plan

Date: 2026-10-12 · Repository state audited: commit `5d0219e` (working tree clean apart from `docs/`).
Everything below marked **verified** was confirmed by executing code or querying data in this session; nothing is taken from earlier reports without re-checking.

---

## 1. Current-state audit (Deliverable 1)

### 1.1 Environment (verified)

| Item | Observed |
|---|---|
| Python | 3.14.2 (user site-packages) |
| Key packages | spacy 3.8.13, sentence-transformers 5.7.0, neo4j driver 6.2.0, fastapi 0.129.0, torch 2.14.0+cu126 |
| GPU | RTX 4060 Laptop, 8 GB, CUDA available |
| Ollama | server 0.32.5 running; one model: `llama3:latest` (Q4_0, 4.4 GB) |
| Docker | daemon 29.1.3 running; image `neo4j:5` present |
| Neo4j | container `neo4j-local` (neo4j 5.26 community, created 2026-08-16) — stopped; started in this session for **read-only** inspection |
| OCR | Tesseract 5.5.3 and Poppler 26.02 installed (OCR fallback is usable) |

### 1.2 Entry points and data flow (verified)

`run_pipeline.py` → `pipeline/pdf_loader.process_all_pdfs` (PDF → `data/processed/*.txt`) → `pipeline/text_chunker.process_and_chunk` (→ `data/processed/chunks/*_chunks.json`) → `graph/neo4j_loader.ingest_chunks_to_neo4j` (Chunk nodes + MiniLM vectors + `chunk_vector_index`) → `graph/graph_builder.build_knowledge_graph` (NER gate → Llama-3 fallback → Mission/FailureMode/Subsystem/RootCause + `SIMILAR_ROOT_CAUSE`). Query side: `src/graph/retriever.py` (FastAPI app) and `src/backend/rag_pipeline.py` (CLI). Evaluation: `evalutation/run_eval.py`.

### 1.3 Component status

| Component | Status | Evidence (this session) |
|---|---|---|
| PDF extraction + OCR fallback | Works; output on disk | Imports OK; Tesseract/Poppler present. Challenger PDF is a 261-page scan with 22 near-empty text pages |
| Text cleaning | Works, with defects | Ligatures removed by ASCII stripping; page numbers and structure discarded (no page field in any chunk JSON) |
| Chunking | Works | 2,175 chunks on disk |
| Neo4j ingestion | Works but **stale-prone** | Skips existing chunk IDs and never updates text: 449 of 596 Challenger chunk texts in the DB differ from the current files; DB holds 2 chunks (`Challenger_596/597`) that no longer exist on disk |
| NER gate | Runs; 0.6% acceptance | Measured earlier on all 2,175 chunks (13 pass); code unchanged since |
| Graph construction | **Was run previously; resulting graph is contaminated** | See 1.4 |
| Retriever / API / CLI | **Broken** | `import graph.retriever` → `ImportError: cannot import name 'GraphRAGRetriever' … circular import`; `python src/backend/rag_pipeline.py` fails the same way |
| Package layout | **Broken (new finding)** | Empty root `backend/` package shadows `src/backend/`: `import backend` resolves to `backend/__init__.py` |
| Evaluation runner | **Broken** | `python evalutation/run_eval.py` → `ImportError: cannot import name 'extract_failure_data'`; `test_data.json` is a placeholder template |
| Citation tracking | **Not implemented** | No page/offset provenance anywhere in the data model |
| Baselines, annotations, results files | **Not implemented** | No results/log files in the repository |

### 1.4 Corrections to earlier audit findings

| Earlier finding | Correction | Evidence |
|---|---|---|
| "No recorded run; nothing shows the pipeline completed" | **Partly wrong.** A graph exists in `neo4j-local`: 2,177 Chunk, 161 FailureMode, 192 RootCause, 133 Subsystem, 5 Mission, 7 Document nodes; 1,681 MENTIONS, 1 SIMILAR_ROOT_CAUSE. What is missing is logs and result files, not a run | Read-only Cypher counts |
| (new) Graph validity | **The existing graph is contaminated and must not be used for experiments.** 5 FailureMode nodes without `extraction_method` come from hard-coded `EXTRACTION_RULES` in commit `7d9ce24` (one keyword such as "alignment", "parachute", "seal" or "metric" asserted a whole pre-written mission/cause record). They are linked to 1,493 chunk mentions, including **all** 245 annual-report chunks that carry any mention (95 → Ariane 5 "64-bit to 16-bit Overflow"; 89 → ExoMars "Premature Parachute Jettison"; 76 → Challenger "O-ring Seal Erosion"; 28 → MCO; 8 → Columbia; counts saved in `runs/_legacy_db_snapshot/neo4j_local_counts.json`). Re-running the current code never removed them because every write is a `MERGE` | Cypher queries; `git show 7d9ce24:src/graph/graph_builder.py` |
| "material failure related failure" is the only cross-mission FailureMode collision | **Two collisions** in the real graph: that one and `O-ring erosion` (Challenger + Columbia). The single similarity edge links `primary O-ring seal failure` ↔ `poor sealing action, foam debris problems, O-ring erosion` at 0.6521, just above the uncalibrated 0.65 threshold | Cypher |
| Extraction is "99.4% LLM" (predicted) | **Consistent with the stored graph**: of 163 Mission→FailureMode links, 151 are `llm`, 7 `ner`, 5 legacy (None) | Cypher |
| Everything else in the v1 audit (broken retriever, broken eval import, corpus composition, ligatures, OCR noise, no page provenance, first-match root-cause bias, case-sensitive gazetteer) | **Confirmed** | Execution and inspection above |

**Consequence.** The old database is preserved untouched as evidence. All new work uses a separate, freshly created database so earlier results are not overwritten and contamination cannot leak into experiments.

---

## 2. Base-paper selection (Deliverable 2)

### 2.1 Candidates examined

| Criterion | **Kim & Kim (IEEE CASE 2026)** | Xiang et al. (*Aerospace* 2026) | Xie et al. — HybridRAG (*Sci. Rep.* 2025) | Yang et al. — AEVS (*Computers* 2026) | Ai et al. — KEO (arXiv 2025) | An et al. — ADRAG (IEEE TR 2026) |
|---|---|---|---|---|---|---|
| Bibliography | S. Kim, S. Kim, "Multi-Field Hybrid RAG for Maritime Accident Root Cause Analysis," pp. 238–243 | X. Xiang, X. Chen, J. Yang, vol. 13, no. 1, Art. 16 | X. Xie, X. Tang, S. Gu, L. Cui, vol. 15, Art. 17752 | Y. Yang, G. Chen, B. He, Y. Zhao, vol. 15, no. 3, Art. 178 | K. Ai, J. A. Karr, M. Jiang, N. V. Chawla, C. Wang, arXiv:2510.05524 | J. An *et al.*, vol. 75, pp. 2523–2535 |
| Venue verified | IEEE conference (Crossref + DOI) | MDPI journal | Springer Nature journal | MDPI journal | Preprint | IEEE journal |
| DOI | 10.1109/CASE69030.2026.11704480 | 10.3390/aerospace13010016 | 10.1038/s41598-025-02643-2 | 10.3390/computers15030178 | 10.48550/arXiv.2510.05524 | 10.1109/TR.2026.3704165 |
| Text examined | **Full** (arXiv 2606.13249) | **Full** | **Full** | Method, data, future-work sections | **Full** | Abstract only |
| Task | Retrieve precedent accident cases + generate RCA from official investigation reports | Extract causes from accident reports; causation KG; cross-accident chain analysis | Aircraft fault diagnosis QA | Grounded triple extraction | KG-RAG QA over maintenance records | Avionics diagnosis from datasheets |
| Technical similarity to MissionMind | **High for T1/T2** (case retrieval over investigation reports + grounded RCA) | **High for graph construction**; no retrieval task | Medium (graph + BM25 + vector fusion) but different task | High for extraction component only | Medium | Medium (unverifiable) |
| Architecture reproducible? | **Yes**: per-field BM25 + bge-m3, RRF k = 60, fully specified | Partly: depends on DeepSeek-V3.1 (671B) via API and custom schema | **No**: agentic planner with qwen2-72b; fusion not specified; trained BERT extractor | Yes in principle (prompts in paper) | Yes (code released) | No |
| Data | KMST reports (Korean; not used by us) | NTSB (public) | Private UAV data (not public) | Public benchmarks | OMIn (FAA, 1–3 sentence records) | Private |
| Evaluation | NormRecall@100, nDCG@100 on a metadata proxy; ROUGE-L, SBERT, LLM judge; tag accuracy/F1 | Manual accuracy on 50 reports; no recall, no IAA, no baselines | Token F1, hallucination rate, latency, RAM on 100 queries; **authors state no significance tests were applied** | Triple P/R/F1 vs references | LLM judges only (GPT-4o, Llama-3.3-70B); ROUGE | Not known |
| Documented limitations | Proxy labels; rule-based tags; judge bias | Coarse schema; graph lacks source links (future work) | "Schema ambiguities and data quality" | Sentence-level only; document-level and RAG integration future work | LLM-judge not valid/reliable; needs human evaluation | Unknown |
| Adaptation needed | Fields must be recovered from unstructured reports; English; human relevance labels replace the proxy | Local LLM instead of 671B API; spaceflight schema | Most components would be re-invented | Extend to document level + pages | Long documents instead of short records | — |
| **Suitability as primary base** | **Best** | Strong *competing/supporting* work | Supporting (architecture precedent) | Supporting (extraction method) | Supporting (finding on query types) | Related work only |

### 2.2 Decision

**Primary base paper: Kim & Kim, IEEE CASE 2026 (retained after re-assessment, not by default).** Reasons, in order of weight:

1. **It matches the task MissionMind actually evaluates.** T1 (retrieve causally analogous past cases) and T2 (grounded RCA explanation) are precedent retrieval and precedent-grounded generation over official investigation reports — exactly its problem formulation.
2. **It is the only candidate whose core method can be reproduced faithfully on local hardware** (BM25, bge-m3, RRF with k = 60, per-field indexing, top-k settings and metric formulas are all stated).
3. **It cleanly separates baseline from extension.** Its method is graph-free, so anything graph-based in MissionMind is unambiguously our extension, measured against it — and it names graph-based reasoning as future work.
4. Its stated limitations (proxy labels, rule-based tags, judge bias) are exactly what our human-labelled benchmark addresses.

**Honest trade-off.** Xiang *et al.* is technically closer on causal-graph construction, but (a) it is not IEEE, (b) its pipeline depends on a 671B-parameter API model, and (c) it has no retrieval task to reproduce. It is positioned as the closest *competing* work and its causation schema informs ours. HybridRAG is closest architecturally but is not reproducible (private data, 72B agentic planner, unspecified fusion, no significance testing).

### 2.3 What MissionMind reproduces from the base paper (B3)

| Base-paper element | Reproduced as | Recorded deviation |
|---|---|---|
| Field-wise indexing (Summary / Causes / Disposition) | Pseudo-fields recovered by section segmentation (Narrative / Analysis-Findings / Causes / Recommendations) | Fields are inferred, not native; accuracy reported |
| Sparse retrieval BM25 per field | Same | Tokeniser and BM25 parameters recorded |
| Dense retrieval bge-m3 per field | Same model | Precision/quantisation recorded |
| RRF over all field × method rankings, k_rrf = 60 | Same | k tuned on dev only if the paper's procedure is followed; default 60 kept |
| Precedent-grounded generation, temperature 0, JSON output | Same structure with a local 7–8B model | Generator differs (paper: Qwen3-Next-80B) |
| Evaluation with metadata proxy | Reproduced **only** for RQ5 (proxy vs human agreement) | Human labels are the reference standard |
| Chunk annotation with case ID + field type | Same, plus page number | Page added |

What is **not** taken from the base paper (MissionMind extension): causal-factor extraction with evidence verification, the causal-factor graph channel, page-level citation verification, abstention, human-labelled benchmark.

---

## 3. Research alignment (Deliverable 3)

Working title retained: *MissionMind: A Benchmark and Evidence-Anchored Graph-Augmented Retrieval Study for Cross-Mission Causal Analogy in Spaceflight Mishap Investigation Reports.*

| RQ | Answerable with the current corpus (5 failure reports)? | Requirement |
|---|---|---|
| RQ1 Evidence-anchored extraction reliability vs recall cost | **Partly** — extraction can be measured on passages of 5 long reports once D1 labels exist | D1 annotations (~350 passages; ~150 feasible from current reports) |
| RQ2 Graph vs base-paper retrieval for cross-mission analogy | **No** — with 5 missions each query has only 4 candidates; mission-level ranking metrics are meaningless | ≥ 20 missions + D2 labels |
| RQ3 Graph information beyond BM25/dense/hybrid | **Passage-level only, weakly** | D3 questions; more missions for cross-mission categories |
| RQ4 Page-level verifiable evidence | **Yes, after Stage 2** (page provenance) | Page-aware passages; citation checker |
| RQ5 Automatic metrics vs human judgement | **Partly** | Human ratings on a sample |

**Fundamental risk stated plainly:** the central claim (RQ2) cannot be tested until the corpus reaches about 20 missions. Stages 1–3 below do not depend on that, so work proceeds; corpus expansion must start in parallel (Stage 2 of the v2 roadmap) or the study reduces to a pilot.

---

## 4. Architecture and implementation plan (Deliverable 4)

| # | Pipeline step | Existing file | Action | Stage |
|---|---|---|---|---|
| 1 | Ingestion + source verification | `src/pipeline/pdf_loader.py` | Keep; add manifest + checksums | 2 |
| 2 | PDF parsing + OCR fallback | `src/pipeline/pdf_loader.py`, `text_cleaner.py` | Keep; add NFKC, keep page numbers | 2 |
| 3 | Page-aware chunking + metadata | `src/pipeline/text_chunker.py` | Extend: page/offset fields, section path | 2 |
| 4 | Causal-factor extraction | `src/models/ner_model.py`, `src/graph/graph_builder.py` | **Stage 1: expose `extract_failure_data()` unchanged in behaviour** (B4 = current system); new extractor later | 1 → 4 |
| 5 | Evidence verification | — | New module `src/models/evidence_verifier.py` | 4 |
| 6 | Normalisation / relation validation | `graph_builder.py` | Replace string MERGE with canonical IDs | 4 |
| 7 | KG storage | `src/graph/neo4j_connector.py`, `neo4j_loader.py` | Keep connector; loader gets refresh-on-change | 1 (config) / 2 |
| 8 | BM25 / dense / hybrid retrieval | — (dense only via Neo4j index) | New `src/retrieval/` (BM25, bge-m3, RRF) = B1–B3 | 3 |
| 9 | Graph-augmented retrieval | `src/graph/retriever.py` | **Stage 1: restore `GraphRAGRetriever`** (vector + graph facts = B4); graph channel later | 1 → 4 |
| 10 | Grounded generation | `src/backend/rag_pipeline.py`, `src/backend/main.py` | **Stage 1: repair imports, single shared prompt module** | 1 |
| 11 | Citation verification | — | New, after page provenance | 2 → 4 |
| 12 | Evaluation + benchmarking | `evalutation/metrics.py`, `run_eval.py` | **Stage 1: repair runner, input validation, run logging** | 1 |

Principles: no new frameworks in Stage 1; behaviour of the current extractor is preserved so it can serve as baseline B4; every run writes to its own `runs/<run_id>/` directory; the legacy contaminated database is never written to.

## 5. Baselines (summary; full plan in Proposal v2 §13)

B0 LLM-only · B1 BM25 · B2 dense · B3 base-paper multi-field hybrid RRF · B4 repaired current MissionMind (vector + unverified graph facts) · B5 LightRAG (if feasible on 8 GB) · P evidence-anchored graph-augmented retrieval. Each writes `predictions.jsonl`, `metrics.json`, `config.yaml`, `env.json` and `log.txt` under `runs/<run_id>/`. Human labels are the reference; proxies are reported only for RQ5. No baseline is run on test labels before the test set is frozen.

---

## 6. Stage 1 execution plan (Deliverable 5)

**Objective:** a minimum working, reproducible pipeline on a small subset of the current corpus, with the query and evaluation entry points repaired, tests in place, and every run logged. No corpus expansion, no new graph method.

| ID | Acceptance criterion | How verified |
|---|---|---|
| A1 | `import graph.retriever`, `backend.main`, `backend.rag_pipeline` succeed | pytest import test |
| A2 | `evalutation/run_eval.py` starts, validates its input, and rejects placeholder data with a clear error | pytest + manual run |
| A3 | `extract_failure_data()` exists and returns the schema `metrics.extraction_metrics` expects, with behaviour identical to the build loop | unit test with mocked LLM |
| A4 | Unit tests pass without Neo4j/Ollama | `pytest -m "not integration"` |
| A5 | Configuration in one place (env vars + `.env.example`); no hard-coded credentials in active code | grep + test |
| A6 | Dependencies pinned to the verified environment | `requirements-lock.txt` |
| A7 | End-to-end smoke run on a subset (Ariane 5 + Mars Climate Orbiter) against a **fresh** Neo4j instance: ingestion → graph build → hybrid query → answer | integration test + run artefacts |
| A8 | Run artefacts saved: config, environment, model identifiers, timings, graph statistics, query outputs, log | files in `runs/<run_id>/` |
| A9 | Legacy `neo4j-local` database unchanged | node/relationship counts before = after |

Commands are listed in the Stage 1 verification report (§7), with their actual outputs.

---

## 7. Stage 1 verification report (Deliverable 7)

**Objective.** Repair the minimum working pipeline and make it reproducible, without changing the extraction method (the repaired system is baseline B4).
**Code under test:** commits `91e3ca4` (repairs) and `40cf711` (query-check script) on branch `stage1-repair`. All verified runs record `git_dirty: false`.

### 7.1 Files changed

| File | Change | Reason |
|---|---|---|
| `src/graph/retriever.py` | Restored `GraphRAGRetriever` (vector search + graph facts, from `7d9ce24`), plus `aggregate_rows`, `build_context_text`, `related_failures` | File had been overwritten by the API (circular import) |
| `src/backend/main.py` | FastAPI app moved here; lazy retriever; no credentials | Old content was a duplicate with hard-coded password |
| `src/backend/generation.py` (new) | One prompt template and one Ollama call (temperature 0, seed 42) | Three divergent prompt copies existed |
| `src/backend/rag_pipeline.py`, `src/backend/__init__.py` | Use shared retriever and generation | Import repair |
| `backend/` (root, 4 empty files) | Removed | Shadowed `src/backend` |
| `src/graph/graph_builder.py` | `extract_failure_data()` (same logic as the build loop, which now calls it); document filter; per-chunk records; stats returned; seed passed to the LLM | Eval import; run artefacts |
| `src/graph/neo4j_loader.py` | Config-driven; document filter; vector dimension from embedder; stats returned | Reproducibility |
| `src/graph/neo4j_connector.py` | Config-driven; no default password; server notifications off | Security; log noise |
| `src/config.py`, `src/runlog.py`, `.env.example` (new) | Central settings; per-run directories with config, env, model digest, timings, log | Reproducibility |
| `evalutation/run_eval.py` | Uses the real retriever/extractor; input validation; CLI; run directories | Was broken and duplicated retrieval logic |
| `evalutation/fixtures/stage1_smoke_fixture.json` (new) | 3 chunks + 2 queries labelled by the assistant, marked **not a benchmark** | Plumbing check only |
| `run_pipeline.py` | `--docs`, `--run-id`, `--skip-extract-text`; run artefacts | Subset smoke runs |
| `scripts/stage1_query_check.py` (new) | CLI + HTTP API check | Query-side acceptance |
| `tests/` (new, 44 tests), `pytest.ini` | Unit + integration tests | A1–A7 |
| `requirements.txt`, `requirements-lock.txt` (new) | Missing packages added; exact versions pinned | Dependency repair |
| `README.md` | Status block; unsupported claims flagged, not deleted | Accuracy |

### 7.2 Commands executed and actual results

| Step | Command | Result |
|---|---|---|
| Unit tests | `python -m pytest -m "not integration"` | 41 passed |
| Fresh DB | `docker run … neo4j-missionmind-stage1` on ports 7688/7475, own volume | Neo4j 5.26.29, 0 nodes |
| Smoke run (failed) | `run_pipeline.py --run-id stage1_smoke_pipeline …` | **Failed**: `'_Tee' object has no attribute 'isatty'` (bug in new run logger). Fixed and regression test added; no DB writes occurred. Kept in `runs/stage1_smoke_pipeline/FAILED.txt` |
| Trial runs | `stage1_smoke_pipeline_r2`, `stage1_eval_plumbing_trial` | Passed on uncommitted tree; labelled TRIAL, not for reporting |
| Verified run A / B | DB emptied, then `python run_pipeline.py --skip-extract-text --run-id stage1_verified_pipeline_{a,b} --docs "Ariane_5_Flight_501_Failure_Inquiry_Board_Report." Mars_Climate_Orbiter` | Both exit 0. Ingestion ~10–11 s; graph build ~156 s. 96 chunks: 3 NER, 16 LLM, 77 no data, 0 LLM failures; 17 FailureMode, 16 Subsystem, 18 RootCause, 0 similarity edges |
| Determinism | Compare `extraction_records.jsonl` of A and B | **96/96 identical** back to back |
| Full suite | `python -m pytest -v` | **44 passed** (41 unit + 3 integration) — `runs/stage1_verified_tests/pytest_all.txt` |
| Eval runner | `python evalutation/run_eval.py --data evalutation/fixtures/stage1_smoke_fixture.json --run-id stage1_verified_eval_plumbing` | Exit 0; all three tracks wrote predictions and metrics |
| Independent recomputation | Script recomputing detection counts, recall and MRR from the saved predictions | Matches reported metrics exactly |
| Query paths | `python scripts/stage1_query_check.py --run-id stage1_verified_query` | CLI answer produced; API `GET /` 200, `POST /query` 200 |
| Legacy DB | Counts vs `runs/_legacy_db_snapshot/neo4j_local_counts.json` | Unchanged |

### 7.3 Acceptance criteria

| ID | Criterion | Status |
|---|---|---|
| A1 | Retriever, API and CLI import | **Pass** |
| A2 | Eval runner starts, validates, rejects placeholder data (exit 2) | **Pass** |
| A3 | `extract_failure_data()` returns the metrics schema; same path as graph build | **Pass** (unit tests with mocked LLM; build loop calls it) |
| A4 | Unit tests pass without services | **Pass** (41) |
| A5 | Single configuration; no hard-coded password in active code | **Pass** (test scans `src/`, `evalutation/`, `run_pipeline.py`) |
| A6 | Dependencies pinned | **Partial** — versions pinned from the verified environment; installation into a clean virtual environment was **not** tested |
| A7 | End-to-end smoke run on a fresh DB, including query and answer | **Pass** |
| A8 | Run artefacts saved (config, env incl. model digest, timings, stats, records, logs) | **Pass** |
| A9 | Legacy `neo4j-local` unchanged | **Pass** |

### 7.4 Observations (facts from this stage; none is a research result)

1. **Cross-session LLM non-determinism.** Back-to-back runs were identical, but the earlier trial run (same extraction code, earlier Ollama session) differed on 5/96 records (e.g. `Ariane…_15`: no data vs "Inappropriately handled exception"). Temperature 0 + seed does not guarantee reproducibility across sessions. **Consequence for later stages:** freeze LLM outputs as versioned artefacts and reuse them across experiments; report extraction variance from repeated runs.
2. **Dense retrieval misses the causal passages on the plumbing queries.** Exact-cosine re-ranking confirmed the Neo4j index result: the labelled Ariane chunks rank 5th and 20th, the MCO root-cause chunk 45th of 96. The API answer for "Why was the Mars Climate Orbiter lost?" consequently names the wrong root cause. Two queries are an anecdote, not evidence; they motivate the planned BM25/multi-field baselines.
3. **LLM-judge scores on 2 questions with the generator as judge** are recorded but carry no weight (self-preference, n = 2).
4. **Graph defect visible in the fresh build:** `FailureMode.extraction_method` is overwritten by the last chunk that merges into the node (3 NER chunks produced a single `ner`-labelled node). Recorded for Stage 4 (canonicalisation), unchanged here to keep B4 faithful.

### 7.5 Behaviour changes relative to the original code (recorded deviations)

- One shared generation prompt (asks for source ids, allows "not in context") with temperature 0 and seed 42 for API, CLI and eval — previously three prompt variants and Ollama's default temperature.
- LLM extraction call now passes `seed` (temperature 0 was already set).
- Retriever returns one entry per chunk with a `facts` list (previously one row per chunk×fact) and adds `related_failures`; API response schema changed accordingly.
- Answer track compares chunk-only vs graph-fact context under the same prompt (previously two different prompts).
- `NEO4J_PASSWORD` must be set; no fallback.

### 7.6 Remaining limitations (carried to Stage 2+)

Ingestion skips existing chunks (stale text in reused DBs) · no page or offset provenance · ligature loss from ASCII stripping · OCR noise in the Challenger scan · case-sensitive gazetteer · first-match root-cause labels · MERGE-by-raw-string canonicalisation · corpus of 5 failure reports (RQ2 untestable) · no human-labelled data · clean-environment install untested · folder name `evalutation` kept to avoid breaking paths.

### 7.7 Next step (awaiting approval)

**Stage 2 — ingestion and provenance:** page-aware parsing (page numbers and character offsets per passage), NFKC before filtering, refresh-on-change ingestion, OCR quality sampling on Challenger, pseudo-field segmentation with a 100-section accuracy check, and a corpus manifest with checksums. In parallel, start the corpus search (≥ 20 missions), because RQ2 depends on it.
