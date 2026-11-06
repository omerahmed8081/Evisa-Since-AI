# Pipeline starter: filter → extract → link → store

Turns Teams chats / emails / call transcripts into knowledge in a Neo4j graph.

```
nodes.csv ──────────────────────────────▶ (:Device) nodes
threads/*.json|txt ─▶ Gemini (filter + extract, fixed schema) ─▶ link to devices ─▶ (:Assertion) nodes
```

**Growing vocabulary:** symptoms, actions and events are stored as `(:Term)` nodes in Neo4j.
`schema.py` only holds a starting list. Gemini reuses existing terms where they fit and creates new ones
where they don't; `vocabulary.py` merges near-duplicates (e.g. `BOUNCE_PORT` → `BOUNCE_INTERFACE`, using
embeddings) and saves genuinely new terms, so every later chat can use them. The *structure* of the output
(which fields exist) stays fixed; the *words* grow.

**Design rule:** Gemini handles *language* (what was said, in any language). Code handles *facts*
(which devices exist, install dates, timestamps). Gemini never invents device IDs or dates.

## Files

| File | What it does |
|---|---|
| `schema.py` | The exact JSON shape Gemini must return + the starting vocabulary |
| `vocabulary.py` | The growing vocabulary: seeds Neo4j, merges near-duplicate terms, adds new ones |
| `prompts.py` | Instructions + 2 examples sent to Gemini (written once, reused for every chat) |
| `threads.py` | Reads Teams/call JSON and email TXT into one format |
| `extract.py` | Calls Gemini with structured output (+ retry for free-tier rate limits) |
| `graph.py` | All Neo4j code: constraints, load inventory, save sources and assertions |
| `load_inventory.py` | Loads `nodes.csv` (and optionally `events.json`) into Neo4j |
| `ingest.py` | Runs the pipeline over thread files |
| `reconcile.py` | Updates older knowledge when new knowledge arrives: reinforce / narrow scope / supersede (valid_to) / conflict |
| `cache.py` | Disk cache of all Gemini answers (`cache/`), so re-runs cost no API calls |
| `retrieve.py` | What applies to a device: scope + validity + firmware filter, duplicates merged (the agent's tool) |
| `reset_graph.py` | Empty the database |
| `queries.cypher` | Queries to inspect the graph in Neo4j Browser |
| `data/` | The dataset: inventory, events, 33 conversations, answer key (`ground_truth.json`), `DATA.md` |

## Setup (≈20 min)

1. **Python packages**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows   (Mac/Linux: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
2. **Gemini key:** https://aistudio.google.com → Get API key. Check which Flash model is current there.
3. **Neo4j**, one of:
   - **AuraDB Free** (easiest): https://neo4j.com/cloud/aura-free → create instance → download the credentials file.
     URI looks like `neo4j+s://xxxx.databases.neo4j.io`.
   - **Docker:** `docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password123 neo4j:5`
     (Browser at http://localhost:7474, URI `bolt://localhost:7687`).
4. Copy `.env.example` to `.env` and fill in the values.

## Run, in this order

```bash
# 0. (Once, if the database still has the sample data) empty it
python reset_graph.py

# 1. Optional: test Gemini alone on a few threads (no Neo4j needed)
python ingest.py data/threads/T001.json --dry-run

# 2. Load the inventory and the event stream into Neo4j
python load_inventory.py        # loads data/inventory/nodes.csv and data/events/events.json

# 3. Run the pipeline over all conversations (oldest first)
python ingest.py data/threads
#    If it stops (rate limit, network), run the same command again:
#    finished threads are skipped, failed ones are retried. --force redoes everything.

# 4. Ask what applies to a device (duplicates are merged here)
python retrieve.py TRN-077
python retrieve.py TRN-042 --symptoms TRAFFIC_COUNTERS_ZERO INTERFACE_UP
python retrieve.py TRN-077 --json        # exactly what the chatbot agent will receive
```

**Duplicates are merged at retrieval time** (`retrieve.py`), not when storing. The graph keeps one
assertion per conversation (full traceability); when results are returned, assertions with the same
kind of knowledge, device type, outcome and set of actions are combined into ONE result listing all
sources and devices. Confidence = highest base confidence + 0.1 per extra independent source (max 0.95).
Failed attempts are never merged with fixes that worked, and access info is never merged.

**Firmware:** knowledge with `scope_firmware_below` ("workaround only needed below 3.4") is hidden for devices
already at or above that version; knowledge with `scope_firmware_at_least` ("fixed from 3.4 on") is hidden for
devices below it. `retrieve.py` lists what it hid and why.

**Names in Neo4j Browser:** devices, assertions and sources get a `name` property, so the graph view
shows `TRN-042`, `T001-1`, etc. (re-run `load_inventory.py` once to add it to existing devices).

The first full run embeds the starting vocabulary (one batch of Gemini embedding calls).
During ingestion the console shows every vocabulary decision:
```
  vocab: BOUNCE_PORT -> BOUNCE_INTERFACE (similarity 0.93)
  vocab: + NEW action term REPLACE_ANTENNA_CONNECTOR, closest: CLEAN_CONNECTOR 0.71
```
Use those scores to tune `VOCAB_MERGE_THRESHOLD` in `.env` (default 0.88).

Optional `.env` setting: `DEFAULT_OLDER_BEFORE=2020-01-01`, the cutoff used when an expert says
"the older units" without naming any device (default 2020-01-01).

**Later messages update earlier knowledge** (`reconcile.py`, runs automatically during ingest):
| New message says | Effect on the older tip |
|---|---|
| the same fix again (T002, E001, E006, C001, T012) | `REINFORCES` link; decided by code, no API call |
| "fixed in firmware 3.4" (E007, T016) | older tip keeps `valid_to = null` but gets `scope_firmware_below = 3.4` |
| "the gate code changed" (T023) | older tip gets `valid_to` = the new message's time, status `superseded` |
| a different diagnosis, unresolved (T017) | both tips get status `disputed` |

Gemini is only asked (one call, cached) when the answer isn't obvious to code.
Queries 8 and 9 in `queries.cypher` show the result.

**Gemini cache:** every Gemini answer is stored in `cache/`. After `reset_graph.py`, running ingest again
costs **no API calls** unless a conversation or the prompt changed. Keep `cache/` in the repository: it lets
teammates and the jury reproduce the graph without an API key. `--refresh` ignores the cache.

## What is NOT done yet (next steps)

- **Chatbot agent** that calls `retrieve.py` and answers the engineer, plus feedback buttons.
- **Point-in-time queries** (`as_of` date) using `valid_from`/`valid_to` and the firmware history in events.
- **Evaluation** against `data/ground_truth.json`.
- **Evaluation:** compare output with `data/ground_truth.json`.
- **Retrieval tools + chatbot agent.**
