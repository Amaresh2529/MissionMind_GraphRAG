"""Stage 3: base-paper retrieval components (BM25, RRF, multi-field, leave-one-mission-out, generation checks)."""
import hashlib
import math

import numpy as np
import pytest

from retrieval.bm25 import BM25Index, tokenize
from retrieval.corpus import Unit
from retrieval.fusion import rrf
from retrieval import rca_generation
from retrieval.queries import dev_queries
from retrieval.systems import SYSTEMS, Retriever


def test_tokenize():
    assert tokenize("O-ring erosion, 64-bit SRI!") == ["o", "ring", "erosion", "64", "bit", "sri"]


def test_bm25_matches_hand_computation():
    docs = ["seal erosion seal", "parachute failure", "seal leak"]
    idx = BM25Index(docs)
    n, avgdl = 3, (3 + 2 + 2) / 3
    idf_seal = math.log(1 + (n - 2 + 0.5) / (2 + 0.5))
    def term(tf, dl):
        return idf_seal * tf * 2.2 / (tf + 1.2 * (1 - 0.75 + 0.75 * dl / avgdl))
    s = idx.scores("seal")
    assert s[0] == pytest.approx(term(2, 3))
    assert s[2] == pytest.approx(term(1, 2))
    assert 1 not in s
    assert [i for i, _ in idx.rank("seal")] == [0, 2]


def test_bm25_repeated_query_terms_count_once_and_filter():
    idx = BM25Index(["seal erosion", "seal leak", "parachute"])
    assert idx.scores("seal seal seal") == idx.scores("seal")
    assert [i for i, _ in idx.rank("seal", allowed={1})] == [1]


def test_rrf_formula_k60():
    fused = rrf({"a": ["x", "y"], "b": ["y", "z"]})
    scores = {i: s for i, s, _ in fused}
    assert scores["y"] == pytest.approx(1 / 62 + 1 / 61)
    assert scores["x"] == pytest.approx(1 / 61)
    assert scores["z"] == pytest.approx(1 / 62)
    assert [i for i, _, _ in fused] == ["y", "x", "z"]
    assert fused[0][2] == {"a": 2, "b": 1}


class FakeEmbedder:
    """Deterministic bag-of-words hashing embedder (no model download)."""
    name, revision, max_seq_length, cache_key = "fake", None, 0, "fake-test"

    def encode(self, texts):
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for r, t in enumerate(texts):
            for w in tokenize(t):
                out[r, int(hashlib.md5(w.encode()).hexdigest(), 16) % 64] += 1
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


def _u(i, mission, field, text):
    return Unit(f"D{mission}::p{i:04d}::00", f"D{mission}", (mission,), field, i, 0, len(text), None, text)


UNITS = [
    _u(1, "a", "summary", "booster joint seal failed in cold weather at launch"),
    _u(2, "a", "causes", "o ring seal erosion caused by low temperature resiliency loss"),
    _u(3, "b", "summary", "orbiter wing damaged by foam debris during ascent"),
    _u(4, "b", "causes", "foam strike breached the wing leading edge thermal protection"),
    _u(5, "b", "disposition", "recommend imaging of the wing and foam shedding reduction"),
    _u(6, "c", "causes", "seal leak in helium system caused thruster failure"),
    _u(7, "c", "disposition", "recommend seal qualification testing at temperature"),
]


@pytest.fixture(scope="module")
def retriever(tmp_path_factory, monkeypatch_module):
    return Retriever(UNITS, FakeEmbedder())


@pytest.fixture(scope="module")
def monkeypatch_module(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    from config import get_settings
    s = get_settings()
    mp.setattr(type(s), "processed_dir", property(lambda self: tmp_path_factory.mktemp("proc")), raising=True)
    yield mp
    mp.undo()


def test_b3_fuses_six_lists_and_excludes_query_mission(retriever):
    r = retriever.search(SYSTEMS["B3"], "seal failure at low temperature", exclude_missions={"a"})
    assert r["lists"] == sorted(f"{f}/{m}" for f in ("summary", "causes", "disposition") for m in ("bm25", "dense"))
    assert all(not p["doc_id"].endswith("a") for p in r["passages"])
    assert r["mission_ranking"][0] == "c"            # seal precedents first
    assert set(r["mission_ranking"]) == {"b", "c"}


def test_single_field_and_single_method_systems(retriever):
    r = retriever.search(SYSTEMS["SF-causes-bm25"], "seal", exclude_missions=set())
    assert r["lists"] == ["causes/bm25"]
    assert {p["field"] for p in r["passages"]} == {"causes"}
    assert [p["rank"] for p in r["passages"]] == list(range(1, len(r["passages"]) + 1))
    whole = retriever.search(SYSTEMS["B1"], "seal", exclude_missions=set())
    assert whole["lists"] == ["whole/bm25"] and len(whole["passages"]) == 4


def test_search_is_deterministic(retriever):
    a = retriever.search(SYSTEMS["B3"], "foam wing damage", exclude_missions={"c"})
    b = retriever.search(SYSTEMS["B3"], "foam wing damage", exclude_missions={"c"})
    assert a == b


def test_dense_system_needs_embedder():
    with pytest.raises(RuntimeError):
        Retriever(UNITS, None).search(SYSTEMS["B2"], "seal")


def test_dev_queries_use_summary_field_of_own_mission():
    qs = {q["mission"]: q for q in dev_queries(UNITS)}
    assert set(qs) == {"a", "b"}                     # mission c has no summary-field unit
    assert qs["a"]["text"].startswith("booster joint")


def test_generation_packing_and_citation_checks():
    by_id = {u.id: u for u in UNITS}
    passages = [{"id": u.id} for u in UNITS]
    context, used = rca_generation.pack_context(passages, by_id)
    assert used == [u.id for u in UNITS] and "[C1] mission=a" in context and "field=Causes" in context
    ok = {"probable_root_causes": [{"cause": "x", "evidence": ["C1"]}], "contributing_factors": [],
          "similar_precedents": [{"mission": "a", "similarity": "y", "evidence": ["C9"]}], "recommended_actions": []}
    c = rca_generation.validate(ok, {"C1", "C2"})
    assert c == {"schema_ok": True, "citations": 2, "invalid_citations": 1, "items": 2, "uncited_items": 0}
    assert rca_generation.validate(None, set())["schema_ok"] is False
