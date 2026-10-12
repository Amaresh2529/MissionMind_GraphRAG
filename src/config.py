"""
config.py

Single source of runtime settings for MissionMind. Every module reads its
connection details, model identifiers and paths from here instead of
hard-coding them, so that a run's configuration can be recorded in one place
(see runlog.py) and baseline/proposed runs can differ only by environment.

Values come from environment variables, optionally loaded from a local `.env`
file (git-ignored). `.env.example` lists every variable.

Deliberately NO default for NEO4J_PASSWORD: a missing password now fails with
a clear message instead of silently trying a hard-coded one.
"""

import os
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — plain environment variables still work

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str | None
    llm_model: str
    llm_temperature: float
    llm_seed: int
    embedding_model: str
    data_dir: Path
    runs_dir: Path

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def chunks_dir(self) -> Path:
        return self.processed_dir / "chunks"

    def public_dict(self) -> dict:
        """Settings safe to write into run logs (password removed)."""
        d = asdict(self)
        d["neo4j_password"] = "***set***" if self.neo4j_password else None
        d["data_dir"] = str(self.data_dir)
        d["runs_dir"] = str(self.runs_dir)
        return d


def get_settings() -> Settings:
    """Re-reads the environment on every call so tests can override variables."""
    return Settings(
        neo4j_uri=_env("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_username=_env("NEO4J_USERNAME", "neo4j"),
        neo4j_password=_env("NEO4J_PASSWORD"),
        llm_model=_env("MISSIONMIND_LLM_MODEL", "llama3"),
        llm_temperature=float(_env("MISSIONMIND_LLM_TEMPERATURE", "0")),
        llm_seed=int(_env("MISSIONMIND_LLM_SEED", "42")),
        embedding_model=_env("MISSIONMIND_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        data_dir=Path(_env("MISSIONMIND_DATA_DIR", str(PROJECT_ROOT / "data"))),
        runs_dir=Path(_env("MISSIONMIND_RUNS_DIR", str(PROJECT_ROOT / "runs"))),
    )
