"""
passage_loader.py

Loads Stage 2 page-aware passages (data/processed/passages/<doc_id>.jsonl)
into Neo4j as :Passage nodes with full provenance (doc_id, page,
char_start, char_end, section, chapter, pseudo_field) and an embedding, and
links them to their :Document. Where a curated field map has been applied
(data/processed/fields/<doc_id>.jsonl, scripts/field_map_tool.py apply), each
passage also carries `field` (description | analysis | recommendations | other)
and `field_map_status` (draft | reviewed); otherwise both are null.

Re-ingestion is refresh-on-change (fixes the Stage 1 stale-data defect):
  - new passage id            -> inserted (embedded)
  - same id, different content -> updated (re-embedded)
  - same id, same content      -> skipped
  - id no longer produced      -> deleted
"Content" is a SHA-256 over every stored property, so a changed page number
or pseudo-field is also refreshed, not only changed text.

:Passage nodes live beside the Stage 1 :Chunk nodes; baseline B4 is unaffected.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings
from graph.neo4j_connector import get_driver

INDEX_NAME = "passage_vector_index"
_PROPS = ("doc_id", "page", "char_start", "char_end", "section", "chapter", "pseudo_field",
          "n_words", "source", "low_quality", "text", "field", "field_map_status")


def content_hash(p: dict) -> str:
    payload = json.dumps({k: p.get(k) for k in _PROPS}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def plan_changes(existing: dict[str, str], current: list[dict]) -> dict:
    """Pure diff: existing {id: hash} vs current passages -> what to do."""
    cur = {p["passage_id"]: content_hash(p) for p in current}
    return {
        "insert": [pid for pid in cur if pid not in existing],
        "update": [pid for pid in cur if pid in existing and existing[pid] != cur[pid]],
        "unchanged": [pid for pid in cur if existing.get(pid) == cur[pid]],
        "delete": [pid for pid in existing if pid not in cur],
    }


def load_passages(doc_id: str) -> list[dict]:
    base = get_settings().processed_dir
    with open(base / "passages" / f"{doc_id}.jsonl", encoding="utf-8") as f:
        passages = [json.loads(line) for line in f]
    fields_path = base / "fields" / f"{doc_id}.jsonl"
    if fields_path.exists():
        with open(fields_path, encoding="utf-8") as f:
            fields = {r["passage_id"]: r for r in map(json.loads, f)}
        for p in passages:
            r = fields.get(p["passage_id"])
            if r is None:
                raise ValueError(f"{doc_id}: field file is stale (no entry for {p['passage_id']}); re-run field_map_tool apply")
            p["field"], p["field_map_status"] = r["field"], r["map_status"]
    return passages


def ingest_passages(doc_ids: list[str] | None = None, embedder=None, batch_size: int = 64) -> dict:
    s = get_settings()
    passage_dir = s.processed_dir / "passages"
    files = sorted(passage_dir.glob("*.jsonl"))
    if doc_ids:
        files = [p for p in files if p.stem in set(doc_ids)]
    if embedder is None:
        from sentence_transformers import SentenceTransformer
        embedder = SentenceTransformer(s.embedding_model)
    dims = embedder.get_sentence_embedding_dimension()
    totals = {"insert": 0, "update": 0, "unchanged": 0, "delete": 0, "documents": len(files)}

    driver = get_driver()
    with driver.session() as session:
        session.run(f"""CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS FOR (p:Passage) ON (p.embedding)
                        OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dims)},
                                                 `vector.similarity_function`: 'cosine'}}}}""")
        session.run("CREATE CONSTRAINT passage_id IF NOT EXISTS FOR (p:Passage) REQUIRE p.id IS UNIQUE")
        for path in files:
            doc_id = path.stem
            passages = load_passages(doc_id)
            existing = {r["id"]: r["h"] for r in session.run(
                "MATCH (p:Passage {doc_id: $doc}) RETURN p.id AS id, p.content_hash AS h", doc=doc_id)}
            plan = plan_changes(existing, passages)
            todo = [p for p in passages if p["passage_id"] in set(plan["insert"]) | set(plan["update"])]
            for i in range(0, len(todo), batch_size):
                batch = todo[i:i + batch_size]
                vectors = embedder.encode([p["text"] for p in batch], show_progress_bar=False)
                rows = [{**{k: p.get(k) for k in _PROPS}, "id": p["passage_id"],
                         "content_hash": content_hash(p), "embedding": v.tolist()}
                        for p, v in zip(batch, vectors)]
                session.run("""
                    UNWIND $rows AS row
                    MERGE (d:Document {id: row.doc_id})
                    MERGE (p:Passage {id: row.id})
                    SET p += row
                    MERGE (d)-[:HAS_PASSAGE]->(p)
                """, rows=rows)
            if plan["delete"]:
                session.run("MATCH (p:Passage) WHERE p.id IN $ids DETACH DELETE p", ids=plan["delete"])
            for k in ("insert", "update", "unchanged", "delete"):
                totals[k] += len(plan[k])
            print(f"   {doc_id}: +{len(plan['insert'])} ~{len(plan['update'])} "
                  f"={len(plan['unchanged'])} -{len(plan['delete'])}")
    return totals


if __name__ == "__main__":
    print(ingest_passages(sys.argv[1:] or None))
