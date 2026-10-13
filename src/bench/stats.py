"""
stats.py — paired significance testing over queries (pre-registered).

  paired_permutation(a, b)  two-sided sign-flip permutation test on per-query differences
                            (exact when 2^n <= 2^16, else 20,000 seeded random flips)
  bootstrap_ci(a, b)        percentile bootstrap 95% CI of the mean difference (10,000 seeded resamples)
  holm(pvalues)             Holm-Bonferroni adjusted p-values for the secondary comparisons
Queries where either system's score is undefined (None) are dropped pairwise.
"""

import itertools
import random

SEED = 20261013


def _pairs(a: list, b: list) -> list[float]:
    return [x - y for x, y in zip(a, b) if x is not None and y is not None]


def paired_permutation(a: list, b: list, n_random: int = 20000, seed: int = SEED) -> dict:
    d = _pairs(a, b)
    n = len(d)
    if n == 0:
        return {"n": 0, "mean_diff": None, "p": None}
    obs = abs(sum(d) / n)
    if n <= 16:
        flips = itertools.product((1, -1), repeat=n)
        total = 2 ** n
        exact = True
    else:
        rng = random.Random(seed)
        flips = ([rng.choice((1, -1)) for _ in range(n)] for _ in range(n_random))
        total = n_random
        exact = False
    hits = sum(1 for s in flips if abs(sum(x * y for x, y in zip(d, s)) / n) >= obs - 1e-12)
    p = hits / total if exact else (hits + 1) / (total + 1)
    return {"n": n, "mean_diff": sum(d) / n, "p": p, "exact": exact}


def bootstrap_ci(a: list, b: list, n_boot: int = 10000, seed: int = SEED, alpha: float = 0.05) -> dict:
    d = _pairs(a, b)
    if not d:
        return {"n": 0, "low": None, "high": None}
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(n_boot))
    lo, hi = means[int(alpha / 2 * n_boot)], means[int((1 - alpha / 2) * n_boot) - 1]
    return {"n": len(d), "mean_diff": sum(d) / len(d), "low": lo, "high": hi}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    items = sorted((p, k) for k, p in pvalues.items() if p is not None)
    m, out, running = len(items), {}, 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out
