"""
proposed.py — the MissionMind method P and its ablations (Stage 4).

P = B3 (6 field x method lists, RRF k=60) + one GRAPH list from the verified
causal-factor graph, fused by the same RRF:

  1. Query factors: the evidence-anchored extractor runs on the query text (quotes
     verified against the query), giving a code set Q.
  2. Mission analogy: idf-weighted Jaccard between Q and each candidate mission's
     profile F_m (factor_graph.analogy); the query's own mission is excluded.
  3. Graph list: evidence passages of shared codes, ordered by mission analogy,
     then role (root > contributing > observation), then code idf, then passage id.
  If Q is empty the graph list is empty and P reduces to B3 (recorded per query).

Ablations (Proposal v2, Sec. 13):
  P-noverif     profiles also use rejected proposals with a valid code ("-verification")
  P-nofields    whole-index hybrid (H-whole) + graph list ("-fields")
  P-graphonly   graph list alone; missions ranked by analogy score ("graph only")
  P-noidf       analogy with all idf weights = 1 ("idf off")
"""

from dataclasses import dataclass

from extension import factor_graph as fg
from retrieval.systems import SYSTEMS, Retriever

ROLE_ORDER = fg.ROLE_ORDER


@dataclass
class QueryFactors:
    codes: set
    accepted: list
    rejected: list


class ProposedRetriever:
    def __init__(self, base: Retriever, mentions: list[dict], mentions_noverif: list[dict] | None = None):
        self.base = base
        self.index_of = {u.id: i for i, u in enumerate(base.units)}
        self.variants = {"verified": self._prepare(mentions)}
        if mentions_noverif is not None:
            self.variants["noverif"] = self._prepare(mentions_noverif)

    @staticmethod
    def _prepare(mentions: list[dict]) -> dict:
        prof = fg.profiles(mentions)
        return {"profiles": prof, "idf": fg.idf(prof)}

    def graph_list(self, qf: QueryFactors, allowed: set[int], exclude_missions: set[str],
                   variant: str = "verified", use_idf: bool = True) -> tuple[list[int], dict]:
        v = self.variants[variant]
        w = v["idf"] if use_idf else {}
        scores = {m: fg.analogy(qf.codes, set(p), w) for m, p in v["profiles"].items() if m not in exclude_missions}
        scores = {m: s for m, s in scores.items() if s > 0}
        cand = []
        for m, s in scores.items():
            for code in qf.codes & set(v["profiles"][m]):
                for e in v["profiles"][m][code]["evidence"]:
                    i = self.index_of.get(e["passage_id"])
                    if i is not None and i in allowed:
                        cand.append((-s, ROLE_ORDER.get(e["role"], 3), -v["idf"].get(code, 1.0), e["passage_id"], i))
        cand.sort()
        seen, out = set(), []
        for *_, i in cand:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out, scores

    def search(self, system: str, query: str, qf: QueryFactors, exclude_missions: set[str], k: int = 100) -> dict:
        allowed = self.base.allowed(exclude_missions)
        variant = "noverif" if system == "P-noverif" else "verified"
        glist, mscores = self.graph_list(qf, allowed, exclude_missions, variant, use_idf=(system != "P-noidf"))
        if system == "P-graphonly":
            lists = {"graph/factors": glist} if glist else {}
        else:
            base_cfg = SYSTEMS["H-whole"] if system == "P-nofields" else SYSTEMS["B3"]
            lists = self.base._lists(base_cfg, query, allowed)
            if glist:
                lists["graph/factors"] = glist
        if lists:
            out = self.base.assemble(system, lists, k)
        else:
            out = {"system": system, "lists": [], "passages": [], "mission_ranking": []}
        if system == "P-graphonly":           # missions by analogy score directly
            out["mission_ranking"] = [m for m, _ in sorted(mscores.items(), key=lambda x: (-x[1], x[0]))]
        out["graph"] = {"query_codes": sorted(qf.codes), "graph_list_len": len(glist),
                        "fallback_to_base": not glist,
                        "mission_analogy": {m: round(s, 4) for m, s in sorted(mscores.items(), key=lambda x: (-x[1], x[0]))[:10]}}
        return out


def query_factors(query: str, extract_fn) -> QueryFactors:
    """extract_fn: callable(unit-like, title) -> extractor record (factor_extractor.extract)."""
    from types import SimpleNamespace
    pseudo = SimpleNamespace(id="query", text=query, section=None, page=0, doc_id="query", missions=(),
                             field="query", char_start=0)
    r = extract_fn(pseudo, "New mishap description (query)")
    return QueryFactors({a["code"] for a in r["accepted"]}, r["accepted"], r["rejected"])
