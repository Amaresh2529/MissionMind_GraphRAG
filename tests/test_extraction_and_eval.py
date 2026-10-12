"""A2/A3: extract_failure_data contract and evaluation-input validation."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def ner():
    from models.ner_model import FailureNER
    return FailureNER()


def _llm_never_called(_text):
    raise AssertionError("LLM fallback must not run when the NER gate passes")


def test_ner_path_used_when_gate_passes(ner):
    from graph.graph_builder import extract_failure_data
    text = ("The solid rocket booster joint failed during ascent. Investigators found a design flaw "
            "in the field joint and recorded seal erosion on the primary O-ring.")
    rec = extract_failure_data(text, mission="STS-51-L Challenger", ner=ner, llm_fn=_llm_never_called)
    assert rec["method"] == "ner" and rec["has_failure_data"] is True
    assert rec["mission"] == "STS-51-L Challenger"
    assert rec["subsystem"] == "solid rocket booster"
    assert rec["failure_mode"] == "seal erosion"
    assert "design flaw" in rec["root_cause"]


def test_llm_path_used_when_gate_fails(ner):
    from graph.graph_builder import extract_failure_data
    calls = []

    def fake_llm(text):
        calls.append(text)
        return {"has_failure_data": True, "mission": "LLM guess", "subsystem": "S",
                "failure_mode": "F", "root_cause": "R"}

    rec = extract_failure_data("The committee met on Tuesday.", mission="Doc Mission", ner=ner, llm_fn=fake_llm)
    assert len(calls) == 1 and rec["method"] == "llm"
    assert rec["mission"] == "Doc Mission"            # graph uses document provenance
    rec2 = extract_failure_data("The committee met on Tuesday.", ner=ner, llm_fn=fake_llm)
    assert rec2["mission"] == "LLM guess"


def test_llm_no_data_returns_empty_record(ner):
    from graph.graph_builder import extract_failure_data
    rec = extract_failure_data("Nothing here.", ner=ner, llm_fn=lambda t: {"has_failure_data": False})
    assert rec["has_failure_data"] is False and rec["failure_mode"] is None and rec["method"] == "llm"


def test_record_keys_match_metrics_schema(ner):
    from graph.graph_builder import extract_failure_data
    rec = extract_failure_data("x", ner=ner, llm_fn=lambda t: {"has_failure_data": False})
    assert {"has_failure_data", "mission", "subsystem", "failure_mode", "root_cause"} <= rec.keys()


# --- evaluation input validation ----------------------------------------------
def test_shipped_placeholder_template_is_rejected():
    from run_eval import validate_test_data, load_chunk_texts, InvalidTestData
    data = json.loads((ROOT / "evalutation" / "test_data.json").read_text(encoding="utf-8"))
    with pytest.raises(InvalidTestData) as err:
        validate_test_data(data, load_chunk_texts())
    assert "placeholder" in str(err.value)


def test_valid_minimal_data_passes_and_text_is_filled():
    from run_eval import validate_test_data
    chunks = {"Doc_0": "some chunk text"}
    data = {"labeled_chunks": [{"chunk_id": "Doc_0", "has_failure_data": False}],
            "test_queries": [{"question": "q?", "relevant_chunk_ids": ["Doc_0"]}]}
    out = validate_test_data(data, chunks)
    assert out["labeled_chunks"][0]["text"] == "some chunk text"


def test_unknown_chunk_id_rejected():
    from run_eval import validate_test_data, InvalidTestData
    with pytest.raises(InvalidTestData, match="not found"):
        validate_test_data({"test_queries": [{"question": "q?", "relevant_chunk_ids": ["nope_1"]}]},
                           {"Doc_0": "t"}, tracks=("retrieval",))


def test_run_eval_cli_exits_2_on_placeholder_data():
    import subprocess, sys
    proc = subprocess.run([sys.executable, str(ROOT / "evalutation" / "run_eval.py")],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 2 and "Test data rejected" in proc.stdout
