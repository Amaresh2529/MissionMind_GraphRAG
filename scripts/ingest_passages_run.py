import sys, json, time
sys.path.insert(0, "src")
from runlog import new_run_dir, write_json, environment_info, tee_output
from graph.passage_loader import ingest_passages
from graph.neo4j_connector import close_driver
run = new_run_dir(sys.argv[1], prefix="passage_ingest")
with tee_output(run / "log.txt"):
    write_json(run / "env.json", environment_info())
    t = time.time(); r1 = ingest_passages(); t1 = time.time() - t
    t = time.time(); r2 = ingest_passages(); t2 = time.time() - t   # second run must change nothing
    write_json(run / "result.json", {"first": r1, "first_seconds": round(t1, 1), "second": r2, "second_seconds": round(t2, 1)})
    print("FIRST", r1, round(t1, 1), "s\nSECOND", r2, round(t2, 1), "s")
close_driver()
