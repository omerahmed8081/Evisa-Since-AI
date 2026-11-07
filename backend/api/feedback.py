"""
Feedback loop (Full_pipeline.txt, last box):

  ✅ worked  -> confidence +0.1 (max 0.95)
  ❌ failed  -> confidence -0.2 (min 0.05); after repeated failures (more failed than worked,
               at least FEEDBACK_DISPUTE_AFTER) the tip is marked 'disputed'
  who        -> the logged-in user (name + role from the frontend, or X-User-Name / X-User-Role headers;
               DEMO_USER_NAME / DEMO_USER_ROLE in .env until login exists). Notes are captured as written
               by that person in the app (channel = APP_NAME, e.g. "Evisa"); their role sets the starting
               confidence, and a first-hand report that a fact changed supersedes the old tip.
  ⏭ skipped -> nothing is counted (an earlier vote on the same card is undone)
  comment    -> runs through Flow 1 (ingest.process) as a new conversation, so "it was the patch
               cable" becomes new knowledge, linked and reconciled like any chat. That is also how
               valid_to gets set: "the code changed to 7731" supersedes the old tip.

One vote per engineer, answer and card: the note arriving after the click does not count again, and
changing the verdict undoes the earlier one.

Graph:  (:Feedback {verdict, comment, message_id, created_at})-[:ABOUT]->(:Assertion)
        (Feedback)-[:ON]->(:Device)                  the device(s) the question was about
        (Feedback)-[:BY]->(:Person {name, role})     who voted / wrote the note
        (Feedback)-[:CAPTURED_AS]->(:Source {channel: APP_NAME})<-[:FROM]-(:Assertion)  the note's new tips
"""
import logging
import threading
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pipeline import graph
from api.config import (APP_NAME, FEEDBACK_DISPUTE_AFTER, FEEDBACK_FAILED_DELTA, FEEDBACK_WORKED_DELTA,
                        TIMEZONE)

log = logging.getLogger("api.feedback")
_ingest_lock = threading.Lock()  # one comment at a time through the pipeline

# One engineer, one answer, one card = ONE vote. The UI sends the verdict on click and the same verdict
# again with the optional note; that second request only attaches the note. Changing the verdict
# (worked -> didn't work) undoes the first vote; "skip" undoes it and counts nothing.
SAME_VOTE_WINDOW_MIN = 30   # without a message id (device panel), same card + verdict within 30 min = same vote

PREVIOUS_QUERY = """
MATCH (f:Feedback)-[:ABOUT]->(a:Assertion {id: $aid})
WHERE f.replaced IS NULL
  AND ( ($mid IS NOT NULL AND f.message_id = $mid)
        OR ($mid IS NULL AND f.message_id IS NULL
            AND f.created_at > datetime() - duration({minutes: $window})) )
RETURN f.id AS id, f.verdict AS verdict
ORDER BY f.created_at DESC LIMIT 1
"""

APPLY_QUERY = """
MATCH (a:Assertion {id: $aid})
WITH a, coalesce(a.confidence, 0.5) + $delta AS c
SET a.confidence = round(CASE WHEN c > 0.95 THEN 0.95 WHEN c < 0.05 THEN 0.05 ELSE c END, 2),
    a.feedback_worked = coalesce(a.feedback_worked, 0) + $worked,
    a.feedback_failed = coalesce(a.feedback_failed, 0) + $failed
WITH a,
     a.feedback_failed >= $dispute_after AND a.feedback_failed > a.feedback_worked AS should_dispute
// remember the status from before feedback disputed it, so it can be restored if votes change
SET a.status_before_feedback = CASE WHEN should_dispute AND a.status <> 'disputed'
                                    THEN a.status ELSE a.status_before_feedback END,
    a.status = CASE WHEN should_dispute THEN 'disputed'
                    WHEN a.status = 'disputed' AND a.status_before_feedback IS NOT NULL
                    THEN a.status_before_feedback ELSE a.status END
WITH a, should_dispute
SET a.status_before_feedback = CASE WHEN should_dispute THEN a.status_before_feedback ELSE null END
RETURN a.id AS id, a.confidence AS confidence, a.status AS status,
       a.feedback_worked AS worked, a.feedback_failed AS failed
"""

CREATE_QUERY = """
MATCH (a:Assertion {id: $aid})
CREATE (f:Feedback {id: $fid, verdict: $verdict, comment: $comment, message_id: $mid, created_at: datetime()})
CREATE (f)-[:ABOUT]->(a)
MERGE (p:Person {name: $user_name})
SET p.role = coalesce($user_role, p.role)
CREATE (f)-[:BY]->(p)
WITH f
UNWIND $devices AS dev
MATCH (d:Device {node_id: dev})
MERGE (f)-[:ON]->(d)
"""

STATE_QUERY = """
MATCH (a:Assertion {id: $aid})
RETURN a.id AS id, a.confidence AS confidence, a.status AS status,
       coalesce(a.feedback_worked, 0) AS worked, coalesce(a.feedback_failed, 0) AS failed
"""


def _effect(verdict: str, sign: int) -> dict:
    """Confidence change and counters for a vote (sign -1 = undo it)."""
    if verdict == "worked":
        return {"delta": sign * FEEDBACK_WORKED_DELTA, "worked": sign, "failed": 0}
    if verdict == "failed":
        return {"delta": sign * FEEDBACK_FAILED_DELTA, "worked": 0, "failed": sign}
    return {"delta": 0.0, "worked": 0, "failed": 0}


