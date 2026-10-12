"""Unit tests for text processing, retrieval formatting and metrics (no services needed)."""
import pytest


# --- chunking ---------------------------------------------------------------
def test_chunker_window_and_overlap():
    from pipeline.text_chunker import chunk_text_by_words
    words = [f"w{i}" for i in range(600)]
    chunks = chunk_text_by_words(" ".join(words), chunk_size=250, overlap=50)
    assert [len(c.split()) for c in chunks] == [250, 250, 200]
    assert chunks[1].split()[0] == "w200"          # stride = 250 - 50
    assert chunks[-1].split()[-1] == "w599"         # nothing dropped at the end


def test_chunker_short_text_single_chunk():
    from pipeline.text_chunker import chunk_text_by_words
    assert chunk_text_by_words("a b c", chunk_size=250, overlap=50) == ["a b c"]


# --- cleaning -----------------------------------------------------------------
def test_sanitize_fixes_oring_and_whitespace():
    from pipeline.text_cleaner import sanitize_text
    assert sanitize_text("the  0-ring\n\nseal") == "the O-ring seal"


def test_quality_score_flags_embedded_digits():
    from pipeline.text_cleaner import text_quality_score
    corrupted = " ".join(["faci8ities"] * 10 + ["normal"] * 10)
    assert text_quality_score(corrupted) == 0.0
    assert text_quality_score("") == 1.0


# --- retriever result handling ------------------------------------------------
ROWS = [
    {"chunk_id": "A_1", "doc_id": "A", "context": "text one", "score": 0.9, "mission": "M1",
     "subsystem": "S", "failure_mode": "F1", "root_cause": "R1", "extraction_method": "llm",
     "related": [{"mission": "M2", "failure_mode": "F9", "similarity": 0.7}]},
    {"chunk_id": "A_1", "doc_id": "A", "context": "text one", "score": 0.9, "mission": "M1",
     "subsystem": "S", "failure_mode": "F2", "root_cause": "R2", "extraction_method": "ner", "related": [None]},
    {"chunk_id": "B_4", "doc_id": "B", "context": "text two", "score": 0.5, "mission": None,
     "subsystem": None, "failure_mode": None, "root_cause": None, "extraction_method": None, "related": []},
]


def test_aggregate_rows_one_result_per_chunk_in_rank_order():
    from graph.retriever import aggregate_rows
    out = aggregate_rows(ROWS)
    assert [r["chunk_id"] for r in out] == ["A_1", "B_4"]
    assert [f["failure_mode"] for f in out[0]["facts"]] == ["F1", "F2"]
    assert out[0]["related_failures"] == [{"mission": "M2", "failure_mode": "F9", "similarity": 0.7}]
    assert out[1]["facts"] == [] and out[1]["related_failures"] == []


def test_context_text_contains_sources_and_facts():
    from graph.retriever import aggregate_rows, build_context_text
    text = build_context_text(aggregate_rows(ROWS))
    assert "[1] Source: A_1" in text and "[2] Source: B_4" in text
    assert "Failure mode: F1" in text and "[Cross-mission pattern] M2: F9" in text


def test_prompt_with_and_without_context():
    from backend.generation import build_prompt
    assert "CONTEXT:\nctx" in build_prompt("q?", "ctx")
    assert "CONTEXT" not in build_prompt("q?", None)


# --- run logging -----------------------------------------------------------------
def test_tee_output_behaves_like_a_stream(tmp_path):
    """Regression: the first smoke run crashed because transformers calls
    sys.stdout.isatty() while output was being teed into the run log."""
    import sys
    from runlog import tee_output
    log = tmp_path / "log.txt"
    with tee_output(log):
        print("hello run log")
        assert sys.stdout.isatty() is False
        assert sys.stdout.encoding        # delegated attribute
    assert "hello run log" in log.read_text(encoding="utf-8")


def test_new_run_dir_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setenv("MISSIONMIND_RUNS_DIR", str(tmp_path))
    from runlog import new_run_dir
    new_run_dir("r1")
    with pytest.raises(FileExistsError):
        new_run_dir("r1")


# --- metrics -------------------------------------------------------------------
def test_retrieval_metrics_known_values():
    from metrics import retrieval_metrics, aggregate_retrieval_metrics
    m = retrieval_metrics(["x", "a", "y"], {"a", "b"}, k=3)
    assert m == {"precision_at_k": 0.333, "recall_at_k": 0.5, "reciprocal_rank": 0.5}
    agg = aggregate_retrieval_metrics([m, retrieval_metrics(["a"], {"a"}, k=1)])
    assert agg["mean_reciprocal_rank"] == 0.75


def test_extraction_metrics_detection_counts():
    from metrics import extraction_metrics
    gold = [{"chunk_id": "1", "has_failure_data": True, "mission": "M", "subsystem": "S",
             "failure_mode": "F", "root_cause": "R"},
            {"chunk_id": "2", "has_failure_data": False},
            {"chunk_id": "3", "has_failure_data": True, "mission": "M", "subsystem": "S",
             "failure_mode": "F", "root_cause": "R"}]
    pred = [{**gold[0]}, {"chunk_id": "2", "has_failure_data": True, "mission": "M",
                          "subsystem": "S", "failure_mode": "F", "root_cause": "R"},
            {"chunk_id": "3", "has_failure_data": False}]
    m = extraction_metrics(pred, gold)
    assert (m["detection_precision"], m["detection_recall"]) == (0.5, 0.5)
    assert m["field_accuracy"] == {"mission": 1.0, "subsystem": 1.0, "failure_mode": 1.0, "root_cause": 1.0}
