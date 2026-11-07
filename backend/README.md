# Backend

Python backend: the **capture pipeline** (conversations → knowledge graph), the **Neo4j graph**, and the
**FastAPI** service the frontend talks to. Run every command from this `backend/` folder.

```
1. DATA        data/            inventory, event stream, 33 conversations, answer key, generator
2. CAPTURE     pipeline/        conversation → Gemini (filter + extract) → link to devices → Neo4j,
                                then update older knowledge (reinforce / narrow / supersede / conflict)
3. RETRIEVE    pipeline/retrieve.py   what applies to a device (graph rules, no LLM)
4. API         api/             FastAPI: chat (understand → retrieve → answer), devices, feedback
5. EVALUATE    scripts/evaluate.py    accuracy against the answer key + demo checks
```

## Folder layout

| Path | What it is |
|---|---|
| `api/` | **FastAPI web layer.** Chat with streaming answers and knowledge cards, device endpoints, feedback loop. See [api/README.md](api/README.md) for the full endpoint contract |
| `pipeline/` | **Capture and retrieval** (Python package `pipeline`) |
| `pipeline/ingest.py` | Capture: Gemini extraction, device linking, scope rules ("older units", firmware limits) |
| `pipeline/reconcile.py` | Updates older knowledge when new knowledge arrives |
| `pipeline/retrieve.py` | What applies to a device: scope + validity + firmware filter, duplicates merged |
| `pipeline/graph.py` | All Neo4j queries used by the pipeline |
| `pipeline/prompts.py`, `schema.py` | Gemini prompts and output schemas for capture |
| `pipeline/vocabulary.py` | Growing vocabulary of symptoms/actions/events; near-duplicates merged |
| `pipeline/extract.py`, `cache.py` | Gemini calls + disk cache |
| `pipeline/threads.py` | Reads Teams/call JSON and email files |
| `scripts/` | Command-line tools (below) |
| `data/` | Synthetic dataset: `inventory/nodes.csv`, `events/events.json`, `threads/`, `ground_truth.json`, `generator/`, `DATA.md` |
| `cache/` | Saved Gemini answers. Committed on purpose: rebuilding the graph costs no API quota |
| `docs/queries.cypher` | Useful queries for Neo4j Browser |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # Mac/Linux: cp .env.example .env
```
Fill in `.env`: `GEMINI_API_KEY`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.
- **Gemini key:** https://aistudio.google.com → Get API key.
- **Neo4j:** AuraDB Free (https://neo4j.com/cloud/aura-free, URI `neo4j+s://xxxx.databases.neo4j.io`) or
  Docker: `docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:5`
  (URI `bolt://localhost:7687`).

## Build the knowledge graph

```bash
python scripts/reset_graph.py           # empty the database (asks for confirmation)
python scripts/load_inventory.py        # devices + event stream
python scripts/ingest.py data/threads   # capture all conversations (cached: ~0 Gemini calls)
python scripts/evaluate.py --details    # accuracy against the answer key + 15 demo checks
```

`ingest.py` options: `--dry-run` (print Gemini output, no Neo4j), `--force` (re-process everything),
`--refresh` (ignore the cache, costs API calls). If a run stops (rate limit), run it again: finished
conversations are skipped.

## Run the API

```bash
uvicorn api.main:app --reload --port 8000
```
Open http://localhost:8000/docs. Main endpoints: `POST /api/chat` (streamed answer + knowledge cards),
`GET /api/nodes`, `GET /api/nodes/{id}`, `POST /api/feedback`, `GET /api/stats`, `GET /api/health`.
Full contract: [api/README.md](api/README.md).

## Inspect without the API

```bash
python scripts/retrieve.py TRN-077                                   # what applies to a device
python scripts/retrieve.py TRN-042 --symptoms TRAFFIC_COUNTERS_ZERO  # ranked by symptom match
python scripts/retrieve.py TRN-077 --json                            # machine-readable
```

## How it works (key design decisions)

- **Gemini handles language, code handles facts.** Gemini reads conversations and questions; device IDs,
  install dates, firmware, timestamps and which knowledge applies are decided by code and the graph.
- **The graph decides what is true.** Retrieval uses a fixed Cypher query, never a generated one: knowledge
  observed on the device, or whose scope rule covers it (same device type; "older units" = installed before
  2020), still valid (`valid_to` empty), and allowed by firmware limits.
- **Knowledge changes over time.** "Fixed in firmware 3.4" narrows older tips to firmware < 3.4 (still valid
  for older devices); "the gate code changed" ends the old code (`valid_to`); contradicting experts → both
  `disputed`. Repeats are merged into one result with all sources; confidence grows with confirmations.
- **Failed attempts are knowledge too.** "Rebooting didn't help on TRN-015" warns the next engineer.
- **Feedback closes the loop.** 👍 +0.1, 👎 −0.2, disputed after repeated failures; an engineer's comment is
  captured as new knowledge through the same pipeline.
- **Growing vocabulary.** Symptoms/actions are mapped to shared terms in any language; new terms are added
  automatically and near-duplicates are merged with embeddings.

## Evaluation (synthetic dataset, 33 conversations)

Useful/noise decision 100% · devices linked 100% · scope 90% · outcome 100% · actions 100% · symptoms 97% ·
9/9 expected knowledge updates · 15/15 demo retrieval checks (`python scripts/evaluate.py --details`).

## Limitations and path to production

Synthetic data (88% useful vs. mostly noise in reality) → cheap pre-filters (channels, device/keyword rules,
event correlation, a small local classifier) before any LLM call; install date stands in for a real
hardware-generation field; real linking needs sites and aliases; privacy → self-hosted open model, opt-in
channels, expert confirmation before storing, and storing the tip plus a link instead of the raw conversation.
