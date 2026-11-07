"""In-memory conversations and messages (lost on restart; the knowledge itself is in Neo4j).
Each message keeps the cards it showed, so feedback can be applied to all merged assertions."""
import threading
import uuid
from collections import OrderedDict

from api.config import HISTORY_TURNS

_lock = threading.Lock()
_conversations: "OrderedDict[str, dict]" = OrderedDict()
_messages: "OrderedDict[str, dict]" = OrderedDict()
MAX_CONVERSATIONS = 500
MAX_MESSAGES = 5000


def ensure_conversation(conversation_id: str | None) -> str:
    with _lock:
        cid = conversation_id or f"c-{uuid.uuid4().hex[:12]}"
        _conversations.setdefault(cid, {"turns": [], "nodes": []})
        _conversations.move_to_end(cid)
        while len(_conversations) > MAX_CONVERSATIONS:
            _conversations.popitem(last=False)
        return cid


def history(cid: str) -> list[tuple[str, str]]:
    with _lock:
        return list(_conversations.get(cid, {}).get("turns", []))[-HISTORY_TURNS:]


def last_nodes(cid: str) -> list[str]:
    with _lock:
        return list(_conversations.get(cid, {}).get("nodes", []))


def _card_index(cards: list[dict]) -> dict[str, dict]:
    idx = {}
    for c in cards:
        idx[c["assertion_id"]] = {"knowledge_ids": c["knowledge_ids"], "summary": c["summary"]}
        for f in c.get("related_failed", []):
            idx[f["assertion_id"]] = {"knowledge_ids": f["knowledge_ids"], "summary": f["summary"]}
        idx.update(_card_index(c.get("conflicts_with", [])))
    return idx


def save_turn(cid: str, question: str, answer: str, node_ids: list[str], cards: list[dict]) -> str:
    mid = f"m-{uuid.uuid4().hex[:12]}"
    with _lock:
        conv = _conversations.setdefault(cid, {"turns": [], "nodes": []})
        conv["turns"] += [("user", question), ("assistant", answer)]
        conv["turns"] = conv["turns"][-2 * HISTORY_TURNS:]
        if node_ids:
            conv["nodes"] = list(node_ids)
        _messages[mid] = {"conversation_id": cid, "question": question, "node_ids": list(node_ids),
                          "cards": _card_index(cards)}
        while len(_messages) > MAX_MESSAGES:
            _messages.popitem(last=False)
    return mid


def get_message(mid: str | None) -> dict | None:
    if not mid:
        return None
    with _lock:
        return _messages.get(mid)
