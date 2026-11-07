# API (FastAPI)

Backend for the chatbot. It implements the chat flow (understand → retrieve → answer) and the feedback loop.
The capture/retrieval pipeline is imported from the `pipeline` package (`backend/pipeline`).

```
POST /api/chat
  Step A · UNDERSTAND  understand.py  Gemini, structured output: message -> devices, symptom/event terms
                                      (same vocabulary as the stored tips; IDs in the text are always found by regex)
  Step B · RETRIEVE    knowledge.py   Neo4j only: retrieve.find_knowledge() per device, or a symptom search
                                      when no device is named -> KnowledgeCards
  Step C · ANSWER      answer.py      Gemini, streamed, answers ONLY from the cards
                                      (template answer from the cards if Gemini is unavailable)
POST /api/feedback     feedback.py    worked +0.1 / failed -0.2 confidence, 'disputed' after repeated failures,
                                      comment -> ingest.process() as a new 'feedback' conversation
```

## Run

From the **`backend/` folder** (not from inside `api/`):

```bash
pip install -r requirements.txt
python scripts/load_inventory.py          # once
python scripts/ingest.py data/threads     # once (uses cache/, so almost no Gemini calls)
uvicorn api.main:app --reload --port 8000
```

Open http://localhost:8000/docs to try every endpoint.

Quick checks:
```bash
curl localhost:8000/api/health?deep=true
curl -N -X POST localhost:8000/api/chat -H 'content-type: application/json' \
     -d '{"message": "TRN-031: SFP replaced, link up but no traffic. What should I do?"}'
curl -X POST 'localhost:8000/api/chat?stream=false' -H 'content-type: application/json' \
     -d '{"message": "How do I get to the TRN-042 site near Kolari?"}'
```

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/chat` | SSE: `meta`, `token`…, `cards`, `done` (or `error`). `?stream=false` returns JSON |
| GET | `/api/nodes` | Device list for the selector |
| GET | `/api/nodes/{node_id}` | Device facts, all knowledge that applies, event timeline |
| GET | `/api/stats` | Counters for the header |
| POST | `/api/feedback` | `{message_id, assertion_id, verdict: worked\|failed\|skipped, comment}` |
| GET | `/api/health` | `?deep=true` also checks Neo4j and the Gemini key |

Additions to the UI contract (all optional for the frontend):
- every card has `knowledge_ids` (all merged assertions), `confidence`, `symptom_match`, `how_it_applies`,
  and `link` = how the tip reaches the device: `{how: id|alias|location|site|scope, via, site, candidates}`;
- `meta` also has `unknown_nodes`, `symptoms`, `events`, `retrieval` (`device`/`search`/`none`), `understood_by`,
  `resolved_by` (`id`/`alias`/`location`/`site`/`selected`/`gemini`) and `resolution_note`
  ("the Kolari box" -> TRN-042; "the Kittilä site" -> its 3 devices);
- a source `channel` can also be `feedback` (knowledge that came from a feedback comment);
- verdict `skipped` is accepted (Full_pipeline.txt ⏭ button).

## Card rules

- `status`: `disputed` (conflict or repeated 👎) > `outdated` (superseded, or not needed on this firmware)
  > `confirmed` (outcome worked) > `unconfirmed`.
- Failed attempts are attached to the fix they relate to (`related_failed`) when their action is on the fix's
  avoid-list or they share symptoms; otherwise they are shown as their own compact card.
- Conflicting tips are nested in `conflicts_with` ("Experts disagree").
- Knowledge hidden by the firmware rule is shown with a `scope_note` ("Not needed on TRN-077: …").
- Troubleshooting questions don't show site-access cards; access questions show only access cards.

## Settings (.env, all optional)

| Variable | Default | |
|---|---|---|
| `CORS_ORIGINS` | `*` | comma separated; Lovable domains are also allowed by `CORS_ORIGIN_REGEX` |
| `API_MAX_CARDS` | 6 | cards per chat answer |
| `API_GEMINI_MODEL` | (empty) | model for chat answers; empty = `GEMINI_MODEL`. Use a non-lite Flash model for better answers |
| `API_THINKING_BUDGET` | 0 | Gemini thinking off for fast replies; empty = model default. Retried without it automatically if the model rejects it |
| `API_GEMINI_RETRIES` | 8 | Gemini rate limit (429) / overload (503): retry this many times before the template fallback |
| `API_GEMINI_MAX_WAIT` | 30 | max seconds between retries (Gemini's own `retryDelay` is used when it gives one) |
| `API_CACHE_ANSWERS` | true | repeated question + same knowledge = no Gemini call (`cache/api_answer`) |
| `FEEDBACK_DISPUTE_AFTER` | 2 | failed reports (and more failed than worked) before a tip becomes disputed |

## Good to know

- Chats are kept in memory: restarting the API forgets conversations, not knowledge.
- Feedback changes `confidence` on the Assertion nodes. Re-running `scripts/ingest.py --force` resets confidence;
  the `(:Feedback)` nodes stay.
- Step A and Step C answers are cached in `cache/api_understand` and `cache/api_answer`. Delete those folders
  to get fresh Gemini answers (e.g. after changing the prompts in `api/answer.py`).
- Lovable's hosted preview can't reach `localhost`. Use mock mode there, or expose the API with a tunnel
  (`cloudflared tunnel --url http://localhost:8000` or `ngrok http 8000`) and set `VITE_API_BASE_URL`.
