"""FastAPI backend for the Network Knowledge Assistant. Run from the backend/ folder:

    uvicorn api.main:app --reload --port 8000
"""
from . import config  # noqa: F401  (loads .env and puts backend/ on sys.path)
