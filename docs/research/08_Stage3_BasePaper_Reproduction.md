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

Code under test: commits `0fb4833` (Stage 3 implementation) and `dbcff59` (determinism probe and checker fix). Runs on draft field maps are **DEV runs** (`--allow-draft-fields`); no effectiveness number is reported.

### 5.1 Commands and results

| Step | Command / run | Result |
|---|---|---|
| bge-m3 download (user-approved) | `snapshot_download('BAAI/bge-m3', revision='5617a9f…')`, 10 files | 2.29 GB; `pytorch_model.bin` SHA-256 `b5e0ce34…6aad38` = Hugging Face LFS hash. Loads in fp16 on the RTX 4060 (1,024-dim vectors) |
| Unit tests | `pytest tests/test_retrieval.py` | 10 passed (BM25 vs hand computation, RRF formula, 6-list B3, leave-one-mission-out, determinism, generation packing/citation checks) |
| Full suite | `pytest` | 143 passed |
| BM25-only dev run | `stage3_dev_bm25` (uncommitted tree; DEV) | 3 BM25 systems × 19 queries; checker PASS |
| B0 dev run | `stage3_dev_b0_generation` (uncommitted tree; DEV) | 19/19 valid JSON, 102 items, 0 citations (as intended) |
| Verified run A | `run_retrieval.py --run-id stage3_verified_a --generate B3 B0 --allow-draft-fields` | Exit 0. 10 configurations × 19 queries. Indexing 39 s (bge-m3 encoding of 4,453 passages); search 0.5–9.3 s per configuration for all 19 queries; B3 generation 577 s (≈ 30 s/query) |
| Verified run B | same, `stage3_verified_b` | Exit 0; embedding cache hit; generation served from cache |
| Checker, first version | `verify_stage3.py … --out runs/stage3_verified_check` | **FAIL (C5)**: `generation/B3.jsonl` differed. Cause: only the `cached` flag (A generated, B read the cache); content identical. Kept as evidence |
| Checker, fixed | `… --out runs/stage3_verified_check_r2` | **PASS**: C3, C4, C5 (10/10 prediction files byte-identical; generation identical apart from the cache flag), C6 |
| No-cache generation probe | `MISSIONMIND_GEN_NO_CACHE=1 … --run-id stage3_gen_nocache_probe` | B3: **19/19** answers identical to run A (≈ 1 h apart). B0: only **5/19** identical to the dev run (≈ 2 h apart, same prompts, model 100% on GPU); 9/19 below 0.7 string similarity |
| Artefact check | `runs/stage3_artifact_check` | Stage 1: 14/14 hashes unchanged. Stage 2b passages/fields: none modified after commit `123b614` (SHA-256 recorded) |

### 5.2 Corpus and generation figures (run A)

| Item | Value |
|---|---|
| Indexed units | 4,453 passages: Summary 926, Causes 3,340, Disposition 187 (22 missions, 23 documents) |
| Dev queries | 19 (one per mission with description text; VV17, VV22 and GSLV-F10 have none) |
| B3 generation | 19/19 parsed and schema-valid; 117 items; 226 citations, **9 invalid (4.0%)** (ids not shown in the context); 2 items uncited; 18–24 chunks fit the context (not 40); max prompt 7,534 tokens of 8,192 |
| B0 generation | 19/19 parsed and schema-valid; 102 items; 0 citations |

### 5.3 Descriptive observations (not quality measures)

- **B3 is dominated by the smallest field.** In B3's top 100, Disposition passages make up 861 of 1,900 (45%) although they are 4% of the units; Summary 645, Causes 394. RRF gives each of the 6 lists equal weight, so the top ranks of the 187-passage Disposition index earn as much credit as those of the 3,340-passage Causes index. In the paper every card contributes exactly one chunk per field, so fields are balanced and this effect does not arise. This is a **faithful consequence of the reproduced method on unbalanced fields**. It is reported, not tuned. Whether to add a field-balanced variant is a design decision for Stage 5, to be fixed before any test labels exist.
- Configurations differ substantially. Mean top-10 passage overlap with B3: H-whole 0.60, B1 0.39, B2 0.37, single-field Causes ≈ 0.17–0.20. Top-5 mission overlap: 0.56–0.74.
- Qualitatively plausible mission neighbours appear: OCO↔Glory, Challenger↔Columbia, CRS-7↔Orb-3, the three Vega flights. Very long reports (Columbia, Starliner) appear often in mission rankings, a possible document-length bias to check in Stage 5.

### 5.4 Acceptance criteria

| ID | Status | Evidence |
|---|---|---|
| C1 BM25 correct, deterministic | **Pass** | unit tests; query terms summed in sorted order (no hash-seed effect) |
| C2 RRF = paper formula, k = 60 | **Pass** | unit test |
| C3 All configurations on real corpus; 100 passages with provenance; B3 = 6 lists | **Pass** | `stage3_verified_check_r2` |
| C4 Leave-one-mission-out | **Pass** | 0 leaked passages or missions in 10 × 19 predictions |
| C5 Re-run identical | **Pass** | retrieval byte-identical; generation identical **because of the cache** |
| C6 Generation schema, citations, repeatability | **Pass with finding** | Schema 19/19 for both; 4.0% invalid B3 citations. The model itself is not reproducible across time for B0 (5/19), so reported generations must come from the saved cache |
| C7 Run artefacts | **Pass** | config, env, index stats, queries, predictions, generation, timings, log in every run |
| C8 Deviations recorded | **Pass** | Section 3 (D1–D13) |
| C9 Earlier artefacts unchanged | **Pass** | `stage3_artifact_check` |

### 5.5 Limitations

- No effectiveness results: relevance labels (D2) and answer references (D3) do not exist. The paper's proxy cannot be rebuilt without equivalent metadata.
- Field maps are drafts. Every Stage 3 run is DEV until the maps are reviewed (`load_units(require_status="reviewed")` is the default for non-dev runs).
- Dev queries are taken from each mission's own report summary and can contain the board's causes; they are for plumbing only.
- Generator is an 8B model with an 8k context (18–24 chunks instead of 40); a stronger local generator is a possible Stage 5 ablation.
- bge-m3 load takes about 20–110 s because the repo ships `pytorch_model.bin` (no safetensors).

### 5.6 Next step

Before Stage 4 (the proposed extension), three inputs are needed:
1. The field-map review and held-out field test (from Stage 2b).
2. A decision on the field-imbalance effect (keep the faithful B3 only, or also add a field-balanced B3 variant as a pre-registered secondary baseline).
3. Start of the D2/D3 annotation, without which no retrieval comparison can be reported.
