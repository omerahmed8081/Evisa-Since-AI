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

**2. Frontend** (Node.js 22.12+, npm 11+ or Bun): see [frontend/README.md](frontend/README.md).
```bash
cd frontend
npm install
cp .env.example .env.local             # Windows: copy .env.example .env.local
```

**3. Run both with one command** (from the repository root, after steps 1 and 2 once):
```bash
npm run dev
```
This starts the API on http://localhost:8000 and, as soon as it answers, the web app on http://localhost:8080.
Output of both appears in one terminal, prefixed `[api]` and `[web]`. **Ctrl+C stops both**; if one crashes,
the other is stopped too.

| Command | What it starts |
|---|---|
| `npm run dev` | API + web app |
| `npm run dev:backend` | only the API |
| `npm run dev:frontend` | only the web app |
| `npm run test:frontend` | frontend tests |

The launcher ([scripts/dev.mjs](scripts/dev.mjs), no extra packages) picks the Python in this order: the `PYTHON`
environment variable, `backend/.venv`, then `python`/`python3` on your PATH (e.g. an activated conda environment).
For the frontend it uses npm 11+, or Bun if npm is older. Examples:
```bash
PYTHON=~/miniconda3/bin/python npm run dev     # a specific Python
WEB_PM=bun npm run dev                         # force Bun for the frontend
API_PORT=8001 npm run dev                      # API on another port (the web app is pointed at it,
                                               # unless another address is saved in its ⚙ Settings)
```

## Working together

- Clone once, then work on a branch: `git checkout -b my-feature`, push, open a pull request.
- Keep the structure: backend code in `backend/`, frontend code in `frontend/`.
- Never commit `.env` files or credentials (they are in `.gitignore`).
- `backend/cache/` **is** committed: it holds the Gemini answers, so anyone can rebuild the graph without
  using API quota.
