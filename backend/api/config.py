"""API settings, read from backend/.env.

Imported first by api/__init__.py so .env is loaded and backend/ is on sys.path before anything
else (the capture code is imported as the `pipeline` package)."""
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

CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
CORS_ORIGIN_REGEX = os.environ.get("CORS_ORIGIN_REGEX", r"https://.*\.(lovable\.app|lovableproject\.com|lovable\.dev)")

MAX_CARDS = int(os.environ.get("API_MAX_CARDS", "6"))
MAX_OUTDATED_CARDS = int(os.environ.get("API_MAX_OUTDATED_CARDS", "2"))
HISTORY_TURNS = int(os.environ.get("API_HISTORY_TURNS", "6"))

CHAT_MODEL = os.environ.get("API_GEMINI_MODEL", "").strip()

THINKING_BUDGET = os.environ.get("API_THINKING_BUDGET", "0")
GEMINI_RETRIES = int(os.environ.get("API_GEMINI_RETRIES", "8"))
GEMINI_MAX_WAIT = float(os.environ.get("API_GEMINI_MAX_WAIT", "30"))
CACHE_ANSWERS = os.environ.get("API_CACHE_ANSWERS", "true").lower() == "true"

APP_NAME = os.environ.get("APP_NAME", "Evisa").strip() or "Evisa"
DEMO_USER_NAME = os.environ.get("DEMO_USER_NAME", "").strip()
DEMO_USER_ROLE = os.environ.get("DEMO_USER_ROLE", "").strip()

FEEDBACK_WORKED_DELTA = 0.1
FEEDBACK_FAILED_DELTA = -0.2
FEEDBACK_DISPUTE_AFTER = int(os.environ.get("FEEDBACK_DISPUTE_AFTER", "2"))
MIN_COMMENT_CHARS = 8

TIMEZONE = "Europe/Helsinki"
