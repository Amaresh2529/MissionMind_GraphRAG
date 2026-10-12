"""A7 (integration): retrieval against the Stage 1 smoke database.

Requires the Neo4j instance named in .env to contain the smoke subset built by
    python run_pipeline.py --skip-extract-text --docs "Ariane_5_Flight_501_Failure_Inquiry_Board_Report." Mars_Climate_Orbiter
Skipped automatically when the database is unreachable or empty.
"""
import pytest

pytestmark = pytest.mark.integration

SUBSET = ("Ariane_5_Flight_501_Failure_Inquiry_Board_Report._", "Mars_Climate_Orbiter_")


@pytest.fixture(scope="module")
def retriever():
    from graph.neo4j_connector import get_driver, close_driver
    try:
        with get_driver().session() as s:
            n = s.run("MATCH (c:Chunk) RETURN count(c) AS n").single()["n"]
    except Exception as err:
        pytest.skip(f"Neo4j not reachable: {err}")
    if n == 0:
        pytest.skip("smoke database is empty — run the smoke pipeline first")
    from graph.retriever import GraphRAGRetriever
    yield GraphRAGRetriever()
    close_driver()


def test_hybrid_search_contract(retriever):
    results = retriever.hybrid_search("What caused the Ariane 5 Flight 501 failure?", top_k=3)
    assert 1 <= len(results) <= 3
    assert len({r["chunk_id"] for r in results}) == len(results)          # one entry per chunk
    assert all(r["chunk_id"].startswith(SUBSET) for r in results)          # only the smoke subset exists
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)
    for r in results:
        assert r["context"] and r["doc_id"]
        for f in r["facts"]:
            assert set(f) == {"mission", "subsystem", "failure_mode", "root_cause", "extraction_method"}


def test_context_builds_from_live_results(retriever):
    results = retriever.hybrid_search("Mars Climate Orbiter units", top_k=2)
    text = retriever.build_context_text(results)
    assert results[0]["chunk_id"] in text


def test_graph_contains_only_current_code_facts():
    """The fresh DB must not contain legacy rule-based facts (extraction_method NULL)."""
    from graph.neo4j_connector import get_driver
    with get_driver().session() as s:
        legacy = s.run("MATCH (fm:FailureMode) WHERE fm.extraction_method IS NULL RETURN count(fm) AS n").single()["n"]
    assert legacy == 0
