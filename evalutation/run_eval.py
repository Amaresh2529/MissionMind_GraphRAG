"""
run_eval.py

Evaluation runner for MissionMind. Three tracks, all scored with the pure
functions in metrics.py:

  1. extraction  graph_builder.extract_failure_data() vs hand-labelled chunks
  2. retrieval   GraphRAGRetriever ranked chunk ids vs hand-labelled relevant chunks
  3. answers     graph-fact context vs chunk-only context, same prompt and
                 generator, scored by an LLM judge (secondary evidence only;
                 the judge must be validated against human ratings before
                 any claim is made from it)

Every run writes to runs/<run_id>/eval/ and refuses to overwrite earlier runs.

Input file schema (evalutation/test_data.json by default):
{
  "dataset_info": {"name": ..., "annotator": ..., "status": ...},   # optional
  "labeled_chunks": [{"chunk_id", "has_failure_data", "mission", "subsystem",
                      "failure_mode", "root_cause", "text"(optional)}],
  "test_queries":   [{"question", "relevant_chunk_ids": [...]}]
}
Chunk text is taken from data/processed/chunks when omitted. Placeholder
values ("<paste ...>", "REPLACE ...") and unknown chunk ids are rejected
before any model or database is touched.

Usage:
    python evalutation/run_eval.py --data evalutation/test_data.json --tracks extraction,retrieval
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))
sys.path.append(str(Path(__file__).resolve().parent))

from config import get_settings  # noqa: E402
from runlog import new_run_dir, write_json, environment_info, tee_output, Timer  # noqa: E402

TRACKS = ("extraction", "retrieval", "answers")
_PLACEHOLDER = re.compile(r"<\s*paste|REPLACE", re.IGNORECASE)


class InvalidTestData(ValueError):
    pass


def load_chunk_texts() -> dict[str, str]:
    texts = {}
    for path in get_settings().chunks_dir.glob("*_chunks.json"):
        with open(path, encoding="utf-8") as f:
            for c in json.load(f)["chunks"]:
                texts[c["chunk_id"]] = c["text"]
    return texts


def validate_test_data(data: dict, chunk_texts: dict[str, str], tracks=TRACKS) -> dict:
    """Checks structure and content; fills missing chunk text from disk.
    Raises InvalidTestData listing every problem found."""
    problems = []

    def check_str(where, value):
        if isinstance(value, str) and _PLACEHOLDER.search(value):
            problems.append(f"{where}: placeholder value {value[:40]!r}")

    if "extraction" in tracks:
        chunks = data.get("labeled_chunks")
        if not chunks:
            problems.append("labeled_chunks: missing or empty")
        for i, c in enumerate(chunks or []):
            where = f"labeled_chunks[{i}]"
            for key in ("chunk_id", "has_failure_data"):
                if key not in c:
                    problems.append(f"{where}: missing '{key}'")
            if not isinstance(c.get("has_failure_data"), bool):
                problems.append(f"{where}: has_failure_data must be true/false")
            for key, value in c.items():
                check_str(f"{where}.{key}", value)
            cid = c.get("chunk_id")
            if cid not in chunk_texts:
                problems.append(f"{where}: chunk_id {cid!r} not found in {get_settings().chunks_dir}")
            elif "text" in c and not _PLACEHOLDER.search(str(c["text"])) and c["text"] != chunk_texts[cid]:
                problems.append(f"{where}: text differs from the current chunk file (re-chunked since labelling?)")
            elif "text" not in c:
                c["text"] = chunk_texts[cid]

    if {"retrieval", "answers"} & set(tracks):
        queries = data.get("test_queries")
        if not queries:
            problems.append("test_queries: missing or empty")
        for i, q in enumerate(queries or []):
            where = f"test_queries[{i}]"
            check_str(f"{where}.question", q.get("question"))
            if not q.get("question"):
                problems.append(f"{where}: missing question")
            rel = q.get("relevant_chunk_ids") or []
            if not rel:
                problems.append(f"{where}: relevant_chunk_ids missing or empty")
            for cid in rel:
                check_str(f"{where}.relevant_chunk_ids", cid)
                if cid not in chunk_texts:
                    problems.append(f"{where}: relevant chunk {cid!r} not found")

    if problems:
        raise InvalidTestData("Test data rejected:\n  - " + "\n  - ".join(problems))
    return data


def run_extraction_eval(gold_chunks: list[dict], out_dir: Path) -> dict:
    from graph.graph_builder import extract_failure_data, MISSION_NAME_MAP
    from metrics import extraction_metrics
    print(f"\n{'='*60}\n1. EXTRACTION QUALITY  ({len(gold_chunks)} labelled chunks)\n{'='*60}")
    predictions = []
    for item in gold_chunks:
        doc_id = item["chunk_id"].rsplit("_", 1)[0]
        mission = MISSION_NAME_MAP.get(doc_id, doc_id.replace("_", " ").strip())
        try:
            pred = extract_failure_data(item["text"], mission=mission)
        except Exception as err:  # an LLM failure counts as "no extraction", and is logged
            pred = {"has_failure_data": False, "error": str(err)}
        pred["chunk_id"] = item["chunk_id"]
        predictions.append(pred)
    with open(out_dir / "predictions_extraction.jsonl", "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    result = extraction_metrics(predictions, gold_chunks)
    print(json.dumps(result, indent=2))
    return result


def run_retrieval_eval(test_queries: list[dict], retriever, k: int, out_dir: Path) -> dict:
    from metrics import retrieval_metrics, aggregate_retrieval_metrics
    print(f"\n{'='*60}\n2. RETRIEVAL QUALITY  ({len(test_queries)} questions, k={k})\n{'='*60}")
    per_query, rows = [], []
    for q in test_queries:
        retrieved = retriever.vector_search_chunk_ids(q["question"], top_k=k)
        m = retrieval_metrics(retrieved, set(q["relevant_chunk_ids"]), k=k)
        print(f"  {q['question'][:60]!r}: {m}")
        per_query.append(m)
        rows.append({"question": q["question"], "retrieved": retrieved,
                     "relevant": q["relevant_chunk_ids"], **m})
    with open(out_dir / "predictions_retrieval.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    result = {"k": k, "n_queries": len(per_query), **aggregate_retrieval_metrics(per_query)}
    print(json.dumps(result, indent=2))
    return result


def run_answer_eval(test_queries: list[dict], retriever, k: int, judge_model: str, out_dir: Path) -> dict:
    from backend.generation import build_prompt, generate
    from metrics import llm_judge_score, aggregate_judge_scores
    print(f"\n{'='*60}\n3. ANSWERS — graph facts vs chunk text only  ({len(test_queries)} questions)\n{'='*60}")
    rows, plain_scores, graph_scores = [], [], []
    for q in test_queries:
        results = retriever.hybrid_search(q["question"], top_k=k)
        chunk_only = [{**r, "facts": [], "related_failures": []} for r in results]
        answers = {
            "chunk_only": generate(build_prompt(q["question"], retriever.build_context_text(chunk_only))),
            "graph_facts": generate(build_prompt(q["question"], retriever.build_context_text(results))),
        }
        scores = {name: llm_judge_score(q["question"], a, judge_model=judge_model) for name, a in answers.items()}
        plain_scores.append(scores["chunk_only"])
        graph_scores.append(scores["graph_facts"])
        rows.append({"question": q["question"], "retrieved": [r["chunk_id"] for r in results],
                     "answers": answers, "judge_scores": scores})
        print(f"  ✓ {q['question'][:60]!r}")
    with open(out_dir / "predictions_answers.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    result = {"judge_model": judge_model,
              "chunk_only": aggregate_judge_scores(plain_scores),
              "graph_facts": aggregate_judge_scores(graph_scores)}
    print(json.dumps(result, indent=2))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--data", default=str(Path(__file__).resolve().parent / "test_data.json"))
    parser.add_argument("--tracks", default="extraction,retrieval,answers",
                        help="comma-separated subset of: " + ",".join(TRACKS))
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--judge-model", default=None,
                        help="defaults to the generator model (flagged as self-preference risk)")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)

    tracks = [t.strip() for t in args.tracks.split(",") if t.strip()]
    unknown = set(tracks) - set(TRACKS)
    if unknown:
        parser.error(f"unknown track(s): {sorted(unknown)}")

    with open(args.data, encoding="utf-8") as f:
        data = json.load(f)
    data = validate_test_data(data, load_chunk_texts(), tracks)  # fail before touching models/DB

    settings = get_settings()
    judge_model = args.judge_model or settings.llm_model
    run_dir = new_run_dir(args.run_id, prefix="eval")
    out_dir = run_dir / "eval"
    out_dir.mkdir()
    timer = Timer()
    with tee_output(run_dir / "log.txt"):
        if judge_model == settings.llm_model and "answers" in tracks:
            print(f"⚠️  Judge model == generator model ({judge_model}): self-preference bias risk. "
                  f"Treat answer scores as unvalidated.")
        write_json(run_dir / "config.json", {"settings": settings.public_dict(), "args": vars(args),
                                             "tracks": tracks, "judge_model": judge_model,
                                             "dataset_info": data.get("dataset_info")})
        write_json(run_dir / "env.json", environment_info())

        results = {}
        retriever = None
        if {"retrieval", "answers"} & set(tracks):
            from graph.retriever import GraphRAGRetriever
            retriever = GraphRAGRetriever()
        try:
            if "extraction" in tracks:
                with timer.step("extraction"):
                    results["extraction"] = run_extraction_eval(data["labeled_chunks"], out_dir)
            if "retrieval" in tracks:
                with timer.step("retrieval"):
                    results["retrieval"] = run_retrieval_eval(data["test_queries"], retriever, args.k, out_dir)
            if "answers" in tracks:
                with timer.step("answers"):
                    results["answers"] = run_answer_eval(data["test_queries"], retriever, args.k, judge_model, out_dir)
        finally:
            from graph.neo4j_connector import close_driver
            close_driver()
        write_json(out_dir / "metrics.json", results)
        write_json(run_dir / "timings.json", timer.timings)
        print(f"\n{'='*60}\nSaved results to {out_dir}")
    return results


if __name__ == "__main__":
    try:
        main()
    except InvalidTestData as err:
        print(err)
        sys.exit(2)
