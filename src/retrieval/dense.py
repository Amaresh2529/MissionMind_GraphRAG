"""
dense.py — dense retrieval with a sentence-transformers model (base paper: BAAI/bge-m3).

Only bge-m3's dense output is used (the paper names bge-m3 for dense retrieval
and does not mention its sparse or multi-vector modes). Embeddings are
L2-normalised, so the dot product is cosine similarity. Passage embeddings
are cached per (model, revision, max_seq_length, text hash) under
data/processed/emb_cache/, so re-runs do not re-encode and give identical
vectors.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

DEFAULT_MODEL = "BAAI/bge-m3"
DEFAULT_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"   # HF commit checked 2026-10-12
MAX_SEQ_LENGTH = 1024   # longest passage is 329 words (< 600 tokens); queries are capped at 300 words


class Embedder:
    """Thin wrapper so tests can substitute a deterministic fake."""

    def __init__(self, model: str = DEFAULT_MODEL, revision: str | None = DEFAULT_REVISION,
                 max_seq_length: int = MAX_SEQ_LENGTH, batch_size: int = 16):
        from sentence_transformers import SentenceTransformer
        import torch
        self.name, self.revision, self.batch_size = model, revision, batch_size
        self.model = SentenceTransformer(model, revision=revision,
                                         device="cuda" if torch.cuda.is_available() else "cpu")
        if self.model.device.type == "cuda":
            self.model.half()
        self.model.max_seq_length = max_seq_length
        self.max_seq_length = max_seq_length

    @property
    def cache_key(self) -> str:
        return f"{self.name.replace('/', '__')}@{(self.revision or 'none')[:12]}_len{self.max_seq_length}"

    def encode(self, texts: list[str]) -> np.ndarray:
        v = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                              show_progress_bar=False, convert_to_numpy=True)
        return v.astype(np.float32)


def _text_hash(texts: list[str]) -> str:
    h = hashlib.sha256()
    for t in texts:
        h.update(hashlib.sha256(t.encode("utf-8")).digest())
    return h.hexdigest()[:20]


class DenseIndex:
    def __init__(self, ids: list[str], texts: list[str], embedder):
        self.ids, self.embedder = ids, embedder
        cache = get_settings().processed_dir / "emb_cache" / embedder.cache_key / f"{_text_hash(texts)}.npy"
        if cache.exists():
            self.matrix = np.load(cache)
            self.cache_hit = True
        else:
            self.matrix = embedder.encode(texts)
            cache.parent.mkdir(parents=True, exist_ok=True)
            np.save(cache, self.matrix)
            self.cache_hit = False
        self.cache_path = cache

    def rank(self, query: str, allowed: set[int] | None = None, depth: int | None = None) -> list[tuple[int, float]]:
        q = self.embedder.encode([query])[0]
        sims = self.matrix @ q
        idx = np.array(sorted(allowed)) if allowed is not None else np.arange(len(self.ids))
        if idx.size == 0:
            return []
        order = idx[np.lexsort((idx, -sims[idx]))]   # by similarity desc, then index asc (deterministic)
        if depth:
            order = order[:depth]
        return [(int(i), float(sims[i])) for i in order]
