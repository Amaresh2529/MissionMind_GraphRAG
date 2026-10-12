"""B6: refresh-on-change ingestion for Stage 2 passages and Stage 1 chunks."""
import json

import numpy as np
import pytest

from graph.passage_loader import plan_changes, content_hash
from graph.neo4j_loader import plan_chunk_changes


def _p(pid, text, page=1, field="causes"):
    return {"passage_id": pid, "doc_id": "D", "page": page, "char_start": 0, "char_end": len(text),
            "section": "S", "chapter": "C", "pseudo_field": field, "n_words": len(text.split()),
            "source": "text_layer", "low_quality": False, "text": text}


def test_plan_changes_classifies_every_case():
    old = [_p("a", "same"), _p("b", "old text"), _p("c", "gone")]
    existing = {p["passage_id"]: content_hash(p) for p in old}
    plan = plan_changes(existing, [_p("a", "same"), _p("b", "new text"), _p("d", "brand new")])
    assert plan == {"insert": ["d"], "update": ["b"], "unchanged": ["a"], "delete": ["c"]}


def test_metadata_change_counts_as_update():
    existing = {"a": content_hash(_p("a", "t", page=1))}
    assert plan_changes(existing, [_p("a", "t", page=2)])["update"] == ["a"]


def test_chunk_plan():
    plan = plan_chunk_changes({"x_0": "a", "x_1": "b", "x_2": "c"},
                              [{"chunk_id": "x_0", "text": "a"}, {"chunk_id": "x_1", "text": "B!"},
                               {"chunk_id": "x_3", "text": "d"}])
    assert plan == {"insert": ["x_3"], "update": ["x_1"], "unchanged": ["x_0"], "delete": ["x_2"]}


# ---------------------------------------------------------------------------
class FakeEmbedder:
    """Deterministic 384-d vectors; avoids loading a model in tests."""
    def get_sentence_embedding_dimension(self):
        return 384

    def encode(self, texts, show_progress_bar=False):
        return np.array([[float((hash(t) >> i) & 1) for i in range(384)] for t in texts])


DOC = "zz_refresh_test_doc"


@pytest.fixture
def stage1_db(tmp_path, monkeypatch):
    from graph.neo4j_connector import get_driver, close_driver
    try:
        get_driver().verify_connectivity()
    except Exception as err:
        pytest.skip(f"Neo4j not reachable: {err}")
    monkeypatch.setenv("MISSIONMIND_DATA_DIR", str(tmp_path))
    yield get_driver()
    with get_driver().session() as s:
        s.run("MATCH (n) WHERE n.doc_id = $d OR n.id = $d OR n.id STARTS WITH $p DETACH DELETE n",
              d=DOC, p=DOC + "_")
    close_driver()


def _write_passages(tmp_path, passages):
    d = tmp_path / "processed" / "passages"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / f"{DOC}.jsonl", "w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps({**p, "doc_id": DOC}) + "\n")


def _stored(driver):
    with driver.session() as s:
        return {r["id"]: r["text"] for r in s.run(
            "MATCH (:Document {id: $d})-[:HAS_PASSAGE]->(p:Passage) RETURN p.id AS id, p.text AS text", d=DOC)}


@pytest.mark.integration
def test_passage_refresh_end_to_end(stage1_db, tmp_path):
    from graph.passage_loader import ingest_passages
    emb = FakeEmbedder()
    v1 = [_p(f"{DOC}::p0001::00", "alpha"), _p(f"{DOC}::p0001::01", "beta"), _p(f"{DOC}::p0002::00", "gamma")]
    _write_passages(tmp_path, v1)
    r1 = ingest_passages([DOC], embedder=emb)
    assert (r1["insert"], r1["update"], r1["delete"]) == (3, 0, 0)

    r2 = ingest_passages([DOC], embedder=emb)                     # nothing changed
    assert (r2["insert"], r2["update"], r2["unchanged"], r2["delete"]) == (0, 0, 3, 0)

    v2 = [_p(f"{DOC}::p0001::00", "alpha"), _p(f"{DOC}::p0001::01", "beta (corrected)")]
    _write_passages(tmp_path, v2)
    r3 = ingest_passages([DOC], embedder=emb)
    assert (r3["insert"], r3["update"], r3["unchanged"], r3["delete"]) == (0, 1, 1, 1)
    assert _stored(stage1_db) == {f"{DOC}::p0001::00": "alpha", f"{DOC}::p0001::01": "beta (corrected)"}


@pytest.mark.integration
def test_chunk_refresh_end_to_end(stage1_db, tmp_path, monkeypatch):
    import graph.neo4j_loader as loader
    monkeypatch.setattr(loader, "SentenceTransformer", lambda name: FakeEmbedder())
    chunks_dir = tmp_path / "processed" / "chunks"
    chunks_dir.mkdir(parents=True)

    def write(chunks):
        (chunks_dir / f"{DOC}_chunks.json").write_text(json.dumps(
            {"document_id": DOC, "total_chunks": len(chunks), "chunks": chunks}), encoding="utf-8")

    write([{"chunk_id": f"{DOC}_0", "text": "one"}, {"chunk_id": f"{DOC}_1", "text": "two"}])
    r1 = loader.ingest_chunks_to_neo4j([DOC])
    assert (r1["inserted"], r1["updated"], r1["deleted"]) == (2, 0, 0)
    write([{"chunk_id": f"{DOC}_0", "text": "one, re-chunked"}])
    r2 = loader.ingest_chunks_to_neo4j([DOC])
    assert (r2["inserted"], r2["updated"], r2["skipped"], r2["deleted"]) == (0, 1, 0, 1)
    from graph.neo4j_connector import get_driver
    with get_driver().session() as s:
        rows = {r["id"]: r["t"] for r in s.run(
            "MATCH (:Document {id: $d})-[:HAS_CHUNK]->(c:Chunk) RETURN c.id AS id, c.text AS t", d=DOC)}
    assert rows == {f"{DOC}_0": "one, re-chunked"}
