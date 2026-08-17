"""
metrics.py

Reusable evaluation metrics for MissionMind Graph-RAG:
  1. Extraction quality  - how accurate is graph_builder.py's LLM extraction vs a hand-labeled gold set
  2. Retrieval quality   - Recall@k / Precision@k / MRR for the vector search step
  3. Answer quality      - LLM-judge rubric scoring, used to compare Graph-RAG vs plain vector RAG

These are pure functions with no side effects (no Neo4j calls baked in) so they can be
unit-tested and reused from run_eval.py or a notebook.
"""

import json
import statistics
from sentence_transformers import SentenceTransformer, util
import ollama

_embedder = None  # lazy-loaded, one instance shared across calls


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedder


def _semantic_match(predicted: str, gold: str, threshold: float = 0.6) -> bool:
    """True if two short text fields (e.g. root_cause phrasings) are close enough in meaning.
    Exact string match is too strict for LLM-generated text that paraphrases the source."""
    if predicted is None or gold is None:
        return predicted == gold
    if predicted.strip().lower() == gold.strip().lower():
        return True
    embedder = _get_embedder()
    emb = embedder.encode([predicted, gold], show_progress_bar=False)
    score = util.cos_sim(emb[0], emb[1]).item()
    return score >= threshold


# ---------------------------------------------------------------------------
# 1. Extraction quality (graph_builder.py)
# ---------------------------------------------------------------------------

def extraction_metrics(predictions: list[dict], gold: list[dict]) -> dict:
    """
    Compares graph_builder.py's per-chunk extraction against a hand-labeled gold set.

    predictions / gold: lists of dicts, one per chunk:
        {"chunk_id": ..., "has_failure_data": bool, "mission": str|None,
         "subsystem": str|None, "failure_mode": str|None, "root_cause": str|None}

    Returns detection precision/recall/F1 (did it correctly say "failure described here
    or not") plus field-level accuracy on chunks both sides agree contain failure data.
    """
    gold_by_id = {g["chunk_id"]: g for g in gold}

    tp = fp = fn = tn = 0
    field_correct = {"mission": 0, "subsystem": 0, "failure_mode": 0, "root_cause": 0}
    field_total = 0

    for pred in predictions:
        g = gold_by_id.get(pred["chunk_id"])
        if g is None:
            continue

        pred_has = pred.get("has_failure_data", False)
        gold_has = g.get("has_failure_data", False)

        if pred_has and gold_has:
            tp += 1
        elif pred_has and not gold_has:
            fp += 1
        elif not pred_has and gold_has:
            fn += 1
        else:
            tn += 1

        if pred_has and gold_has:
            field_total += 1
            for field in field_correct:
                if _semantic_match(pred.get(field), g.get(field)):
                    field_correct[field] += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    field_accuracy = {
        field: (count / field_total if field_total else 0.0)
        for field, count in field_correct.items()
    }

    return {
        "detection_precision": round(precision, 3),
        "detection_recall": round(recall, 3),
        "detection_f1": round(f1, 3),
        "field_accuracy": {k: round(v, 3) for k, v in field_accuracy.items()},
        "n_gold_positive": tp + fn,
        "n_predicted_positive": tp + fp,
    }


# ---------------------------------------------------------------------------
# 2. Retrieval quality (vector search step)
# ---------------------------------------------------------------------------

def retrieval_metrics(retrieved_ids: list[str], relevant_ids: set[str], k: int = 3) -> dict:
    """
    Standard IR metrics for one query.
    retrieved_ids: ranked chunk ids returned by the vector search, best-first.
    relevant_ids:  the set of chunk ids that are actually relevant to the query
                   (from your test set).
    """
    top_k = retrieved_ids[:k]
    hits = [cid for cid in top_k if cid in relevant_ids]

    precision_at_k = len(hits) / k if k else 0.0
    recall_at_k = len(hits) / len(relevant_ids) if relevant_ids else 0.0

    reciprocal_rank = 0.0
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            reciprocal_rank = 1.0 / rank
            break

    return {
        "precision_at_k": round(precision_at_k, 3),
        "recall_at_k": round(recall_at_k, 3),
        "reciprocal_rank": round(reciprocal_rank, 3),
    }


def aggregate_retrieval_metrics(per_query_metrics: list[dict]) -> dict:
    """Averages retrieval_metrics() output across all test queries (gives you Mean Reciprocal Rank etc.)."""
    if not per_query_metrics:
        return {}
    keys = per_query_metrics[0].keys()
    return {
        f"mean_{key}": round(statistics.mean(m[key] for m in per_query_metrics), 3)
        for key in keys
    }


# ---------------------------------------------------------------------------
# 3. Answer quality (for the Graph-RAG vs plain-RAG ablation)
# ---------------------------------------------------------------------------

_JUDGE_PROMPT = """You are grading an aerospace failure-analysis assistant's answer for a technical evaluation. Be strict and consistent.

QUESTION:
{question}

ANSWER TO GRADE:
{answer}

Score the answer from 1 (poor) to 5 (excellent) on each dimension:
- factual_accuracy: is the failure mode / root cause described correctly and specifically, with no fabricated details?
- specificity: does it name the actual mission, subsystem, and mechanism rather than speaking generically?
- completeness: does it address the root cause, not just the symptom?

Respond with ONLY a JSON object:
{{"factual_accuracy": <1-5>, "specificity": <1-5>, "completeness": <1-5>, "justification": "<one sentence>"}}
"""


def llm_judge_score(question: str, answer: str, judge_model: str = "llama3") -> dict:
    """
    Scores one (question, answer) pair with an LLM-as-judge rubric.
    Note: using the same model family as the generator risks self-preference bias —
    for the paper, prefer a different/larger judge model if one is available, and
    state that choice explicitly in the write-up.
    """
    response = ollama.chat(
        model=judge_model,
        messages=[{"role": "user", "content": _JUDGE_PROMPT.format(question=question, answer=answer)}],
        format="json",
        options={"temperature": 0}
    )
    try:
        scores = json.loads(response["message"]["content"])
    except json.JSONDecodeError:
        return {"factual_accuracy": None, "specificity": None, "completeness": None, "justification": "parse_error"}

    numeric = [v for k, v in scores.items() if k != "justification" and isinstance(v, (int, float))]
    scores["overall"] = round(statistics.mean(numeric), 3) if numeric else None
    return scores


def aggregate_judge_scores(scores: list[dict]) -> dict:
    """Averages llm_judge_score() output across all test questions for one condition (e.g. 'graph_rag' vs 'plain_rag')."""
    valid = [s for s in scores if s.get("overall") is not None]
    if not valid:
        return {}
    dims = ["factual_accuracy", "specificity", "completeness", "overall"]
    return {f"mean_{d}": round(statistics.mean(s[d] for s in valid), 3) for d in dims}