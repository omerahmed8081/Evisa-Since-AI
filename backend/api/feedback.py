"""Feedback on knowledge cards.

worked / failed adjust the assertion's confidence (+0.1 / -0.2) and repeated failures mark it
disputed; skip counts nothing. One vote per user, answer and card. An optional note is captured as
a new conversation through the normal ingest pipeline (channel = APP_NAME), so it can add, narrow
or supersede knowledge."""
import logging
import threading
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pipeline import graph
from api.config import (APP_NAME, FEEDBACK_DISPUTE_AFTER, FEEDBACK_FAILED_DELTA, FEEDBACK_WORKED_DELTA,
                        TIMEZONE)

log = logging.getLogger("api.feedback")
_ingest_lock = threading.Lock()

SAME_VOTE_WINDOW_MIN = 30

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
CREATE (f:Feedback {id: $fid, verdict: $verdict, comment: $comment, message_id: $mid, created_at: datetime(),
                    tried_actions: $tried_actions, resolved_by_action: $resolved_by_action})
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
           devices: list[str] | None = None, user: dict | None = None,
           tried_actions: list[str] | None = None, resolved_by_action: str | None = None
           ) -> tuple[list[dict], list[str]]:
    """Apply one vote to every assertion of a card. Returns (new state per assertion, Feedback ids that
    hold the note, used to link the note to what it became in the graph)."""
    updated, note_ids = [], []
    for aid in ids:
        if not graph.run("MATCH (a:Assertion {id: $aid}) RETURN a.id", aid=aid):
            continue
        prev = graph.run(PREVIOUS_QUERY, aid=aid, mid=message_id, window=SAME_VOTE_WINDOW_MIN)
        prev = dict(prev[0]) if prev else None

        if prev and prev["verdict"] == verdict:
            if comment:
                graph.run("MATCH (f:Feedback {id: $id}) SET f.comment = $c", id=prev["id"], c=comment)
            if tried_actions or resolved_by_action:
                graph.run("MATCH (f:Feedback {id: $id}) "
                          "SET f.tried_actions = coalesce($tried_actions, f.tried_actions), "
                          "f.resolved_by_action = coalesce($resolved_by_action, f.resolved_by_action)",
                          id=prev["id"], tried_actions=tried_actions or None, resolved_by_action=resolved_by_action)
            if comment or tried_actions or resolved_by_action:
                note_ids.append(prev["id"])
            state = graph.run(STATE_QUERY, aid=aid)
            updated.append(dict(state[0]))
            continue

        if prev:
            graph.run("MATCH (f:Feedback {id: $id}) SET f.replaced = true", id=prev["id"])
            _apply(aid, prev["verdict"], -1)

        if verdict == "skipped" and not comment:
            state = graph.run(STATE_QUERY, aid=aid)
            updated.append(dict(state[0]))
            continue

        fid = f"FB-{uuid.uuid4().hex[:10]}-{aid}"
        graph.run(CREATE_QUERY, aid=aid, fid=fid, verdict=verdict, comment=comment, mid=message_id,
                  devices=list(devices or []), user_name=(user or {}).get("name") or "Field Engineer",
                  user_role=(user or {}).get("role"),
                  tried_actions=list(tried_actions or []) or None, resolved_by_action=resolved_by_action)
        if comment or tried_actions or resolved_by_action:
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
        graph.run("UNWIND $fids AS fid MATCH (f:Feedback {id: fid}) MATCH (s:Source {id: $sid}) "
                  "MERGE (f)-[:CAPTURED_AS]->(s)", fids=list(feedback_ids or []), sid=thread["thread_id"])
        log.info("Feedback comment ingested as %s", thread["thread_id"])
    except Exception:
        log.exception("Could not ingest feedback comment")


def valid_action_codes(codes: list[str] | None) -> list[str]:
    """Keep only codes that exist as action terms in the vocabulary (the UI offers only those)."""
    codes = [c for c in dict.fromkeys(codes or []) if c]
    if not codes:
        return []
    rows = graph.run("MATCH (t:Term {category: 'action'}) WHERE t.name IN $codes RETURN t.name AS name", codes=codes)
    known = {r["name"] for r in rows}
    return [c for c in codes if c in known]


CARD_CONTEXT_QUERY = """
MATCH (a:Assertion) WHERE a.id IN $ids
RETURN a.symptoms AS symptoms, a.events AS events, a.knowledge_type AS knowledge_type
"""

_NORMAL_STATES = {"INTERFACE_UP", "OPTICAL_LEVELS_NORMAL", "ALARMS_CLEARED"}


def _phrase(code: str) -> str:
    from api.cards import action_text
    return action_text(code) if code else ""


