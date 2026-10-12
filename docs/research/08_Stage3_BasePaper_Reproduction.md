# MissionMind — Stage 3: Reproduction of the Base-Paper Method

Date: 2026-10-12. Branch `stage1-repair`.

**Objective.** Reproduce, on MissionMind's corpus, the retrieval and generation method of the selected base paper:

> S. Kim and S. Kim, "Multi-Field Hybrid Retrieval-Augmented Generation for Maritime Accident Root Cause Analysis," *IEEE CASE 2026*, pp. 238–243, doi:10.1109/CASE69030.2026.11704480 (full text: arXiv 2606.13249).

The result is baseline **B3**, together with the paper's own comparison configurations (whole-document and single-field indexing; BM25, dense and hybrid) and its LLM-only generation baseline (**B0**). Every deviation is recorded below.

Stage 3 does **not** measure retrieval or answer quality. That needs the human-labelled benchmark (D2/D3), which does not exist yet. The paper's own proxy relevance (keywords, accident type, tribunal location, year from Korean tribunal metadata) has no equivalent metadata in our corpus.

## 1. Method as stated in the paper (re-read 2026-10-12)

| Element | Paper |
|---|---|
| Units | Each card's text is split into three fields (Summary, Causes, Disposition). Each field is one chunk linked to its case ID (37,007 chunks, mean 283 characters) |
| Sparse | BM25 per field; implementation, tokeniser and k1/b **not stated** |
| Dense | BAAI/bge-m3 per field; dense/sparse/multi-vector mode and normalisation **not stated** |
| Query | "a free-text description of a vessel incident" |
| Fusion | RRF over 6 rankings (3 fields × BM25/dense): RRFScore(c) = Σ_r 1/(k_rrf + rank_r(c)), k_rrf = 60 |
| Retrieval evaluation | k = 100 chunks; NormRecall@100, nDCG@100 against a metadata proxy |
| Generation | Top 40 chunks by RRF score; each annotated with case ID and field type; Qwen3-Next-80B-A3B-Instruct; temperature 0; strict JSON via system prompt; prompt text **not published** |
| Baselines | Whole-document indexing; single-field indexing (Summary only, Causes only), each with BM25/dense/hybrid. LLM-only generation (same model and prompt, no context) |
| Split | 70/15/15 train/validation/test; index built on train |

## 2. MissionMind implementation

| Component | File |
|---|---|
| BM25 (self-contained, Okapi, k1 = 1.2, b = 0.75, lowercase `[a-z0-9]+` tokens) | `src/retrieval/bm25.py` |
| Dense bge-m3 (dense vectors only, L2-normalised, fp16 on GPU, embedding cache) | `src/retrieval/dense.py` |
| RRF, k = 60, deterministic tie-break | `src/retrieval/fusion.py` |
| Corpus: primary passages with curated field ≠ other; description→Summary, analysis→Causes, recommendations→Disposition | `src/retrieval/corpus.py` |
| Configurations B1, B2, H-whole, SF-summary-{bm25,dense,hybrid}, SF-causes-{…}, B3; leave-one-mission-out | `src/retrieval/systems.py` |
| Automatic dev queries (not a benchmark) | `src/retrieval/queries.py` |
| Grounded RCA generation (B3) and LLM-only (B0): shared JSON schema, citation checks, cache | `src/retrieval/rca_generation.py` |
| Runner | `scripts/run_retrieval.py` |
| Tests | `tests/test_retrieval.py` |

## 3. Deviations from the paper

| # | Paper | MissionMind | Reason |
|---|---|---|---|
| D1 | Native fields of short tribunal cards | Curated field maps over long reports (Stage 2b), passages of 150–300 words; front/back matter (`other`) not indexed | Mishap reports have no native field structure |
| D2 | "Whole document" = the card's 3 fields concatenated into one chunk | One index over all field passages | Reports are up to 300 pages; a single chunk per report is meaningless |
| D3 | BM25 parameters unstated | Okapi, k1 = 1.2, b = 0.75, simple tokeniser, query terms counted once | Lucene/Elasticsearch defaults; not tuned |
| D4 | bge-m3 mode unstated | Dense output only, normalised, max_seq_length 1024, fp16 | Paper names bge-m3 for dense retrieval |
| D5 | Ranked-list depth unstated | Each list cut at 1,000 before fusion | Corpus has 4,453 units; depth affects only RRF tails |
| D6 | Query = incident description | Dev: first 300 words of the query mission's own description field; later: human-written queries (D2/D3) | No benchmark queries yet |
| D7 | Train/test split of cases | Leave-one-mission-out: all passages of the query's mission(s) removed before ranking | 22 missions; every mission is both query and precedent |
| D8 | Evaluated at chunk level only | Chunk ranking (k = 100) **plus** mission ranking by each mission's best-ranked passage | The MissionMind task (T1) ranks missions |
| D9 | Generator Qwen3-Next-80B | llama3 8B (Q4_0) via Ollama, temperature 0, seed 42 | Local hardware (8 GB GPU) |
| D10 | Top 40 chunks in context | At most 40, packed in rank order up to 4,200 words (8,192-token window); number used is recorded | llama3 context limit |
| D11 | Annotation: case ID + field | Case ID (mission), document, field, page | Page-level citation checks |
| D12 | Prompt unpublished | Own prompt and JSON schema (`rca_generation.py`) | — |
| D13 | Distractors: none | The 2 ISRO distractor reports are not indexed in Stage 3 | They have no fields; whether to include them is a Stage 5 design decision |

## 4. Acceptance criteria

| ID | Criterion |
|---|---|
| C1 | BM25 scores equal hand-computed values; ranking deterministic (unit tests) |
| C2 | RRF equals the paper's formula with k = 60 (unit test) |
| C3 | All paper configurations run on the real corpus: every query returns 100 passages with provenance (doc, page, field) and a mission ranking; B3 fuses exactly 6 lists |
| C4 | Leave-one-mission-out holds in every saved prediction |
| C5 | Re-running retrieval gives byte-identical predictions |
| C6 | Generation: B3 grounded and B0 with the same schema. JSON parse rate, schema validity and citation validity are recorded; a repeated run gives identical outputs |
| C7 | Each run saves config, env, index statistics, queries, predictions, timings, log |
| C8 | Deviations recorded (Section 3) |
| C9 | Earlier artefacts unchanged (Stage 1 hashes; Stage 2b passages and fields) |

## 5. Verification report

*(Filled in after execution.)*
