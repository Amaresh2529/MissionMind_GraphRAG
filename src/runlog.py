"""
runlog.py

Run bookkeeping shared by run_pipeline.py and evalutation/run_eval.py: every
run gets its own directory runs/<run_id>/ containing

    config.json   settings actually used (password redacted) + CLI arguments
    env.json      Python/package versions, GPU, Ollama model digest, Neo4j server
    log.txt       full console output of the run
    timings.json  wall-clock seconds per step

so results can be traced to the exact configuration that produced them and
earlier runs are never overwritten (an existing run_id is refused).
"""

import datetime
import importlib.metadata as md
import json
import platform
import sys
import time
from contextlib import contextmanager
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))  # -> src/
from config import get_settings

_PACKAGES = ["torch", "sentence-transformers", "transformers", "spacy", "en-core-web-sm", "neo4j",
             "ollama", "fastapi", "pymupdf", "pytesseract", "pdf2image", "wordfreq", "numpy",
             "pandas", "python-dotenv", "pytest"]


def new_run_dir(run_id: str | None = None, prefix: str = "run") -> Path:
    run_id = run_id or f"{prefix}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = get_settings().runs_dir / run_id
    if run_dir.exists():
        raise FileExistsError(f"{run_dir} already exists — choose a new run id; earlier runs are never overwritten.")
    run_dir.mkdir(parents=True)
    return run_dir


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def package_versions() -> dict:
    versions = {}
    for name in _PACKAGES:
        try:
            versions[name] = md.version(name)
        except md.PackageNotFoundError:
            versions[name] = None
    return versions


def environment_info(include_services: bool = True) -> dict:
    info = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": package_versions(),
    }
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        info["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception as e:  # torch missing or broken: record, don't fail the run
        info["gpu_error"] = str(e)
    try:
        import subprocess
        info["git_commit"] = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                            text=True, cwd=Path(__file__).resolve().parent.parent).stdout.strip()
        info["git_dirty"] = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "evalutation", "run_pipeline.py"],
                                                capture_output=True, text=True,
                                                cwd=Path(__file__).resolve().parent.parent).stdout.strip())
    except Exception as e:
        info["git_error"] = str(e)
    if include_services:
        s = get_settings()
        try:
            import ollama
            listed = {m.model: m for m in ollama.list().models}
            entry = listed.get(s.llm_model) or listed.get(f"{s.llm_model}:latest")
            import os, urllib.request
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            host = host if host.startswith("http") else f"http://{host}"
            server = json.load(urllib.request.urlopen(f"{host}/api/version", timeout=10))
            info["llm"] = {"model": s.llm_model, "server": server,
                           "digest": entry.digest if entry else None,
                           "size_bytes": entry.size if entry else None,
                           "details": entry.details.model_dump() if entry and entry.details else None}
        except Exception as e:
            info["llm_error"] = str(e)
        try:
            from graph.neo4j_connector import server_info
            info["neo4j"] = server_info()
        except Exception as e:
            info["neo4j_error"] = str(e)
    return info


class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()

    def isatty(self):
        # Libraries (e.g. transformers' loading report) query this; a tee into
        # a log file is never an interactive terminal.
        return False

    def __getattr__(self, name):
        # encoding, errors, fileno, ... come from the primary (console) stream.
        return getattr(self.streams[0], name)


@contextmanager
def tee_output(log_path: Path):
    """Copies everything printed during the block into log_path."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Tee(old_out, fh), _Tee(old_err, fh)
        try:
            yield
        finally:
            sys.stdout, sys.stderr = old_out, old_err


class Timer:
    def __init__(self):
        self.timings: dict[str, float] = {}

    @contextmanager
    def step(self, name: str):
        start = time.time()
        try:
            yield
        finally:
            self.timings[name] = round(time.time() - start, 2)
