"""Stage 4: evidence verification, factor graph, graph channel, citation enforcement (no LLM, no DB)."""
import math

import pytest

from extension import factor_graph as fg
from extension.factor_extractor import codes, locate_quote, verify
from extension.grounded_generation import enforce
from extension.proposed import ProposedRetriever, QueryFactors
from retrieval.corpus import Unit
from retrieval.systems import Retriever

TEXT = "The Board found that the O-ring  seals were never tested at\nlow temperature before flight."


def test_locate_quote_normalises_whitespace_case_and_maps_back():
    span = locate_quote(TEXT, "o-ring seals were never tested at low temperature")
    assert span is not None
    assert TEXT[span[0]:span[1]] == "O-ring  seals were never tested at\nlow temperature"
    assert locate_quote(TEXT, "seals were tested at high temperature") is None


def test_verify_rules():
    valid = set(codes())
    ok, reason, _ = verify({"code": "V1", "role": "root", "quote": "seals were never tested at low temperature"}, TEXT, valid)
    assert ok and reason == "ok"
    assert verify({"code": "X9", "role": "root", "quote": "seals were never tested at low"}, TEXT, valid)[1] == "bad_code"
    assert verify({"code": "V1", "role": "maybe", "quote": "seals were never tested at low"}, TEXT, valid)[1] == "bad_role"
    assert verify({"code": "V1", "role": "root", "quote": "never tested"}, TEXT, valid)[1] == "quote_too_short"
    assert verify({"code": "V1", "role": "root", "quote": "the board invented this quote here"}, TEXT, valid)[1] == "quote_not_in_passage"


def test_taxonomy_has_22_codes():
    assert len(codes()) == 22


def _m(pid, missions, code, role):
    return {"passage_id": pid, "doc_id": pid.split("::")[0], "page": 1, "missions": missions, "code": code,
            "role": role, "statement": "", "quote": "q", "char_start": 0, "char_end": 1}


MENTIONS = [
    _m("Da::p0001::00", ["a"], "V1", "root"), _m("Da::p0001::00", ["a"], "M2", "contributing"),
    _m("Db::p0001::00", ["b"], "V1", "contributing"), _m("Db::p0002::00", ["b"], "T5", "root"),
    _m("Dc::p0001::00", ["c"], "M2", "root"), _m("Dc::p0002::00", ["c"], "V1", "observation"),
    _m("Dd::p0001::00", ["d"], "T2", "root"),
]


def test_profiles_idf_and_analogy():
    prof = fg.profiles(MENTIONS)
    assert set(prof) == {"a", "b", "c", "d"} and set(prof["a"]) == {"V1", "M2"}
    w = fg.idf(prof)
    assert w["V1"] == pytest.approx(math.log(4 / 3) + 1) and w["T2"] == pytest.approx(math.log(4) + 1)
    assert fg.analogy({"V1", "M2"}, {"V1", "M2"}, w) == 1.0
    assert fg.analogy({"V1"}, {"T2"}, w) == 0.0
    expected = w["V1"] / (w["V1"] + w["M2"] + w["T5"])
    assert fg.analogy({"V1", "M2"}, {"V1", "T5"}, w) == pytest.approx(expected)


def _unit(pid, mission):
    return Unit(pid, pid.split("::")[0], (mission,), "causes", 1, 0, 10, None, f"text of {pid} seal test")


@pytest.fixture
def prop():
    units = [_unit(p, p[1]) for p in ["Da::p0001::00", "Db::p0001::00", "Db::p0002::00", "Dc::p0001::00",
                                      "Dc::p0002::00", "Dd::p0001::00"]]
    return ProposedRetriever(Retriever(units, None), MENTIONS)


def test_graph_list_orders_by_analogy_then_role_and_excludes_query_mission(prop):
    qf = QueryFactors({"V1", "M2"}, [], [])
    allowed = prop.base.allowed({"a"})
    glist, scores = prop.graph_list(qf, allowed, {"a"})
    ids = [prop.base.units[i].id for i in glist]
    assert "a" not in scores and set(scores) == {"b", "c"}
    assert scores["c"] > scores["b"]                       # c shares V1 and M2, b only V1
    assert ids == ["Dc::p0001::00", "Dc::p0002::00", "Db::p0001::00"]   # c first; root before observation


def test_empty_query_factors_fall_back(prop):
    qf = QueryFactors(set(), [], [])
    glist, scores = prop.graph_list(qf, prop.base.allowed(set()), set())
    assert glist == [] and scores == {}


