"""POST /api/feedback: 👍 / 👎 / skip on a knowledge card, with an optional comment."""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from api import feedback, store
from api.config import DEMO_USER_NAME, DEMO_USER_ROLE, MIN_COMMENT_CHARS
from api.models import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(req: FeedbackRequest, background: BackgroundTasks, request: Request):
    # Who: the logged-in user (body fields, or headers from a login proxy), else the demo user
    user = {"name": req.user_name or request.headers.get("x-user-name") or DEMO_USER_NAME or "Field Engineer",
            "role": req.user_role or request.headers.get("x-user-role") or DEMO_USER_ROLE or "Field Engineer"}
    message = store.get_message(req.message_id)
    shown = (message or {}).get("cards", {}).get(req.assertion_id or "", {})
    # A card can stand for several merged assertions: apply the feedback to all of them.
    ids = req.assertion_ids or shown.get("knowledge_ids") or ([req.assertion_id] if req.assertion_id else [])
    if not ids:
        raise HTTPException(422, "Give assertion_id (or assertion_ids)")

    comment = (req.comment or "").strip() or None
    # Structured outcome: only codes that exist in the vocabulary count
    tried = feedback.valid_action_codes(req.tried_actions) if req.tried_actions else []
    resolved = (feedback.valid_action_codes([req.resolved_by_action]) or [None])[0] if req.resolved_by_action else None
    updated, note_ids = feedback.record(ids, req.verdict, comment, req.message_id,
                                        devices=(message or {}).get("node_ids"), user=user,
                                        tried_actions=tried or None, resolved_by_action=resolved)
    if not updated:
        raise HTTPException(404, "None of the given assertions exist")

    # Codes -> tips directly (no Gemini); the note is kept as the tip's details.
    # Only free text without usable codes ("Something else…") goes through the Gemini capture pipeline.
    structured = bool(resolved or (tried and req.verdict == "failed"))
    if structured:
        background.add_task(feedback.capture_structured, req.verdict, ids, message, shown.get("summary"),
                            tried, resolved, comment, note_ids, user)
    queued = not structured and len(comment or "") >= MIN_COMMENT_CHARS
    if queued:
        background.add_task(feedback.ingest_comment, comment, req.verdict, ids, message, shown.get("summary"),
                            note_ids, user)
    return {"ok": True, "updated": updated, "comment_queued": queued, "structured_queued": structured}
