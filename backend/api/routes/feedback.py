"""POST /api/feedback: 👍 / 👎 / skip on a knowledge card, with an optional comment."""
from fastapi import APIRouter, BackgroundTasks, HTTPException

from api import feedback, store
from api.config import MIN_COMMENT_CHARS
from api.models import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackResponse)
def post_feedback(req: FeedbackRequest, background: BackgroundTasks):
    message = store.get_message(req.message_id)
    shown = (message or {}).get("cards", {}).get(req.assertion_id or "", {})
    # A card can stand for several merged assertions: apply the feedback to all of them.
    ids = req.assertion_ids or shown.get("knowledge_ids") or ([req.assertion_id] if req.assertion_id else [])
    if not ids:
        raise HTTPException(422, "Give assertion_id (or assertion_ids)")

    updated = feedback.record(ids, req.verdict, req.comment, req.message_id)
    if not updated:
        raise HTTPException(404, "None of the given assertions exist")

    comment = (req.comment or "").strip()
    queued = len(comment) >= MIN_COMMENT_CHARS
    if queued:
        background.add_task(feedback.ingest_comment, comment, req.verdict, ids, message, shown.get("summary"))
    return {"ok": True, "updated": updated, "comment_queued": queued}