def _symptom_words(symptoms: list[str]) -> str:
    from api.cards import humanize
    main = [s for s in symptoms if s not in _NORMAL_STATES] or symptoms
    return humanize(main[0]).lower() if main else "the problem"


def _reconcile(assertion_id: str, reporter: dict | None):
    from pipeline import reconcile
    reconcile.reconcile(assertion_id, reporter)


def capture_structured(verdict: str, ids: list[str], message: dict | None, summary: str | None,
                       tried_actions: list[str] | None, resolved_by_action: str | None, comment: str | None,
                       feedback_ids: list[str] | None = None, user: dict | None = None):
    """Background task: the engineer's chosen options become tips directly, built from the codes.

    - tried_actions (didn't help)  -> a 'failed attempt' tip (shows under "What didn't work")
    - resolved_by_action (fixed it) -> a 'worked' tip with that action as the fix
    Symptoms and events come from the card the engineer answered, so the new tips describe the same problem.
    They are bound to the device(s) of the question; reconcile then relates them to older tips."""
    from pipeline.ingest import BASE_CONFIDENCE, reporter_confidence

    try:
        nodes = (message or {}).get("node_ids") or _devices_of(ids)
        devices = ", ".join(nodes) or "an unnamed device"
        ctx = [dict(r) for r in graph.run(CARD_CONTEXT_QUERY, ids=list(ids))]
        symptoms = sorted({x for r in ctx for x in (r.get("symptoms") or [])})
        events = sorted({x for r in ctx for x in (r.get("events") or [])})
        problem = _symptom_words(symptoms)
        now = _now()
        who = (user or {}).get("name") or "Field Engineer"
        role = (user or {}).get("role") or "Field Engineer"
        reporter = {"name": who, "role": role, "app": APP_NAME, "date": now[:10]}
        tried = [_phrase(c) for c in tried_actions or []]
        thread_id = f"FB-{uuid.uuid4().hex[:8].upper()}"
        text = (f"Structured report in {APP_NAME} by {who} ({role}) on {devices}. "
                f"Question: {(message or {}).get('question') or '-'} Suggested tip: {summary or '-'} "
                f"Verdict: {verdict}. Tried without success: {', '.join(tried) or '-'}. "
                f"Fixed by: {_phrase(resolved_by_action) if resolved_by_action else '-'}. Note: {comment or '-'}")
        thread = {"thread_id": thread_id, "channel": APP_NAME, "language": None, "subject": f"Report on {devices}",
                  "participants": [who], "reported_by": reporter,
                  "messages": [{"seq": 1, "timestamp": now, "author": who, "role": role, "text": text}]}

        base = {"source_id": thread_id, "knowledge_type": "troubleshooting_rule", "events": events,
                "symptoms": symptoms, "avoid": [], "author": who, "observed_on": list(nodes),
                "scope_node_type": None, "scope_installed_before": None, "scope_firmware_below": None,
                "scope_firmware_at_least": None, "valid_from": now}
        tips = []
        if tried_actions and verdict == "failed":
            tips.append({**base, "id": f"{thread_id}-1", "outcome": "failed", "actions": list(tried_actions),
                         "confidence": BASE_CONFIDENCE["failed"], "details": None,
                         "summary": f"On {devices}, {' and '.join(t.lower() for t in tried)} did not fix "
                                    f"{problem} (reported by {who} in {APP_NAME})."})
        if resolved_by_action:
            fix = _phrase(resolved_by_action)
            tips.append({**base, "id": f"{thread_id}-2", "outcome": "worked", "actions": [resolved_by_action],
                         "confidence": max(BASE_CONFIDENCE["worked"], reporter_confidence(reporter)),
                         "details": comment or None,
                         "summary": f"On {devices}, {problem} was fixed by: {fix[:1].lower() + fix[1:]}"
                                    + (f" (after {', '.join(t.lower() for t in tried)} did not help)" if tried else "")
                                    + f". Reported by {who} in {APP_NAME}."})
        if not tips:
            return
        with _ingest_lock:
            graph.save_source(thread, text)
            for a in tips:
                graph.save_assertion(a)
                graph.link_terms(a)
            for a in tips:
                _reconcile(a["id"], reporter)
            graph.mark_source_done(thread_id)
        graph.run("MERGE (p:Person {name: $n}) SET p.role = $r", n=who, r=role)
        graph.run("UNWIND $fids AS fid MATCH (f:Feedback {id: fid}) MATCH (s:Source {id: $sid}) "
                  "MERGE (f)-[:CAPTURED_AS]->(s)", fids=list(feedback_ids or []), sid=thread_id)
        log.info("Structured feedback captured as %s: %s", thread_id, [a["id"] for a in tips])
    except Exception:
        log.exception("Could not capture structured feedback")
