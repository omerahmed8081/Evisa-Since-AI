"""
pipeline: capture human operational knowledge from conversations into a time-aware Neo4j
knowledge graph, keep it up to date, and retrieve what applies to a device.

Used by the FastAPI layer (backend/api) and the command-line scripts (backend/scripts).
"""
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"

load_dotenv(BACKEND_DIR / ".env")
