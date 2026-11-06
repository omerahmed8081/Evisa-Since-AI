"""
Disk cache for Gemini results (extractions, relation decisions, embeddings).

Why: the Gemini free tier is limited. With the cache, changing OUR rules (scope, merging,
linking) and re-running costs no API calls; only new or changed conversations go to Gemini.

  cache/extract/<hash>.json     one file per conversation (+ prompt version)
  cache/relations/<hash>.json   one file per "how does this new tip relate to older ones" decision
  cache/embed/<hash>.json       one file per embedded vocabulary term

Delete the cache/ folder, or run ingest.py with --refresh, to force fresh Gemini calls.
"""
import hashlib
import json
import os
from pathlib import Path

CACHE_DIR = Path(os.environ.get("CACHE_DIR", "cache"))
ENABLED = True  # ingest.py --refresh sets this to False


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
