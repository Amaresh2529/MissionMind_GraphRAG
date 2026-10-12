"""
bm25.py — Okapi BM25 (self-contained, no third-party package).

The base paper uses BM25 per field but does not state the implementation,
tokeniser or parameters, so the common Lucene/Elasticsearch defaults are used
and recorded as a deviation-by-unspecification:

    idf(t)   = ln(1 + (N - df + 0.5) / (df + 0.5))           (non-negative variant)
    score    = sum_t idf(t) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl))
    k1 = 1.2, b = 0.75
    tokens   = lower-cased runs of [a-z0-9] (no stemming, no stop-word list)

Each distinct query term counts once (query term frequency ignored).
Ties are broken by document order (stable sort), so rankings are deterministic.
"""

import math
import re
from collections import Counter

K1 = 1.2
B = 0.75
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self, texts: list[str], k1: float = K1, b: float = B):
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(t)) for t in texts]
        self.lengths = [sum(tf.values()) for tf in self.tfs]
        self.n = len(texts)
        self.avgdl = (sum(self.lengths) / self.n) if self.n else 0.0
        df = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (self.n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self.postings: dict[str, list[int]] = {}
        for i, tf in enumerate(self.tfs):
            for t in tf:
                self.postings.setdefault(t, []).append(i)

    def scores(self, query: str) -> dict[int, float]:
        out: dict[int, float] = {}
        for t in sorted(set(tokenize(query))):   # sorted: float sums independent of string-hash seed
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.postings[t]:
                tf = self.tfs[i][t]
                norm = tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avgdl)
                out[i] = out.get(i, 0.0) + idf * tf * (self.k1 + 1) / norm
        return out

    def rank(self, query: str, allowed: set[int] | None = None, depth: int | None = None) -> list[tuple[int, float]]:
        s = self.scores(query)
        items = [(i, v) for i, v in s.items() if allowed is None or i in allowed]
        items.sort(key=lambda x: (-x[1], x[0]))
        return items[:depth] if depth else items
