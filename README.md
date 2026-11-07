# Silent knowledge → machine-readable context (Elisa × Since AI 2026)

Engineers solve network problems with knowledge that lives in chats, emails and calls. This project
captures that knowledge automatically, links it to the right equipment in a **time-aware Neo4j knowledge
graph** (`valid_from` / `valid_to`), keeps it up to date as new messages arrive, and serves it to field
engineers through a chatbot, with sources, confidence and feedback.

```
backend/   Python: capture pipeline + Neo4j graph + FastAPI (chat, devices, feedback)
frontend/  Web app (chat UI) that talks to the backend API
```

## Quick start

**1. Backend** (Python 3.10+, a Neo4j database, a Gemini API key)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                 # Mac/Linux: cp .env.example .env  -> then fill in your keys

python scripts/load_inventory.py       # devices + event stream into Neo4j
python scripts/ingest.py data/threads  # capture all conversations (cached Gemini answers are reused)
uvicorn api.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs. Details: [backend/README.md](backend/README.md).

**2. Frontend**: see [frontend/README.md](frontend/README.md). Point it at the API with
`VITE_API_BASE_URL=http://localhost:8000`.

## Working together

- Clone once, then work on a branch: `git checkout -b my-feature`, push, open a pull request.
- Keep the structure: backend code in `backend/`, frontend code in `frontend/`.
- Never commit `.env` files or credentials (they are in `.gitignore`).
- `backend/cache/` **is** committed: it holds the Gemini answers, so anyone can rebuild the graph without
  using API quota.
