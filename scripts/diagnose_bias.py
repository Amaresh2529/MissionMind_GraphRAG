"""
diagnose_bias.py — label-free check whether a system ranks missions by how MUCH their reports say rather than by
causal similarity (document-length / document-type bias; external review suggestion, 2026-10-13).

    python scripts/diagnose_bias.py --run runs/<retrieval_run> --out runs/<id>

For every system: how often each candidate mission appears in the top-5 of other missions' queries, correlated
(Spearman) with the mission's corpus size (indexed passages) and with its factor-profile size (number of verified
categories). A strong positive correlation means long reports are favoured regardless of the query. Also reports
top-5 frequency for full board reports vs shorter documents (summaries, slides, press releases).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from retrieval.corpus import load_units, manifest  # noqa: E402


def spearman(x: list[float], y: list[float]) -> float | None:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    if len(x) < 3:
        return None
    rx, ry = ranks(x), ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    man = manifest()
    size = Counter(m for u in load_units(None) for m in u.missions)
    fg = json.loads((ROOT / "runs/stage4_factor_graph_r2/factor_graph.json").read_text(encoding="utf-8"))["profiles"]
    full = {m for d in man.values() if d["role"] == "primary" and d["doc_type"] == "official_investigation_report"
            for m in d["mission_ids"]}
    res = {}
    for f in sorted((Path(args.run) / "predictions").glob("*.jsonl")):
        rows = [json.loads(l) for l in open(f, encoding="utf-8")]
        cnt = Counter(m for r in rows for m in [x for x in r["mission_ranking"] if x != r["mission"]][:5])
        ms = sorted(size)
        freq = [cnt.get(m, 0) for m in ms]
        n_q = len(rows)
        cand_full = [m for m in ms if m in full]
        cand_short = [m for m in ms if m not in full]
        res[f.stem] = {"rho_top5_vs_passages": spearman(freq, [size[m] for m in ms]),
                       "rho_top5_vs_profile_size": spearman(freq, [len(fg.get(m, {})) for m in ms]),
                       "top5_rate_full_reports": round(sum(cnt[m] for m in cand_full) / max(1, n_q * len(cand_full)), 3),
                       "top5_rate_short_docs": round(sum(cnt[m] for m in cand_short) / max(1, n_q * len(cand_short)), 3),
                       "most_frequent_top5": cnt.most_common(5)}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    (out / "bias_diagnostic.json").write_text(json.dumps({"run": args.run, "systems": res}, indent=1), encoding="utf-8")
    for s, v in res.items():
        print(f"{s:16s} rho(passages)={v['rho_top5_vs_passages']} rho(profile)={v['rho_top5_vs_profile_size']} "
              f"top5 full={v['top5_rate_full_reports']} short={v['top5_rate_short_docs']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
