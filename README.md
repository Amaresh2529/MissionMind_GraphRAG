# 🚀 MissionMind: Graph-RAG Aerospace Failure Analysis

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Neo4j](https://img.shields.io/badge/Neo4j-Graph_Database-008CC1)
![NLP](https://img.shields.io/badge/NLP-spaCy-09A3D5)
![LLM](https://img.shields.io/badge/LLM-Llama_3-000000)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)

> **Project status (2026-10-12): research prototype, Stage 1 (repair + reproducible baseline).**
> No experimental results exist yet. Statements below such as "hallucination-free", "transformer-backed NER",
> `neo4j-graphrag` and RAGAS describe the original plan and are **not** supported by the current code or evidence —
> see `docs/research/05_Stage1_Audit_BasePaper_Plan.md` for the verified state.
>
> **Run (Stage 1):**
> 1. `pip install -r requirements.txt` (exact versions: `requirements-lock.txt`), `python -m spacy download en_core_web_sm`; Tesseract + Poppler for OCR.
> 2. `cp .env.example .env` and point `NEO4J_*` at a **fresh** Neo4j 5 instance; `ollama pull llama3`.
> 3. `python run_pipeline.py --skip-extract-text --docs Mars_Climate_Orbiter` (omit `--docs` for all documents). Artefacts go to `runs/<run_id>/`.
> 4. Query: `python src/backend/rag_pipeline.py "your question"` or `uvicorn --app-dir src backend.main:app`.
> 5. Evaluate: `python evalutation/run_eval.py --data <labelled file>` (the shipped `test_data.json` is a placeholder and is rejected).
> 6. Tests: `python -m pytest -m "not integration"` (no services) / `python -m pytest` (needs the smoke database).

**MissionMind** is an advanced Natural Language Processing (NLP) and Knowledge Graph pipeline designed to automatically extract, link, and analyze aerospace failure modes across multiple international space agencies (NASA, ESA, and ISRO). 

Traditional Retrieval-Augmented Generation (RAG) systems frequently hallucinate or lose causal structural integrity when processing complex engineering and numerical failure data. MissionMind solves this by mapping unstructured, multi-hundred-page incident reports into an explicit **Failure Mode and Effects Analysis (FMEA) Knowledge Graph**, enabling deterministic, hallucination-free LLM diagnostic querying.

---

## ✨ Key Features

*   **Automated Unstructured Ingestion:** Parses dense, unstructured PDF inquiry reports (e.g., Columbia CAIB, ISRO GSLV-F10 FAC, ESA Ariane 5) into clean text streams.
*   **FMEA Entity Recognition:** Utilizes transformer-backed NLP pipelines to isolate critical engineering entities: *Mission Phase, Subsystem, Failure Mode, Root Cause, and Mitigation*.
*   **Cross-Agency Causal Discovery:** Discovers hidden engineering parallels by linking causal failure chains between independent missions (e.g., automatically linking an ISRO telemetry anomaly to a historical ESA flight software failure).
*   **Hybrid Graph-Vector Retrieval:** Combines Cypher graph traversal (for structural exactness) with dense vector search (for semantic context) using `neo4j-graphrag`.
*   **Secure Local Synthesis:** Employs **Llama-3-8B** running locally via Ollama to synthesize retrieved engineering data without leaking sensitive diagnostics to external APIs.

---

## 🏗️ Architecture & Tech Stack

This project is engineered as a modular, pure `.py` backend, designed for seamless DevOps deployment and rigorous academic evaluation.

| Component | Technology / Framework | Function |
| :--- | :--- | :--- |
| **Data Extraction** | `PyMuPDF` (`fitz`) | High-speed text extraction and sanitization from raw mission PDFs. |
| **NLP & NER** | `spaCy` | Dependency parsing and custom Named Entity Recognition for FMEA nodes. |
| **Embeddings** | `Sentence-Transformers` | Generating dense semantic vector representations for text chunks. |
| **Knowledge Graph** | `Neo4j` & `neo4j-graphrag` | Network graph storage and hybrid Cypher/Vector query execution. |
| **Synthesis Engine** | `Llama-3 (8B)` / `Ollama` | Factual, grounded summarization of retrieved failure graphs. |
| **API Backend** | `FastAPI` & `Uvicorn` | RESTful API layer for routing GraphRAG queries. |
| **Evaluation** | `RAGAS` | Automated academic validation of *Faithfulness* and *Context Precision*. |

---

## 📂 Repository Structure

```text
MissionMind_GraphRAG/
├── data/                       # Local data storage (Ignored in Git)
│   ├── raw/                    # Original NASA/ISRO/ESA PDFs
│   ├── processed/              # Cleaned text chunks (.txt)
│   └── kg_triples/             # Extracted NER entities for Neo4j
├── src/                        # Core Python Modules
│   ├── pipeline/               # Extraction & text cleaning scripts
│   ├── models/                 # Embedding generation & NLP rules
│   └── graph/                  # Neo4j database connector & Cypher builders
├── backend/                    # FastAPI web layer
│   ├── main.py                 
│   └── routes/                 # GraphRAG search endpoints
├── evaluation/                 # RAGAS metrics and performance testing
├── requirements.txt            # Project dependencies
└── run_pipeline.py             # Main CLI execution script