def _apply(aid: str, verdict: str, sign: int) -> dict | None:
    rows = graph.run(APPLY_QUERY, aid=aid, dispute_after=FEEDBACK_DISPUTE_AFTER, **_effect(verdict, sign))
    return dict(rows[0]) if rows else None


def record(ids: list[str], verdict: str, comment: str | None, message_id: str | None,
           devices: list[str] | None = None, user: dict | None = None) -> tuple[list[dict], list[str]]:
    """Apply one vote to every assertion of a card. Returns (new state per assertion, Feedback ids that
    hold the note, used to link the note to what it became in the graph)."""
    updated, note_ids = [], []
    for aid in ids:
        if not graph.run("MATCH (a:Assertion {id: $aid}) RETURN a.id", aid=aid):
            continue
        prev = graph.run(PREVIOUS_QUERY, aid=aid, mid=message_id, window=SAME_VOTE_WINDOW_MIN)
        prev = dict(prev[0]) if prev else None

        if prev and prev["verdict"] == verdict:
            # Same vote again (the note arriving): attach the note, don't count twice
            if comment:
                graph.run("MATCH (f:Feedback {id: $id}) SET f.comment = $c", id=prev["id"], c=comment)
                note_ids.append(prev["id"])
            state = graph.run(STATE_QUERY, aid=aid)
            updated.append(dict(state[0]))
            continue

        if prev:  # changed their mind: undo the earlier vote
            graph.run("MATCH (f:Feedback {id: $id}) SET f.replaced = true", id=prev["id"])
            _apply(aid, prev["verdict"], -1)

        if verdict == "skipped" and not comment:
            state = graph.run(STATE_QUERY, aid=aid)   # skip: nothing is counted or stored
            updated.append(dict(state[0]))
            continue

        fid = f"FB-{uuid.uuid4().hex[:10]}-{aid}"
        graph.run(CREATE_QUERY, aid=aid, fid=fid, verdict=verdict, comment=comment, mid=message_id,
                  devices=list(devices or []), user_name=(user or {}).get("name") or "Field Engineer",
                  user_role=(user or {}).get("role"))
        if comment:
            note_ids.append(fid)
        updated.append(_apply(aid, verdict, +1))
    return [u for u in updated if u], note_ids


def _now() -> str:
    """Current time in the team's time zone. Windows has no built-in time zone database (needs the
    'tzdata' package); fall back to the computer's local time instead of failing."""
    try:
        return datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds")
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().isoformat(timespec="seconds")


def _devices_of(ids: list[str]) -> list[str]:
    rows = graph.run("MATCH (a:Assertion)-[:OBSERVED_ON]->(d:Device) WHERE a.id IN $ids "
                     "RETURN collect(DISTINCT d.node_id) AS ids", ids=ids)
    return list(rows[0]["ids"]) if rows else []


def ingest_comment(comment: str, verdict: str, ids: list[str], message: dict | None, summary: str | None,
                   feedback_ids: list[str] | None = None, user: dict | None = None):
    """Background task: the engineer's comment becomes a new 'feedback' conversation in the graph."""
    from pipeline import ingest
    from pipeline.vocabulary import Vocabulary

    try:
        nodes = (message or {}).get("node_ids") or _devices_of(ids)
        devices = ', '.join(nodes) or 'an unnamed device'
        verdict_text = {"worked": "The suggested tip worked.", "failed": "The suggested tip did NOT work.",
                        "skipped": "I did not try the suggested tip."}[verdict]
        now = _now()
        who = (user or {}).get("name") or "Field Engineer"
        role = (user or {}).get("role") or "Field Engineer"
        # Two messages: what the assistant showed (context, already in the graph) and the engineer's
        # report. Only the report is new; keeping them apart stops the old tip from being captured again
        # ("new code is 3000" must not come back as the old code 9035).
        thread = {
            "thread_id": f"FB-{uuid.uuid4().hex[:8].upper()}",
            "channel": APP_NAME,
            "language": None,
            "subject": f"Report in {APP_NAME} on {devices}",
            "participants": ["Knowledge Assistant", who],
            "reported_by": {"name": who, "role": role, "app": APP_NAME, "date": now[:10]},
            "messages": [
                {"seq": 1, "timestamp": now, "author": "Knowledge Assistant", "role": "Chatbot (context only)",
                 "text": (f"CONTEXT ONLY, already in the knowledge base, do not capture this again. "
                          f"Question about {devices}: {(message or {}).get('question') or '-'} "
                          f"Tip the assistant suggested: {summary or '-'}")},
                {"seq": 2, "timestamp": now, "author": who, "role": role,
                 "text": f"On {devices}: {verdict_text} {comment}"},
            ],
        }
        with _ingest_lock:
            vocab = Vocabulary(use_graph=True).load()
            ingest.process(thread, dry_run=False, vocab=vocab)
        graph.run("MERGE (p:Person {name: $n}) SET p.role = $r", n=who, r=role)
        # Trace: the click/note -> the conversation it was captured as -> the tips that came out of it
        graph.run("UNWIND $fids AS fid MATCH (f:Feedback {id: fid}) MATCH (s:Source {id: $sid}) "
                  "MERGE (f)-[:CAPTURED_AS]->(s)", fids=list(feedback_ids or []), sid=thread["thread_id"])
        log.info("Feedback comment ingested as %s", thread["thread_id"])
    except Exception:
        log.exception("Could not ingest feedback comment")
