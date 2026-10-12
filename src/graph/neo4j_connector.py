"""
neo4j_connector.py

Single shared Neo4j connection point for the whole project. Every other
module (graph_builder, neo4j_loader, retriever, rag_pipeline, main, run_eval)
imports get_driver() from here instead of opening its own
GraphDatabase.driver() with its own hardcoded URI/password.

Connection details come from config.py (environment / .env). There is no
default password: if NEO4J_PASSWORD is unset, get_driver() raises a clear
error rather than trying a guessed credential.
"""

import sys
from pathlib import Path

from neo4j import GraphDatabase

sys.path.append(str(Path(__file__).resolve().parent.parent))  # -> src/
from config import get_settings

_driver = None


class Neo4jConfigError(RuntimeError):
    pass


def get_driver():
    """Returns the single shared driver instance, creating it on first call."""
    global _driver
    if _driver is None:
        s = get_settings()
        if not s.neo4j_password:
            raise Neo4jConfigError(
                "NEO4J_PASSWORD is not set. Copy .env.example to .env and fill in the "
                "credentials of the Neo4j instance you intend to use."
            )
        # Server notifications (e.g. "relationship type SIMILAR_ROOT_CAUSE does not
        # exist" when a graph has no similarity edges yet) are informational and
        # flooded run logs; real errors still raise exceptions.
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_username, s.neo4j_password),
                                       notifications_min_severity="OFF")
    return _driver


def close_driver():
    """Call once at script exit."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def verify_connectivity() -> bool:
    """Fails fast with a clear message if Neo4j isn't reachable, instead
    of a confusing error surfacing deep inside a Cypher call later."""
    uri = get_settings().neo4j_uri
    try:
        get_driver().verify_connectivity()
        return True
    except Exception as err:
        print(f"⚠️  Could not connect to Neo4j at {uri}: {err}")
        print("   Check that the Neo4j instance named in .env is running.")
        return False


def server_info() -> dict:
    """Version/edition of the connected server, for run logs."""
    with get_driver().session() as session:
        rec = session.run(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions[0] AS version, edition"
        ).single()
    return {"name": rec["name"], "version": rec["version"], "edition": rec["edition"],
            "uri": get_settings().neo4j_uri}


if __name__ == "__main__":
    if verify_connectivity():
        print(f"✅ Connected to Neo4j at {get_settings().neo4j_uri}")
    close_driver()
