"""A1/A5: entry points import cleanly; configuration has no hard-coded secret."""
import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

MODULES = ["config", "runlog", "graph.neo4j_connector", "graph.retriever", "graph.neo4j_loader",
           "graph.graph_builder", "models.ner_model", "models.embeddings", "pipeline.pdf_loader",
           "pipeline.text_chunker", "pipeline.text_cleaner", "backend.generation", "backend.main",
           "backend.rag_pipeline", "metrics", "run_eval"]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module):
    importlib.import_module(module)


def test_backend_resolves_to_src_package():
    import backend
    assert Path(backend.__file__).resolve().parent == ROOT / "src" / "backend"


def test_retriever_exposes_expected_api():
    from graph.retriever import GraphRAGRetriever
    for name in ("hybrid_search", "build_context_text", "vector_search_chunk_ids", "close"):
        assert hasattr(GraphRAGRetriever, name)


def test_fastapi_app_routes_registered():
    from backend.main import app
    paths = {r.path for r in app.routes}
    assert {"/", "/query"} <= paths


def test_missing_password_fails_clearly(monkeypatch):
    import graph.neo4j_connector as nc
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    monkeypatch.setattr(nc, "_driver", None)
    with pytest.raises(nc.Neo4jConfigError):
        nc.get_driver()


def test_env_overrides_settings(monkeypatch):
    from config import get_settings
    monkeypatch.setenv("MISSIONMIND_LLM_MODEL", "some-model")
    monkeypatch.setenv("MISSIONMIND_LLM_SEED", "7")
    s = get_settings()
    assert s.llm_model == "some-model" and s.llm_seed == 7
    assert s.public_dict()["neo4j_password"] in (None, "***set***")


def test_no_hardcoded_neo4j_password_in_active_code():
    pattern = re.compile(r"NEO4J_PASSWORD\s*=\s*[\"']|auth=\([^)]*[\"']password[\"']")
    offenders = []
    for path in list((ROOT / "src").rglob("*.py")) + list((ROOT / "evalutation").glob("*.py")) + [ROOT / "run_pipeline.py"]:
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
