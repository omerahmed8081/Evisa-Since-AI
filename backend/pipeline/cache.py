"""Disk cache for Gemini results (extractions, relation decisions, embeddings), keyed by a hash
of the model and the full prompt. Re-running the pipeline only calls Gemini for new input."""
import hashlib
import json
import os
from pathlib import Path

from pipeline import BACKEND_DIR

CACHE_DIR = Path(os.environ.get("CACHE_DIR", BACKEND_DIR / "cache"))
ENABLED = True


def make_key(*parts) -> str:
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def get(namespace: str, key: str):
    if not ENABLED:
        return None
    path = CACHE_DIR / namespace / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def put(namespace: str, key: str, value):
    path = CACHE_DIR / namespace / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
