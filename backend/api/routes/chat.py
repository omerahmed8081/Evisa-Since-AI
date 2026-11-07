"""POST /api/chat: Step A (understand) -> Step B (retrieve) -> Step C (answer), streamed as SSE."""
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api import answer, knowledge, store, understand
from api.models import ChatRequest, ChatResponse

log = logging.getLogger("api.chat")
router = APIRouter(prefix="/api", tags=["chat"])


def chat_events(req: ChatRequest):
    """Yields (event, data) pairs in the order the frontend expects: meta, token*, cards, done."""
    cid = store.ensure_conversation(req.conversation_id)
    hist = store.history(cid)

    # Step A
    u = understand.understand(req.message, req.node_id, hist, store.last_nodes(cid))
    # Step B
    if u.node_ids:
        k = knowledge.for_devices(u.node_ids, u.symptoms, u.events, u.wants_access_info,
                                  overview=u.wants_overview, history=u.wants_history)
    else:
        k = knowledge.search(u.symptoms, u.events, u.node_type, u.wants_access_info)

    yield "meta", {"conversation_id": cid, "resolved_nodes": u.node_ids, "unknown_nodes": u.unknown_nodes,
                   "symptoms": u.symptoms, "events": u.events, "node_type": u.node_type,
                   "retrieval": k.mode, "understood_by": u.by,
                   "resolved_by": u.resolved_by, "resolution_note": u.resolution_note,
                   "ignored_selection": u.ignored_selection,
                   "question_type": "history" if u.wants_history else ("overview" if u.wants_overview else "problem")}

    # Step C
    parts: list[str] = []
    try:
        for t in answer.stream_answer(req.message, hist, u, k):
            parts.append(t)
            yield "token", {"text": t}
    except Exception as e:
        log.warning("Step C failed (%s); %s", e, "using template answer" if not parts else "stream cut")
        if parts:
            yield "error", {"message": "The answer was interrupted. The knowledge cards are still shown below."}
        else:
            text = answer.fallback_answer(u, k)
            parts.append(text)
            yield "token", {"text": text}

    yield "cards", {"cards": k.cards}
    mid = store.save_turn(cid, req.message, "".join(parts), u.node_ids, k.cards)
    yield "done", {"message_id": mid}


def _sse(req: ChatRequest):
    try:
        for event, data in chat_events(req):
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    except Exception as e:  # e.g. Neo4j unreachable
        log.exception("chat failed")
        yield f"event: error\ndata: {json.dumps({'message': f'Knowledge service error: {e.__class__.__name__}'})}\n\n"


@router.post("/chat", response_model=ChatResponse,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "SSE stream (default) or JSON with ?stream=false"}})
def chat(req: ChatRequest, request: Request, stream: bool = True):
    accept = request.headers.get("accept", "")
    if not stream or (accept.startswith("application/json") and "text/event-stream" not in accept):
        result = {"answer": "", "cards": [], "resolved_nodes": []}
        for event, data in chat_events(req):
            if event == "meta":
                result.update(conversation_id=data["conversation_id"], resolved_nodes=data["resolved_nodes"])
            elif event == "token":
                result["answer"] += data["text"]
            elif event == "cards":
                result["cards"] = data["cards"]
            elif event == "done":
                result["message_id"] = data["message_id"]
        return JSONResponse(ChatResponse(**result).model_dump())
    return StreamingResponse(_sse(req), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
