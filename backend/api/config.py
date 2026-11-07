"""
Settings for the API. Imported first (from api/__init__.py) so that:
  - .env is loaded before anything reads os.environ,
  - backend/ is on sys.path, so the capture pipeline is importable as the `pipeline` package,
  - pipeline/cache.py writes to backend/cache no matter where uvicorn was started from.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("CACHE_DIR", str(ROOT / "cache"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

THREADS_DIR = ROOT / "data" / "threads"

# Comma separated list of allowed frontend origins, "*" = allow all (fine for the hackathon demo).
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
# Also allow any Lovable preview / deployment domain.
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", r"https://.*\.(lovable\.app|lovableproject\.com|lovable\.dev)")

MAX_CARDS = int(os.environ.get("API_MAX_CARDS", "6"))          # knowledge cards per answer
MAX_OUTDATED_CARDS = int(os.environ.get("API_MAX_OUTDATED_CARDS", "2"))
HISTORY_TURNS = int(os.environ.get("API_HISTORY_TURNS", "6"))   # previous chat turns sent to Gemini

# Gemini model for the chat (Step A + Step C). Empty = same as GEMINI_MODEL (used for capture).
# A stronger model here gives better answers without touching the capture pipeline or its cache.
CHAT_MODEL = os.environ.get("API_GEMINI_MODEL", "").strip()

# Gemini: 0 turns "thinking" off for fast chat replies (supported by the 2.5 Flash models).
# Newer models may reject it: llm.py then retries without it automatically.
# Set to an empty string to leave the model default.
THINKING_BUDGET = os.environ.get("API_THINKING_BUDGET", "0")
# Cache chat answers on disk (cache/api_answer): same question + same knowledge = no API call.
CACHE_ANSWERS = os.environ.get("API_CACHE_ANSWERS", "true").lower() == "true"

# Feedback rules from Full_pipeline.txt
FEEDBACK_WORKED_DELTA = 0.1
FEEDBACK_FAILED_DELTA = -0.2
FEEDBACK_DISPUTE_AFTER = int(os.environ.get("FEEDBACK_DISPUTE_AFTER", "2"))  # failed reports before 'disputed'
MIN_COMMENT_CHARS = 8  # shorter comments are stored but not sent through the ingest pipeline

TIMEZONE = "Europe/Helsinki"
