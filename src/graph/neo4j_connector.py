"""
neo4j_connector.py

Single shared Neo4j connection point for the whole project. Every other
module (graph_builder, neo4j_loader, retriever, rag_pipeline, main) should
import get_driver() from here instead of each opening its own
GraphDatabase.driver() with its own hardcoded URI/password.

Reads from environment variables when present — a .env file (already in
your .gitignore) is the right place for these — and falls back to your
local Neo4j defaults so nothing breaks if you haven't set one up yet.
"""

import os
from neo4j import GraphDatabase

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — env vars still work if set some other way

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

_driver = None


def get_driver():
    """Returns the single shared driver instance, creating it on first call."""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    return _driver


def close_driver():
    """Call once at script exit."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def verify_connectivity() -> bool:
    """Fails fast with a clear message if local Neo4j isn't running, instead
    of a confusing error surfacing deep inside a Cypher call later."""
    try:
        get_driver().verify_connectivity()
        return True
    except Exception as err:
        print(f"⚠️  Could not connect to Neo4j at {NEO4J_URI}: {err}")
        print("   Check that your local Neo4j instance is running.")
        return False


if __name__ == "__main__":
    if verify_connectivity():
        print(f"✅ Connected to Neo4j at {NEO4J_URI}")
    close_driver()