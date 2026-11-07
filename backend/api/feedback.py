"""
Feedback loop (Full_pipeline.txt, last box):

  ✅ worked  -> confidence +0.1 (max 0.95)
  ❌ failed  -> confidence -0.2 (min 0.05); after repeated failures (more failed than worked,
               at least FEEDBACK_DISPUTE_AFTER) the tip is marked 'disputed'
  ⏭ skipped -> only recorded
  comment    -> runs through Flow 1 (ingest.process) as a new conversation, so "it was the patch
               cable" becomes new knowledge, linked and reconciled like any chat.

Every click is stored as (:Feedback)-[:ABOUT]->(:Assertion) so it can be shown and audited.
"""
import logging
import threading
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline import graph
from api.config import (FEEDBACK_DISPUTE_AFTER, FEEDBACK_FAILED_DELTA, FEEDBACK_WORKED_DELTA, TIMEZONE)

log = logging.getLogger("api.feedback")
_ingest_lock = threading.Lock()  # one comment at a time through the pipeline

RECORD_QUERY = """
UNWIND $ids AS aid
MATCH (a:Assertion {id: aid})
CREATE (f:Feedback {id: $fid + '-' + aid, verdict: $verdict, comment: $comment,
                    message_id: $mid, created_at: datetime()})
CREATE (f)-[:ABOUT]->(a)
WITH a, coalesce(a.confidence, 0.5) AS c
SET a.feedback_worked = coalesce(a.feedback_worked, 0) + CASE WHEN $verdict = 'worked' THEN 1 ELSE 0 END,
    a.feedback_failed = coalesce(a.feedback_failed, 0) + CASE WHEN $verdict = 'failed' THEN 1 ELSE 0 END,
    a.confidence = CASE $verdict
        WHEN 'worked' THEN round(CASE WHEN c + $up > 0.95 THEN 0.95 ELSE c + $up END, 2)
        WHEN 'failed' THEN round(CASE WHEN c + $down < 0.05 THEN 0.05 ELSE c + $down END, 2)
        ELSE c END
WITH a
SET a.status = CASE WHEN a.feedback_failed >= $dispute_after AND a.feedback_failed > a.feedback_worked
                    THEN 'disputed' ELSE a.status END
RETURN a.id AS id, a.confidence AS confidence, a.status AS status,
       a.feedback_worked AS worked, a.feedback_failed AS failed
"""


def record(ids: list[str], verdict: str, comment: str | None, message_id: str | None) -> list[dict]:
    rows = graph.run(RECORD_QUERY, ids=ids, verdict=verdict, comment=comment, mid=message_id,
                     fid=f"FB-{uuid.uuid4().hex[:10]}", up=FEEDBACK_WORKED_DELTA, down=FEEDBACK_FAILED_DELTA,
                     dispute_after=FEEDBACK_DISPUTE_AFTER)
    return [dict(r) for r in rows]


def _devices_of(ids: list[str]) -> list[str]:
    rows = graph.run("MATCH (a:Assertion)-[:OBSERVED_ON]->(d:Device) WHERE a.id IN $ids "
                     "RETURN collect(DISTINCT d.node_id) AS ids", ids=ids)
    return list(rows[0]["ids"]) if rows else []


def ingest_comment(comment: str, verdict: str, ids: list[str], message: dict | None, summary: str | None):
    """Background task: the engineer's comment becomes a new 'feedback' conversation in the graph."""
    from pipeline import ingest
    from pipeline.vocabulary import Vocabulary

    try:
        nodes = (message or {}).get("node_ids") or _devices_of(ids)
        verdict_text = {"worked": "the suggested tip worked", "failed": "the suggested tip did NOT work",
                        "skipped": "the suggested tip was not tried"}[verdict]
        text = (f"Feedback from a field engineer on {', '.join(nodes) or 'an unnamed device'}.\n"
                f"Original problem: {(message or {}).get('question') or '-'}\n"
                f"Suggested tip: {summary or '-'}\n"
                f"Result: {verdict_text}.\n"
                f"Engineer's comment: {comment}")
        thread = {
            "thread_id": f"FB-{uuid.uuid4().hex[:8].upper()}",
            "channel": "feedback",
            "language": None,
            "subject": None,
            "participants": ["Field Engineer"],
            "messages": [{"seq": 1, "timestamp": datetime.now(ZoneInfo(TIMEZONE)).isoformat(timespec="seconds"),
                          "author": "Field Engineer", "role": "Field Engineer", "text": text}],
        }
        with _ingest_lock:
            vocab = Vocabulary(use_graph=True).load()
            ingest.process(thread, dry_run=False, vocab=vocab)
        log.info("Feedback comment ingested as %s", thread["thread_id"])
    except Exception:
        log.exception("Could not ingest feedback comment")
