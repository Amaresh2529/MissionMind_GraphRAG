"""
stage1_query_check.py

Stage 1 acceptance check A7 (query side): runs one question through the CLI
class (backend.rag_pipeline.MissionMindGraphRAG) and one through the HTTP API
(backend.main via FastAPI's TestClient) against the database in .env, and
saves the full responses to runs/<run_id>/.

This verifies that the entry points work end to end. It makes no claim about
answer quality.

Usage:
    python scripts/stage1_query_check.py --run-id stage1_verified_query
"""

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "src"))

from runlog import new_run_dir, write_json, environment_info, tee_output, Timer  # noqa: E402
from config import get_settings  # noqa: E402

QUESTIONS = {
    "cli": "What caused the inertial reference system on Ariane 5 Flight 501 to fail?",
    "api": "Why was the Mars Climate Orbiter lost?",
}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args(argv)
    run_dir = new_run_dir(args.run_id, prefix="query_check")
    timer = Timer()
    with tee_output(run_dir / "log.txt"):
        write_json(run_dir / "config.json", {"settings": get_settings().public_dict(), "questions": QUESTIONS})
        write_json(run_dir / "env.json", environment_info())

        from backend.rag_pipeline import MissionMindGraphRAG
        with timer.step("cli_query"):
            rag = MissionMindGraphRAG(top_k=3)
            answer = rag.query(QUESTIONS["cli"], stream=False)
            results = rag.retriever.hybrid_search(QUESTIONS["cli"], top_k=3)
        write_json(run_dir / "cli_response.json", {
            "question": QUESTIONS["cli"], "answer": answer,
            "retrieved": [{k: r[k] for k in ("chunk_id", "score", "facts", "related_failures")} for r in results]})

        from fastapi.testclient import TestClient
        from backend.main import app
        with timer.step("api_query"):
            with TestClient(app) as client:
                health = client.get("/")
                resp = client.post("/query", json={"question": QUESTIONS["api"], "top_k": 3})
        write_json(run_dir / "api_response.json", {"health_status": health.status_code,
                                                   "status": resp.status_code, "body": resp.json()})
        print(f"API health {health.status_code}, /query {resp.status_code}")
        rag.close()
        write_json(run_dir / "timings.json", timer.timings)
        ok = health.status_code == 200 and resp.status_code == 200 and bool(answer.strip())
        print(f"QUERY CHECK {'PASSED' if ok else 'FAILED'} — artefacts in {run_dir}")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
