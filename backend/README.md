# Backend

Capture pipeline (conversations → knowledge graph), Neo4j graph and FastAPI service. Run all commands from
this folder. Requires `.env` with a Gemini API key and Neo4j credentials (see `.env.example`).

```
data/       synthetic dataset: inventory, nicknames, events, conversations, answer key, generator
pipeline/   capture (extract → link → store → reconcile), retrieval, pre-filter
api/        FastAPI: chat (understand → retrieve → answer), devices, feedback
scripts/    build the graph, train the pre-filter, query a device
tests/      unit tests and evaluations
cache/      stored Gemini results (committed)
models/     trained pre-filter
docs/       queries.cypher for Neo4j Browser
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # Mac/Linux: cp .env.example .env, then fill in the keys
```

## Data / graph

The dataset, the Gemini cache and the pre-filter model are already in the repository. The graph is in Neo4j;
to (re)build it from scratch:

```bash
python scripts/reset_graph.py
python scripts/load_inventory.py
python scripts/ingest.py data/threads --prefilter
python tests/evaluate.py --details
```

`ingest.py` flags: `--dry-run` (print extractions, no Neo4j), `--force` (re-process captured conversations),
`--refresh` (ignore the cache), `--prefilter` (skip noise locally before Gemini). A stopped run can simply be
restarted; captured conversations are skipped.

## Server

```bash
uvicorn api.main:app --reload --port 8000
```

Docs at http://localhost:8000/docs. Endpoints: `POST /api/chat`, `GET /api/nodes`, `GET /api/nodes/{id}`,
`POST /api/feedback`, `GET /api/stats`, `GET /api/health`. Contract and settings: [api/README.md](api/README.md).

## Tools and tests

```bash
python scripts/retrieve.py TRN-077 [--symptoms ...] [--json]   # what applies to a device
python scripts/train_prefilter.py                              # retrain the pre-filter
python -m pytest tests -q                                      # unit tests
python tests/evaluate_prefilter.py                             # pre-filter evaluation
python tests/chat_questions.py                                 # demo questions (API must be running)
```

## Design notes

- Gemini reads language (conversations, questions, answers); device facts, scope, validity and which knowledge
  applies are decided in code and Cypher.
- Assertions have `valid_from` / `valid_to`. New knowledge reinforces, narrows (e.g. firmware < 3.4),
  supersedes (sets `valid_to`) or conflicts with older knowledge (`pipeline/reconcile.py`). Nothing is deleted.
- Devices are linked by ID, nickname (`data/inventory/aliases.csv`) or place; an ambiguous place links to the
  `Site`. Each link stores how it was made and its confidence (1.0 / 0.9 / 0.8 / 0.5).
- Failed attempts are stored as warnings. Duplicates are merged at retrieval; confidence grows with sources.
- Feedback adjusts confidence (one vote per user, answer and card); a note is ingested as a new conversation
  from the logged-in user and can supersede old knowledge.
- The pre-filter (rule score + TF-IDF/logistic regression trained on cached Gemini decisions) skips 97% of the
  noise in the test set with no useful conversation lost.
- Symptom/action/event terms form a growing vocabulary; new terms are merged with embeddings.

## Evaluation (synthetic data, 36 conversations)

Useful/noise 100% · devices 100% · scope 90% · outcome 100% · actions 100% · symptoms 97% · 9/9 knowledge
updates · 21/21 retrieval and linking checks.

## Limitations

Synthetic, mostly-useful data; install date stands in for hardware generation; production would add channel
opt-in, a self-hosted model for privacy, real login and expert review.
