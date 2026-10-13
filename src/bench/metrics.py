"""
metrics.py — metric definitions (pre-registered in docs/research/09_Stage4_5_6_Method_and_Protocol.md).

Gains are LINEAR (G_i = graded relevance), as in the base paper's nDCG@100.

Mission level (T1, labels D2b):
  ndcg_at_k(ranking, gains, k)   DCG = sum_i G_i / log2(i+1), normalised by the ideal ordering of all
                                 graded candidates
  recall_at_k(ranking, rel, k)   |top-k & rel| / |rel|, rel = missions with grade >= 2
  mrr(ranking, rel)              1 / rank of the first relevant mission (0 if none)
Passage level (paper metrics, labels D2a pages of analogous missions):
  norm_recall_at_k               |retrieved_k & gold| / min(k, |gold|)
  ndcg_at_k on passages          gain of a passage = grade of the mission whose evidence page it lies on
Extraction (D1): micro precision/recall/F1 over (passage, code) pairs.
"""

import math


def dcg(gains: list[float]) -> float:
    return sum(g / math.log2(i + 1) for i, g in enumerate(gains, 1))


def ndcg_at_k(ranking: list, gain: dict, k: int) -> float | None:
    ideal = sorted((g for g in gain.values() if g > 0), reverse=True)[:k]
    if not ideal:
        return None                      # undefined: no relevant candidate (query excluded from the mean)
    return dcg([gain.get(x, 0) for x in ranking[:k]]) / dcg(ideal)


def recall_at_k(ranking: list, relevant: set, k: int) -> float | None:
    if not relevant:
        return None
    return len(set(ranking[:k]) & relevant) / len(relevant)


def norm_recall_at_k(ranking: list, gold: set, k: int) -> float | None:
    if not gold:
        return None
    return len(set(ranking[:k]) & gold) / min(k, len(gold))


def mrr(ranking: list, relevant: set) -> float | None:
    if not relevant:
        return None
    for i, x in enumerate(ranking, 1):
        if x in relevant:
            return 1.0 / i
    return 0.0


def prf(pred: set, gold: set) -> dict:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    r = tp / len(gold) if gold else (1.0 if not pred else 0.0)
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "pred": len(pred), "gold": len(gold), "precision": p, "recall": r, "f1": f}


def mean(xs: list) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
