"""Capture pipeline: conversations -> time-aware Neo4j knowledge graph, plus retrieval.
Used by the API (backend/api) and the command-line scripts (backend/scripts)."""
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"

load_dotenv(BACKEND_DIR / ".env")
