"""
embeddings.py

BERT-based semantic embeddings for cross-mission failure comparison.

This is the piece that turns "two failures use different words for the same
underlying cause" into a graph edge. NER (ner_model.py) tells you what field
values are present in a chunk; this module tells you which failures across
DIFFERENT missions are actually about the same kind of problem, even when
their root-cause wording doesn't share a single keyword.

Uses the same all-MiniLM-L6-v2 sentence-transformer already used for chunk
retrieval elsewhere in the pipeline (consistent embedding space, no second
model to maintain) — it's a distilled BERT variant, matching your stack table.

This module only computes embeddings and similarity — it doesn't touch Neo4j.
graph_builder.py is where the resulting pairs become MERGE'd edges.
"""

from dataclasses import dataclass
from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_SIMILARITY_THRESHOLD = 0.65  # placeholder — calibrate before trusting this in the paper, see below

_embedder = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(MODEL_NAME)
    return _embedder


@dataclass
class FailureRecord:
    """One failure node's identity + the text used to compare it against others.
    mission/subsystem/failure_mode/root_cause come from graph_builder.py's
    per-chunk extraction (NER fields + LLM fallback merged); embedding_text
    is what actually gets embedded — failure mode + root cause together gives
    the comparison more signal than root cause alone.
    """
    mission: str
    subsystem: str
    failure_mode: str
    root_cause: str

    @property
    def embedding_text(self) -> str:
        return f"{self.failure_mode}. {self.root_cause}"


def embed_failures(records: list[FailureRecord]):
    """Encodes every failure record's text in one batch call (much faster than one-at-a-time)."""
    embedder = get_embedder()
    texts = [r.embedding_text for r in records]
    return embedder.encode(texts, show_progress_bar=False, convert_to_tensor=True)


def find_cross_mission_similarities(
    records: list[FailureRecord],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    Compares every failure record against every other, keeps pairs that are
    both semantically close AND from different missions (same-mission pairs
    are already connected structurally — that's not new information).

    Returns one dict per qualifying pair, sorted highest-similarity first —
    the strongest cross-mission matches are what you'd lead with as example
    queries in the paper.
    """
    if len(records) < 2:
        return []

    embeddings = embed_failures(records)
    sim_matrix = util.cos_sim(embeddings, embeddings)

    pairs = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if records[i].mission == records[j].mission:
                continue  # only cross-mission connections are new information

            score = sim_matrix[i][j].item()
            if score >= threshold:
                pairs.append({
                    "mission_a": records[i].mission,
                    "mission_b": records[j].mission,
                    "subsystem_a": records[i].subsystem,
                    "subsystem_b": records[j].subsystem,
                    "failure_mode_a": records[i].failure_mode,
                    "failure_mode_b": records[j].failure_mode,
                    "root_cause_a": records[i].root_cause,
                    "root_cause_b": records[j].root_cause,
                    "similarity": round(score, 4),
                })

    pairs.sort(key=lambda p: p["similarity"], reverse=True)
    return pairs


def calibrate_threshold(known_similar_pairs: list[tuple], known_dissimilar_pairs: list[tuple]) -> float:
    """
    Suggests a threshold: the midpoint between the lowest similarity among
    pairs you've manually judged genuinely related, and the highest similarity
    among pairs you've judged unrelated. Run this once you've hand-labeled a
    handful of pairs (reuse a few from your metrics.py test set) — don't ship
    the 0.65 default in the paper without justifying it this way; a reviewer
    will ask where that number came from.
    """
    embedder = get_embedder()

    def pair_score(pair):
        texts = [pair[0].embedding_text, pair[1].embedding_text]
        emb = embedder.encode(texts, show_progress_bar=False)
        return util.cos_sim(emb[0], emb[1]).item()

    similar_scores = [pair_score(p) for p in known_similar_pairs]
    dissimilar_scores = [pair_score(p) for p in known_dissimilar_pairs]

    if not similar_scores or not dissimilar_scores:
        print("Need at least one example of each to calibrate — returning default.")
        return DEFAULT_SIMILARITY_THRESHOLD

    floor = min(similar_scores)
    ceiling = max(dissimilar_scores)
    if floor <= ceiling:
        print(f"⚠️  No clean separation: similar-pair floor ({floor:.3f}) <= "
              f"dissimilar-pair ceiling ({ceiling:.3f}). Inspect the borderline "
              f"pairs before trusting a threshold — your categories may overlap.")
    return round((floor + ceiling) / 2, 4)


if __name__ == "__main__":
    example_records = [
        FailureRecord(
            mission="STS-51-L Challenger",
            subsystem="Solid Rocket Booster",
            failure_mode="O-ring seal erosion",
            root_cause="Low ambient temperature reduced seal resiliency, allowing hot gas blow-by",
        ),
        FailureRecord(
            mission="ExoMars Schiaparelli",
            subsystem="Guidance Navigation and Control",
            failure_mode="Premature parachute jettison",
            root_cause="IMU saturation caused a false negative altitude reading, an unanticipated sensor limit under real conditions",
        ),
        FailureRecord(
            mission="Mars Climate Orbiter",
            subsystem="Navigation Software",
            failure_mode="Trajectory miscalculation",
            root_cause="Unit mismatch between metric and English units in ground software, a specification gap not caught before flight",
        ),
    ]
    results = find_cross_mission_similarities(example_records)
    for r in results:
        print(f"{r['mission_a']} <-> {r['mission_b']}  (similarity: {r['similarity']})")