# MissionMind: Evidence-Anchored, Graph-Augmented Retrieval for Spaceflight Mishap Reports

MissionMind helps investigators find **earlier spaceflight accidents with similar causes** in long official
investigation reports, and drafts **evidence-cited hypotheses** about a new mishap. It reproduces the multi-field hybrid
retrieval method of Kim & Kim (IEEE CASE 2026) as a controlled baseline and adds a **causal-factor graph** whose every
link is tied to a verified, page-located quote.

> **Status (2026-10-14): research prototype.**
> All stages are implemented, tested and audited. Results so far come from a **10-mission pilot with AI-assisted labels**.
> A fully human-labelled evaluation is planned before any paper submission.
> MissionMind **proposes precedent-based hypotheses; it does not establish the root cause of a new mishap.**

**Full guide (27 pages):** [`docs/MissionMind_Project_Guide.pdf`](docs/MissionMind_Project_Guide.pdf) ·
**Summary:** [`docs/PROJECT_SUBMISSION_SUMMARY.md`](docs/PROJECT_SUBMISSION_SUMMARY.md) ·
**Stage reports:** [`docs/research/`](docs/research/)

## What it does

1. **Corpus:** 27 documents (23 official investigation reports or summaries from NASA, ESA, JAXA and ISRO, 22 missions,
   1967–2024), split into 7,117 passages that keep their exact page and character position (OCR for scanned reports).
2. **Baseline (B3):** BM25 + bge-m3 dense retrieval over three report fields (Summary / Causes / Disposition), fused with
   Reciprocal Rank Fusion (k = 60). This is a controlled reproduction and adaptation of the base paper.
3. **Proposed method (P / P2):**
   - an LLM proposes causal factors, and a factor is kept only if its quote is found word-for-word in the report (2,067 of 2,830 kept);
   - the kept factors form a graph of missions linked by shared causal categories (22-category taxonomy);
   - the graph is used as an extra retrieval channel.
4. **Answers:** must cite retrieved passages. Causes are written as *"By analogy with <mission>: <mechanism>"*. The system
   abstains when no grounded answer remains.

## Pilot results (10 missions, AI-assisted labels; exploratory)

| System | nDCG@5 |
|---|---|
| B3 — base-paper method | 0.648 |
| P — proposed (primary comparison) | 0.638 |
| P2 — weighted graph channel (secondary) | 0.678 |
| Graph channel alone (exploratory) | 0.713 |

- **P vs B3:** −0.010, 95% CI [−0.068, +0.049], p = 0.78. **No significant difference.**
- **P2 vs B3:** +0.030, p = 0.65. Not significant.
- **Length bias:** the text-based systems strongly favour missions with long reports (correlation ≈ 0.6); the graph channel did not (≈ 0.03).
- **Support check:** quote verification is necessary but not sufficient. An LLM check judged 16% of verified factors unsupported by their quote; a human review (sheet D4) is pending.
- **Generation:** 0 invalid citations; all generated causes are labelled as precedent-based hypotheses.

## Setup

```
pip install -r requirements.txt          # exact versions: requirements-lock.txt
python -m spacy download en_core_web_sm
ollama pull llama3
copy .env.example .env                   # set NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
```
Also needed: Neo4j 5, Tesseract + Poppler (OCR), and the bge-m3 model (downloaded once).

## Commands

| Step | Command |
|---|---|
| Parse PDFs/HTML into page-aware passages | `python src/pipeline/page_parser.py --run-id ID` |
| Check provenance | `python scripts/validate_passages.py --run-id ID` |
| Apply field maps; load passages into Neo4j | `python scripts/field_map_tool.py apply`; `python scripts/ingest_passages_run.py ID` |
| Extract causal factors; build the factor graph | `python scripts/extract_factors.py --run-id ID`; `python scripts/build_factor_graph.py --run-id ID` |
| Run baselines, P, P2 and ablations | `python scripts/run_retrieval.py --run-id ID --queries FILE --proposed P P2 P-graphonly ...` |
| Evaluate (refuses without complete labels) | `python scripts/evaluate.py --run runs/ID --eval-id EID` |
| Independent audit | `python scripts/audit.py --run runs/ID --eval runs/EID --out runs/AID` |
| Check annotation sheets | `python scripts/check_annotations.py` |
| Tests | `python -m pytest` |

Every run writes its configuration, environment, predictions, metrics and log to `runs/<run_id>/`; runs are never
overwritten.

## Repository layout

| Folder | Contents |
|---|---|
| `src/pipeline/` | Page-aware parsing, OCR, normalisation, field maps |
| `src/retrieval/` | BM25, dense retrieval, RRF, base-paper systems, RCA generation |
| `src/extension/` | Causal-factor extraction and verification, factor graph, proposed method, QA |
| `src/bench/` | Benchmark labels, metrics, statistics |
| `src/graph/`, `src/backend/`, `run_pipeline.py` | Original Stage 1 system (kept as baseline B4) |
| `scripts/` | Runners, evaluators, audit, annotation tools |
| `evalutation/benchmark/` | Human annotation kit (guide, taxonomy, blank sheets), pilot and synthetic labels |
| `docs/` | Project guide, submission summary, stage reports, commit-ID map |
| `runs/` | Every experiment with full records |
| `paper/` | IEEE manuscript skeleton (results pending human labels) |

## Limitations

- The pilot labels are partly written by the AI assistant that built the system, and the pilot has 10 query missions (low power).
- Field maps and the taxonomy are drafts pending human review.
- The local 8B model does not reproduce its answers across sessions; reported outputs are read from saved caches.
- 10 of 23 primary documents are summaries, press releases or slides.

## Base paper

S. Kim and S. Kim, "Multi-Field Hybrid Retrieval-Augmented Generation for Maritime Accident Root Cause Analysis,"
*Proc. IEEE CASE*, 2026, pp. 238–243, doi:10.1109/CASE69030.2026.11704480.
