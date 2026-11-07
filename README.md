# EVISA: silent knowledge → machine-readable context (Elisa × Since AI 2026)

Captures troubleshooting knowledge from Teams chats, emails and call notes, links it to network devices in a
time-aware Neo4j knowledge graph (`valid_from` / `valid_to`) and serves it to field engineers through a chat UI,
with sources, confidence and feedback.

```
backend/    Python: capture pipeline, Neo4j graph, FastAPI service
frontend/   Web app (chat UI)
scripts/    dev.mjs: starts backend + frontend together
```

## Requirements

- Python 3.10+
- Node.js 22.12+ with npm 11+ (or Bun)
- A Neo4j database: AuraDB Free or local Docker (`docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:5`)
- A Gemini API key (https://aistudio.google.com)

**The backend needs a Neo4j connection and a Gemini API key in `backend/.env` to run** (scripts and server).

## Setup

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate                 # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                 # Mac/Linux: cp .env.example .env

# frontend
cd ../frontend
npm install
copy .env.example .env.local           # Mac/Linux: cp .env.example .env.local
```

`backend/.env`:

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | yes | |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | yes | AuraDB: `neo4j+s://xxxx.databases.neo4j.io`, Docker: `bolt://localhost:7687` |
| `GEMINI_MODEL` | | model used for capture (default in `.env.example`) |
| `API_GEMINI_MODEL` | | model used for chat answers (defaults to `GEMINI_MODEL`) |
| `APP_NAME`, `DEMO_USER_NAME`, `DEMO_USER_ROLE` | | source label and user for feedback notes until login exists |

`frontend/.env.local`: `VITE_API_BASE_URL=http://localhost:8000` and `VITE_USE_MOCK=false` (without a base URL
the UI runs on mock data).

## Data

The data part is done and stored in the repository:

- `backend/data/`: synthetic dataset (inventory, events, 36 conversations, answer key)
- `backend/cache/`: Gemini results for every conversation (extractions, relation decisions, embeddings)
- `backend/models/prefilter.joblib`: trained pre-filter

The knowledge graph itself lives in Neo4j. To build it on a new database, or to start clean (e.g. after testing
feedback), reset everything and rebuild from the stored data. Thanks to the cache this makes almost no Gemini
calls, but the key is still required.

```bash
cd backend
python scripts/reset_graph.py                       # delete everything in Neo4j
python scripts/load_inventory.py                    # devices, sites, nicknames, events
python scripts/ingest.py data/threads --prefilter   # capture all conversations
python tests/evaluate.py                            # check the result against the answer key
```

Regenerating the data is only needed if you change it:

```bash
python data/generator/build.py          # dataset from data/generator/scenarios.py
python data/generator/noise.py          # noise conversations for the pre-filter
python data/validate.py                 # dataset checks
python scripts/train_prefilter.py       # retrain the pre-filter
```

## Run

From the repository root:

```bash
npm run dev
```

Starts the API on http://localhost:8000 (docs at `/docs`) and the web app on http://localhost:8080. Ctrl+C stops
both. `npm run dev:backend` / `npm run dev:frontend` start one side only. The launcher uses `PYTHON`,
`backend/.venv` or `python` on the PATH; `API_PORT=8001 npm run dev` changes the API port.

Separately:

```bash
cd backend && uvicorn api.main:app --reload --port 8000
cd frontend && npm run dev
```

## Tests

```bash
cd backend
python -m pytest tests -q               # unit tests (no Neo4j / Gemini)
python tests/evaluate.py --details      # graph vs. answer key
python tests/evaluate_prefilter.py      # pre-filter, cross-validated
python tests/chat_questions.py          # demo questions against the running API
npm run test:frontend                   # from the repository root
```

## Notes

- Never commit `.env` / `.env.local` or credentials. `backend/cache/` is committed on purpose.
- More detail: [backend/README.md](backend/README.md), [backend/api/README.md](backend/api/README.md),
  [frontend/README.md](frontend/README.md).
- All data, devices and names are synthetic.
