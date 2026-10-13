"""
extract_factors.py — runs the Stage 4 evidence-anchored extractor over every
Summary/Causes passage of the primary corpus (>= MIN_WORDS words).

Writes data/processed/factors/<doc_id>.jsonl (one record per passage: accepted
and rejected factors with reasons) and runs/<run_id>/{config,env,stats,timings}.json.
Resumable: the LLM cache makes a restarted run skip finished passages.

    python scripts/extract_factors.py --run-id stage4_extract_all
"""

import argparse
import collections
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from config import get_settings  # noqa: E402
from runlog import Timer, environment_info, new_run_dir, tee_output, write_json  # noqa: E402
from retrieval.corpus import load_units, manifest  # noqa: E402
from extension import factor_extractor as fx  # noqa: E402

MIN_WORDS = 20


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--docs", nargs="*")
    args = ap.parse_args(argv)
    run, timer = new_run_dir(args.run_id, prefix="extract"), Timer()
    man = manifest()
    with tee_output(run / "log.txt"):
        write_json(run / "env.json", environment_info(include_services=True))
        units = [u for u in load_units(None) if u.field in ("summary", "causes") and len(u.text.split()) >= MIN_WORDS
                 and (not args.docs or u.doc_id in args.docs)]
        write_json(run / "config.json", {"args": vars(args), "min_words": MIN_WORDS, "min_quote_words": fx.MIN_QUOTE_WORDS,
                                         "num_ctx": fx.NUM_CTX, "model": get_settings().llm_model,
                                         "taxonomy_version": fx.taxonomy()["version"], "passages": len(units)})
        out_dir = get_settings().processed_dir / "factors"
        out_dir.mkdir(parents=True, exist_ok=True)
        by_doc = collections.defaultdict(list)
        for u in units:
            by_doc[u.doc_id].append(u)
        stats = collections.Counter()
        reasons, codes = collections.Counter(), collections.Counter()
        t0 = time.time()
        done = 0
        for doc, us in sorted(by_doc.items()):
            with timer.step(doc):
                rows = []
                for u in us:
                    r = fx.extract(u, man[doc]["title"])
                    rows.append(r)
                    stats["passages"] += 1
                    stats["cached"] += r["cached"]
                    stats["parse_fail"] += not r["parse_ok"]
                    stats["proposed"] += len(r["accepted"]) + len(r["rejected"])
                    stats["accepted"] += len(r["accepted"])
                    stats["passages_with_factor"] += bool(r["accepted"])
                    reasons.update(x["reason"] for x in r["rejected"])
                    codes.update(x["code"] for x in r["accepted"])
                    done += 1
                    if done % 200 == 0:
                        print(f"{done}/{len(units)} passages, {time.time() - t0:.0f} s, accepted {stats['accepted']}", flush=True)
                tmp = out_dir / f"{doc}.jsonl.tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    for r in rows:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                tmp.replace(out_dir / f"{doc}.jsonl")
        write_json(run / "stats.json", {**stats, "rejection_reasons": dict(reasons), "accepted_by_code": dict(codes.most_common())})
        write_json(run / "timings.json", timer.timings)
        print(json.dumps({**stats, "rejection_reasons": dict(reasons)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
