"""
build_factor_graph.py — builds mission causal-factor profiles from data/processed/factors and
writes them to Neo4j (Stage 4). Rebuilds the factor edges from scratch each run.

    python scripts/build_factor_graph.py --run-id stage4_factor_graph
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from runlog import environment_info, new_run_dir, tee_output, write_json  # noqa: E402
from extension import factor_extractor as fx, factor_graph as fg  # noqa: E402
from graph.neo4j_connector import close_driver  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args(argv)
    run = new_run_dir(args.run_id, prefix="factor_graph")
    with tee_output(run / "log.txt"):
        write_json(run / "env.json", environment_info(include_services=True))
        mentions = fg.load_mentions()
        prof = fg.profiles(mentions)
        w = fg.idf(prof)
        counts = fg.write_neo4j(prof, fx.codes())
        pairs = {}
        ms = sorted(prof)
        for i, a in enumerate(ms):
            for b in ms[i + 1:]:
                pairs[f"{a}|{b}"] = round(fg.analogy(set(prof[a]), set(prof[b]), w), 4)
        write_json(run / "factor_graph.json", {
            "mentions": len(mentions), "missions": len(prof), "neo4j": counts,
            "idf": {c: round(x, 4) for c, x in sorted(w.items())},
            "profiles": {m: {c: {"roles": dict(e["roles"]), "n_evidence": len(e["evidence"])} for c, e in sorted(p.items())}
                         for m, p in sorted(prof.items())},
            "pairwise_analogy_top20": dict(sorted(pairs.items(), key=lambda x: -x[1])[:20])})
        print(json.dumps({"mentions": len(mentions), "missions": len(prof), "neo4j": counts}))
    close_driver()
    return 0


if __name__ == "__main__":
    sys.exit(main())
