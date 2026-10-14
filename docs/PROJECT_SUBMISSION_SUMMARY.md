# MissionMind — Project Submission Summary (2026-10-13)

**MissionMind: evidence-anchored, graph-augmented retrieval for cross-mission causal analogy in spaceflight mishap
investigation reports.**

## 1. What was built

| Component | Description | Verified by |
|---|---|---|
| Corpus | 27 documents (23 official investigation reports or summaries from NASA, ESA, JAXA and ISRO covering 22 missions, 1967–2024; 2 replaced versions; 2 distractors), SHA-256 manifest | `data/manifest.json`, `tests/test_manifest.py` |
| Ingestion | Page-aware parsing with OCR for scanned reports; 7,117 passages whose text equals the exact page slice | `scripts/validate_passages.py` (0 mismatches) |
| Fields | Curated per-report field maps (Summary / Causes / Disposition, as in the base paper) | `data/field_maps/` (drafts) |
| Base-paper reproduction | Kim & Kim, IEEE CASE 2026: BM25 + bge-m3 per field, RRF k = 60 (B3), plus the paper's comparison systems (B1, B2, whole-index, single-field) and LLM-only (B0); 13 recorded deviations | `docs/research/08` |
| Proposed method P | LLM-proposed causal factors kept only if their quote is verified in the passage (2,067 of 2,830); 22-category taxonomy; factor graph in Neo4j; graph channel fused with B3; citation-constrained generation with abstention; 6 ablations | `docs/research/09`, `tests/test_extension.py` |
| Evaluation and audit | Pre-registered protocol; nDCG/Recall/MRR, NormRecall@100; paired permutation tests, bootstrap CIs, Holm correction; independent audit (comparability, leakage, provenance, citations, metric recomputation) | `scripts/evaluate*.py`, `scripts/audit.py` |
| Tests | 160 automated tests | `python -m pytest` |

## 2. Results available now

| Evidence | What it shows | Where |
|---|---|---|
| Reproducibility | Retrieval runs byte-identical when repeated; all generation outputs cached | `docs/research/08` |
| End-to-end proof of concept (synthetic labels) | All 17 systems, extraction and QA evaluated and audited. **Not a quality measure** | `docs/research/10` |
| **10-mission pilot (mixed owner / AI-assisted labels)** | P vs B3 nDCG@5 = −0.010 (95% CI [−0.068, 0.049], p = 0.78): **no difference**. Exploratory: factor graph alone 0.713 vs B3 0.648 (not significant). Audit PASS | `docs/research/11` |
| **Review-driven second version (P2), pilot** | Weighted graph channel: nDCG@5 0.678 vs B3 0.648 (not significant); text systems strongly favour long reports (ρ ≈ 0.6), the graph channel does not (ρ ≈ 0.03); P2's answers keep only specific mechanisms | `docs/research/12` |
| Structural findings | B3 over-weights the small recommendation field (45%); B3-bal fixed with √ weights; direct query factors are mostly empty (fixed by evidence-based expansion); P's generation gives only category names (43 of 43 items; corrected from an earlier 21/43 hand count), fixed in P2 | `docs/research/08`–`11` |

## 3. Honest scope statement (please keep in the submission)

- The method is an **adaptation**. Its novelty is the verified, page-anchored causal-factor graph channel and the benchmark design, not the retrieval technique itself.
- **No claim that P outperforms the base-paper method is supported yet.** The pilot shows no significant difference.
- Pilot labels are partly written by the AI assistant that built the system. Synthetic-label results are proof of concept only.
- Fully human labelling (benchmark kit in `evalutation/benchmark/`, about 60–80 h) is planned before the IEEE paper submission. The final runs are scripted and take about 2 hours.

## 4. Where to look

`README.md` (commands) · `docs/research/05`–`11` (stage reports) · `paper/missionmind.tex` (IEEE skeleton; results pending human labels) · `runs/` (every run with config, environment, predictions, metrics and audits).
