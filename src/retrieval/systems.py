"""
systems.py — retrieval configurations of the base paper (Kim & Kim, IEEE CASE 2026),
re-implemented over MissionMind passages.

  id               index        methods         paper counterpart
  B1               whole        bm25            whole-document BM25
  B2               whole        dense           whole-document dense
  H-whole          whole        bm25+dense RRF  whole-document hybrid
  SF-summary-*     summary only bm25|dense|hybrid  single-field (Summary)
  SF-causes-*      causes only  bm25|dense|hybrid  single-field (Causes)
  B3               3 fields     6 lists RRF     proposed multi-field hybrid (k_rrf = 60)

"whole": one index over all three fields' passages (the paper concatenates the
three short fields of a card into one chunk; MissionMind reports are far too
long for that, so the whole-document analogue is a single passage index).
Per-field BM25 indexes compute idf within the field, as separate indexes do.

Leave-one-mission-out: units belonging to any of the query's missions are
removed before ranking. Each ranked list is cut at LIST_DEPTH before fusion
(the paper does not state a depth).
"""

from dataclasses import dataclass

from retrieval.bm25 import BM25Index
from retrieval.corpus import FIELDS, Unit
from retrieval.dense import DenseIndex
from retrieval.fusion import K_RRF, rrf

LIST_DEPTH = 1000
TOP_K = 100          # paper: retrieval evaluated at k = 100


@dataclass(frozen=True)
class SystemConfig:
    id: str
    fields: tuple[str, ...] | None     # None = whole (single index over all fields)
    methods: tuple[str, ...]           # "bm25", "dense"
    field_balanced: bool = False       # B3-bal: each field's lists weighted by the field's share of units


def _sf(field: str) -> list[SystemConfig]:
    return [SystemConfig(f"SF-{field}-bm25", (field,), ("bm25",)),
            SystemConfig(f"SF-{field}-dense", (field,), ("dense",)),
            SystemConfig(f"SF-{field}-hybrid", (field,), ("bm25", "dense"))]


SYSTEMS = {c.id: c for c in [
    SystemConfig("B1", None, ("bm25",)),
    SystemConfig("B2", None, ("dense",)),
    SystemConfig("H-whole", None, ("bm25", "dense")),
    *_sf("summary"), *_sf("causes"),
    SystemConfig("B3", FIELDS, ("bm25", "dense")),
    # Secondary baseline (decided 2026-10-13, before any test label exists): Stage 3 found B3's top-100
    # dominated by the 187-unit Disposition field; here each field's RRF contribution is multiplied by
    # 3 * n_field / n_total, so fields count in proportion to their size (weights average to 1).
    SystemConfig("B3-bal", FIELDS, ("bm25", "dense"), field_balanced=True),
]}


class Retriever:
    """Builds every index once; `search` runs any configuration."""

    def __init__(self, units: list[Unit], embedder=None):
        self.units = units
        texts = [u.text for u in units]
        self.whole_bm25 = BM25Index(texts)
        self.field_members = {f: [i for i, u in enumerate(units) if u.field == f] for f in FIELDS}
        self.field_bm25 = {f: BM25Index([texts[i] for i in idx]) for f, idx in self.field_members.items()}
        self.dense = DenseIndex([u.id for u in units], texts, embedder) if embedder is not None else None

    def _lists(self, cfg: SystemConfig, query: str, allowed: set[int]) -> dict[str, list[int]]:
        out = {}
        for method in cfg.methods:
            if method == "dense" and self.dense is None:
                raise RuntimeError(f"{cfg.id} needs a dense embedder")
            if cfg.fields is None:
                if method == "bm25":
                    ranked = self.whole_bm25.rank(query, allowed, LIST_DEPTH)
                else:
                    ranked = self.dense.rank(query, allowed, LIST_DEPTH)
                out[f"whole/{method}"] = [i for i, _ in ranked]
                continue
            for f in cfg.fields:
                members = self.field_members[f]
                if method == "bm25":
                    local_allowed = {j for j, i in enumerate(members) if i in allowed}
                    ranked = [(members[j], s) for j, s in self.field_bm25[f].rank(query, local_allowed, LIST_DEPTH)]
                else:
                    ranked = self.dense.rank(query, allowed & set(members), LIST_DEPTH)
                out[f"{f}/{method}"] = [i for i, _ in ranked]
        return out

    def allowed(self, exclude_missions: set[str]) -> set[int]:
        return {i for i, u in enumerate(self.units) if not exclude_missions.intersection(u.missions)}

    def field_weights(self, lists: dict[str, list]) -> dict[str, float]:
        n = len(self.units)
        return {name: len(FIELDS) * len(self.field_members[name.split("/")[0]]) / n
                for name in lists if name.split("/")[0] in self.field_members}

    def search(self, cfg: SystemConfig, query: str, exclude_missions: set[str] = frozenset(),
               k: int = TOP_K) -> dict:
        lists = self._lists(cfg, query, self.allowed(exclude_missions))
        return self.assemble(cfg.id, lists, k, self.field_weights(lists) if cfg.field_balanced else None)

    def assemble(self, system_id: str, lists: dict[str, list], k: int = TOP_K,
                 weights: dict[str, float] | None = None) -> dict:
        if len(lists) == 1:                      # single ranking: no fusion, report its own order
            (name, items), = lists.items()
            fused = [(i, 1.0 / (K_RRF + r), {name: r}) for r, i in enumerate(items, 1)]
        else:
            fused = rrf(lists, weights=weights)
        top = fused[:k]
        missions, seen = [], set()
        for i, _, _ in fused:                    # mission rank = first (best) passage of each mission
            for m in self.units[i].missions:
                if m not in seen:
                    seen.add(m)
                    missions.append(m)
        return {"system": system_id, "lists": sorted(lists),
                "passages": [{"rank": r, "id": self.units[i].id, "doc_id": self.units[i].doc_id,
                              "field": self.units[i].field, "page": self.units[i].page,
                              "score": round(s, 8), "list_ranks": lr}
                             for r, (i, s, lr) in enumerate(top, 1)],
                "mission_ranking": missions}
