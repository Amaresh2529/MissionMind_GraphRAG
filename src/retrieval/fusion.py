"""
fusion.py — Reciprocal Rank Fusion, exactly as stated in the base paper:

    RRFScore(c) = sum_{r in R} 1 / (k_rrf + rank_r(c)),   k_rrf = 60, ranks 1-based

An item absent from a ranking contributes nothing for that ranking. Ties are
broken by the item's best (smallest) rank in any list, then by item id, so the
fused order is deterministic.
"""

K_RRF = 60


def rrf(rankings: dict[str, list], k: int = K_RRF) -> list[tuple]:
    """rankings: {list_name: [item_id, ...] best first}. Returns [(item_id, score, {list_name: rank})]."""
    scores, ranks = {}, {}
    for name, items in rankings.items():
        for r, item in enumerate(items, 1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + r)
            ranks.setdefault(item, {})[name] = r
    order = sorted(scores, key=lambda i: (-scores[i], min(ranks[i].values()), i))
    return [(i, scores[i], ranks[i]) for i in order]
