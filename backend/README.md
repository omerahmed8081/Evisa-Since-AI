# Backend

Python backend: the **capture pipeline** (conversations → knowledge graph), the **Neo4j graph**, and the
**FastAPI** service the frontend talks to. Run every command from this `backend/` folder.

```
1. DATA        data/            inventory (+ device nicknames), event stream, 36 conversations, answer key, generator
2. CAPTURE     pipeline/        conversation → Gemini (filter + extract) → link to devices → Neo4j,
                                then update older knowledge (reinforce / narrow / supersede / conflict)
3. RETRIEVE    pipeline/retrieve.py   what applies to a device (graph rules, no LLM)
4. API         api/             FastAPI: chat (understand → retrieve → answer), devices, feedback
5. EVALUATE    tests/evaluate.py      accuracy against the answer key + demo checks
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
| `pipeline/linking.py` | Finds devices in messy text: IDs ("trn042"), nicknames (`data/inventory/aliases.csv`), places ("Kolarissa") |
| `pipeline/extract.py`, `cache.py` | Gemini calls + disk cache |
| `pipeline/threads.py` | Reads Teams/call JSON and email files |
| `pipeline/prefilter.py`, `prefilter_data.py` | Local pre-filter (rule score + small classifier) that skips noise before Gemini |
| `models/prefilter.joblib` | The trained pre-filter classifier (166 KB, rebuild with `scripts/train_prefilter.py`) |
| `scripts/` | Command-line tools: build the graph, train the pre-filter, query (below) |
| `tests/` | Evaluation: `evaluate.py` (capture + retrieval vs. the answer key), `evaluate_prefilter.py` (pre-filter recall / noise skipped), `chat_questions.py` (4 demo questions against the running API) |
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
python tests/evaluate.py --details    # accuracy against the answer key + 21 demo checks
```

`ingest.py` options: `--dry-run` (print Gemini output, no Neo4j), `--force` (re-process everything),
`--refresh` (ignore the cache, costs API calls), `--prefilter` (skip obvious noise locally first). If a run
stops (rate limit), run it again: finished conversations are skipped.

## Local pre-filter (skip noise before any LLM call)

Real chat is mostly noise (lunch, meetings, "thanks!"). Sending all of it to Gemini costs money and sends
everything to a cloud API. The pre-filter runs **locally, in milliseconds, with no API**:

1. **Rule score** (transparent): device ID from the inventory +2, technical terms +1 each (max 3),
   resolution / failure phrase +2, access info +2, advice +1, question answered by an expert +1,
   an alarm/work order on a mentioned device within 48 h +3. Below 3 → skipped.
2. **Small classifier**: TF-IDF over 2-4 character snippets (handles Finnish endings and typos) + logistic
   regression. Trained on **Gemini's own past decisions** from the cache (distillation: the cheap model learns
   to imitate the expensive one) plus template noise. It only skips what it is very sure is noise.

Tuned for recall: losing real knowledge is permanent, a noise message let through only costs one Gemini call.
Skipped conversations are still saved as `Source` nodes with `prefiltered = true` so they can be audited.

```bash
python data/generator/noise.py          # 60 extra noise conversations -> data/noise_threads (already included)
python scripts/train_prefilter.py       # trains in seconds -> models/prefilter.joblib
python tests/evaluate_prefilter.py    # honest cross-validated test (--show lists every decision)
python scripts/ingest.py data/threads --prefilter
```

Result (93 conversations: 29 useful, 64 noise; classifier scored only on conversations it never trained on):
rules skip 41/64 noise, classifier skips on average 20.8 of the remaining 23 → **62/64 noise never sent to
Gemini (97%), 0/29 useful lost** even in the worst split. Small, partly template-generated dataset, so this
shows the mechanism; on real Elisa data it is retrained on their own labels (Gemini decisions + expert feedback).

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
- **Messy chats still get linked.** Devices are found by ID (also "trn042", "TRN 042"), by nickname
  (`aliases.csv`: "Ounasvaara hop" = MW-412) or by place ("Kolarin siirtolaite" = the only transmission node
  in Kolari). If a place has several possible devices, the tip is linked to the `Site` instead of guessing,
  and reaches every device there as "reported at the site, not confirmed for this device". Every link
  stores how it was made and how sure it is (ID 1.0, nickname 0.9, place 0.8, site 0.5); retrieval lowers
  a tip's confidence accordingly. The chat resolves "the Kolari box" the same way, in code.
- **Failed attempts are knowledge too.** "Rebooting didn't help on TRN-015" warns the next engineer.
- **Feedback closes the loop.** 👍 +0.1, 👎 −0.2, disputed after repeated failures; an engineer's comment is
  captured as new knowledge through the same pipeline.
- **Growing vocabulary.** Symptoms/actions are mapped to shared terms in any language; new terms are added
  automatically and near-duplicates are merged with embeddings.

## Evaluation (synthetic dataset, 36 conversations)

Useful/noise decision 100% · devices linked 100% · scope 90% · outcome 100% · actions 100% · symptoms 97% ·
9/9 expected knowledge updates · 15 demo retrieval checks + 6 linking checks (place, site, nickname) (`python tests/evaluate.py --details`).

## Limitations and path to production

Synthetic data (88% useful vs. mostly noise in reality) → the local pre-filter above (plus channel opt-in)
runs before any LLM call; install date stands in for a real
hardware-generation field; real linking needs sites and aliases; privacy → self-hosted open model, opt-in
channels, expert confirmation before storing, and storing the tip plus a link instead of the raw conversation.
