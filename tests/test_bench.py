"""Stage 5 metric and statistics definitions on hand-computed cases (no real labels involved)."""
import math

import pytest

from bench import metrics as M, stats as S


def test_ndcg_linear_gains():
    gains = {"a": 3, "b": 2, "c": 0, "d": 1}
    assert M.ndcg_at_k(["a", "b", "d"], gains, 3) == pytest.approx(1.0)
    got = M.ndcg_at_k(["c", "a"], gains, 2)
    assert got == pytest.approx((3 / math.log2(3)) / (3 + 2 / math.log2(3)))
    assert M.ndcg_at_k(["a"], {"a": 0}, 5) is None


def test_recall_normrecall_mrr_prf():
    assert M.recall_at_k(["a", "x", "b"], {"a", "b", "c"}, 2) == pytest.approx(1 / 3)
    assert M.norm_recall_at_k(["a", "b"], {"a", "b", "c"}, 2) == pytest.approx(1.0)   # min(k, |gold|) = 2
    assert M.mrr(["x", "y", "a"], {"a"}) == pytest.approx(1 / 3) and M.mrr(["x"], {"a"}) == 0.0
    r = M.prf({1, 2, 3}, {2, 3, 4, 5})
    assert (r["precision"], r["recall"]) == (pytest.approx(2 / 3), pytest.approx(0.5))
    assert M.mean([1.0, None, 3.0]) == 2.0


def test_permutation_exact_and_identical():
    same = S.paired_permutation([0.5, 0.4, 0.3], [0.5, 0.4, 0.3])
    assert same["p"] == 1.0 and same["mean_diff"] == 0
    d = S.paired_permutation([1, 1, 1, 1, 1], [0, 0, 0, 0, 0])
    assert d["exact"] and d["p"] == pytest.approx(2 / 32)          # only all-plus / all-minus as extreme
    assert S.paired_permutation([1, None], [0, 0])["n"] == 1


def test_bootstrap_and_holm():
    ci = S.bootstrap_ci([1, 1, 1, 1], [0, 0, 0, 0])
    assert ci["low"] == ci["high"] == 1.0
    adj = S.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)


def test_evaluate_run_end_to_end_on_synthetic_labels(tmp_path):
    """Plumbing check with SYNTHETIC labels written to a temp dir (never the real sheets)."""
    import csv
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from evaluate import compare, evaluate_run
    from bench.labels import Labels

    def w(name, header, rows):
        with open(tmp_path / name, "w", encoding="utf-8-sig", newline="") as f:
            cw = csv.writer(f); cw.writerow(header); cw.writerows(rows)
    w("D2b_mission_pairs.csv", ["pair_id", "mission_a", "mission_b", "grade", "shared_codes", "note"],
      [["P1", "q", "a", "3", "V1", ""], ["P2", "q", "b", "0", "", ""], ["P3", "a", "b", "1", "M2", ""]])
    w("D2a_mission_factors.csv", ["mission", "factor_code", "role", "factor_short", "doc_id", "page", "quote", "note"],
      [["a", "V1", "root", "x", "Da", "4", "", ""]])
    labels = Labels(tmp_path)
    run = tmp_path / "run"; (run / "predictions").mkdir(parents=True)
    good = {"query_id": "T1-q", "mission": "q", "mission_ranking": ["a", "b"],
            "passages": [{"id": "Da::p0004::00"}, {"id": "Db::p0001::00"}]}
    bad = {"query_id": "T1-q", "mission": "q", "mission_ranking": ["b", "a"],
           "passages": [{"id": "Db::p0001::00"}, {"id": "Da::p0004::00"}]}
    (run / "predictions" / "P.jsonl").write_text(json.dumps(good) + "\n")
    (run / "predictions" / "B3.jsonl").write_text(json.dumps(bad) + "\n")
    units_by_page = {("Da", 4): ["Da::p0004::00"], ("Db", 1): ["Db::p0001::00"]}
    pq, summary = evaluate_run(run, labels, units_by_page)
    assert summary["P"]["mission_ndcg@5"] == pytest.approx(1.0)
    assert summary["B3"]["mission_ndcg@5"] == pytest.approx(1 / math.log2(3))
    assert summary["P"]["passage_normrecall@100"] == 1.0 and summary["P"]["mission_mrr"] == 1.0
    assert summary["B3"]["mission_mrr"] == 0.5
    c = compare(pq)
    assert c["primary"]["comparison"] == "P vs B3" and c["primary"]["permutation"]["n"] == 1