def test_enforce_drops_uncited_and_abstains():
    ans = {"probable_root_causes": [{"cause": "x", "evidence": ["C1", "C9"]}, {"cause": "y", "evidence": []}],
           "contributing_factors": [], "similar_precedents": [], "recommended_actions": [{"action": "z", "evidence": ["C7"]}]}
    out, st = enforce(ans, {"C1", "C2"})
    assert out["probable_root_causes"] == [{"cause": "x", "evidence": ["C1"]}]
    assert out["recommended_actions"] == [] and st == {"abstain": False, "dropped_items": 2, "removed_citations": 2,
                                                            "generic_dropped": 0,
                                                            "cause_items_raw": 2, "cause_items_kept": 1}
    out2, st2 = enforce({k: [] for k in ("probable_root_causes", "contributing_factors", "similar_precedents",
                                         "recommended_actions")}, {"C1"})
    assert st2["abstain"] and "abstained" in out2
    assert enforce(None, set())[1]["abstain"]


def test_p2_drops_generic_category_items():
    names = {"Procedure deficient or not followed", "Hardware design deficiency"}
    ans = {"probable_root_causes": [{"cause": "Procedure deficient or not followed", "evidence": ["C1"]},
                                    {"cause": "Thermostatic switches rated for 28 V failed at 65 V", "evidence": ["C1"]}],
           "contributing_factors": [], "similar_precedents": [], "recommended_actions": []}
    out, st = enforce(ans, {"C1"}, names)
    assert [x["cause"] for x in out["probable_root_causes"]] == ["Thermostatic switches rated for 28 V failed at 65 V"]
    assert st["generic_dropped"] == 1


def test_p2_weights_graph_list_and_filters_generic_codes(tmp_path, monkeypatch):
    from extension import proposed as pr
    from config import get_settings
    from test_retrieval import FakeEmbedder
    monkeypatch.setattr(type(get_settings()), "processed_dir", property(lambda self: tmp_path), raising=True)
    mentions = MENTIONS + [_m("Dd::p0001::00", ["d"], "V1", "observation")]       # V1 now in all 4 missions
    units = [_unit(p, p[1]) for p in ["Da::p0001::00", "Db::p0001::00", "Db::p0002::00", "Dc::p0001::00",
                                      "Dc::p0002::00", "Dd::p0001::00"]]
    prop2 = ProposedRetriever(Retriever(units, FakeEmbedder()), mentions)
    monkeypatch.setattr(prop2, "expanded_codes", lambda qf, q, ex, v="verified": ({"V1", "M2"}, {"V1", "M2"}))
    qf = QueryFactors(set(), [], [])
    out = prop2.search("P2", "seal test", qf, exclude_missions={"a"})
    assert out["graph"]["graph_weight"] == pr.GRAPH_WEIGHT
    assert out["graph"]["generic_codes_dropped"] == ["V1"] and out["graph"]["query_codes"] == ["M2"]
    out_nf = prop2.search("P2-nofilter", "seal test", qf, exclude_missions={"a"})
    assert out_nf["graph"]["generic_codes_dropped"] == [] and out_nf["graph"]["query_codes"] == ["M2", "V1"]
    out_p = prop2.search("P", "seal test", qf, exclude_missions={"a"})
    assert out_p["graph"]["graph_weight"] == 1.0


def test_mechanism_block_and_qa_generic_enforcement():
    from extension.grounded_generation import mechanism_block
    from extension.qa import _enforce
    assert mechanism_block({}) == ""
    blk = mechanism_block({"C10": "the seal eroded", "C2": "the switch welded shut"})
    assert blk.index("[C2]") < blk.index("[C10]")
    ans = {"answer": "a", "abstain": False, "key_points": [
        {"point": "Hardware design deficiency", "evidence": ["C1"]},
        {"point": "Switches rated for 28 V could not open at 65 V", "evidence": ["C1"]}]}
    out, st = _enforce(ans, {"C1"}, {"Hardware design deficiency"})
    assert [k["point"] for k in out["key_points"]] == ["Switches rated for 28 V could not open at 65 V"]
    assert st["generic_dropped"] == 1 and st["points_raw"] == 2 and st["points_kept"] == 1


def test_enforce_reports_retention():
    ans = {"probable_root_causes": [{"cause": "Procedure deficient or not followed", "evidence": ["C1"]},
                                    {"cause": "Valve seat cracked under thermal cycling", "evidence": ["C1"]}],
           "contributing_factors": [{"factor": "x", "evidence": []}], "similar_precedents": [], "recommended_actions": []}
    out, st = enforce(ans, {"C1"}, {"Procedure deficient or not followed"})
    assert st["cause_items_raw"] == 3 and st["cause_items_kept"] == 1
