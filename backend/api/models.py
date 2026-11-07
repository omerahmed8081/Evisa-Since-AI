"""Request/response shapes. They follow section 4 of UI_PROMPT.md (the frontend contract)."""
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- requests ----------
class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str = Field(min_length=1, max_length=4000)
    node_id: Optional[str] = Field(default=None, description="Device picked in the UI's device selector")


class FeedbackRequest(BaseModel):
    message_id: Optional[str] = None
    assertion_id: Optional[str] = Field(default=None, description="The card's assertion_id")
    assertion_ids: Optional[list[str]] = Field(default=None, description="Alternative: explicit list of ids")
    verdict: Literal["worked", "failed", "skipped"]
    comment: Optional[str] = Field(default=None, max_length=2000)
    user_name: Optional[str] = Field(default=None, max_length=120, description="Logged-in user (e.g. 'Erkki Expert')")
    user_role: Optional[str] = Field(default=None, max_length=60, description="e.g. 'Network Expert', 'Field Engineer', 'NOC Operator'")


# ---------- knowledge cards ----------
class Source(BaseModel):
    thread_id: str
    channel: str  # teams | email | call | feedback
    author: Optional[str] = None
    timestamp: Optional[str] = None
    excerpt: Optional[str] = None


class Scope(BaseModel):
    node_type: Optional[str] = None
    installed_before: Optional[str] = None
    firmware_below: Optional[str] = None
    firmware_at_least: Optional[str] = None


class FailedRef(BaseModel):
    assertion_id: str
    knowledge_ids: list[str]
    summary: str
    actions_text: list[str] = []
    sources: list[Source] = []


class KnowledgeCard(BaseModel):
    assertion_id: str
    knowledge_ids: list[str] = Field(description="All stored assertions merged into this card (send these with feedback)")
    knowledge_type: str
    summary: str
    actions: list[str]
    actions_text: list[str]
    avoid: list[str]
    avoid_text: list[str]
    outcome: Literal["worked", "failed", "unknown"]
    status: Literal["confirmed", "disputed", "outdated", "unconfirmed"]
    confidence: float
    symptom_match: Optional[float] = None
    how_it_applies: Optional[str] = None
    scope: Scope
    scope_text: str
    scope_note: Optional[str] = None
    observed_on: list[str]
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    details: Optional[str] = None
    sources: list[Source]
    conflicts_with: list["KnowledgeCard"] = []
    related_failed: list[FailedRef] = []
    link: Optional[dict] = Field(default=None, description="How the knowledge reaches this device: "
                                 "{how: id|alias|location|site|scope, via, site, candidates}")


KnowledgeCard.model_rebuild()


# ---------- other responses ----------
class ChatResponse(BaseModel):
    """Plain JSON form of /api/chat (when called with ?stream=false or Accept: application/json)."""
    conversation_id: str
    message_id: str
    answer: str
    cards: list[KnowledgeCard]
    resolved_nodes: list[str]


class Node(BaseModel):
    node_id: str
    node_type: Optional[str] = None
    install_date: Optional[str] = None
    firmware: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None


class Event(BaseModel):
    event_id: str
    timestamp: Optional[str] = None
    event_type: Optional[str] = None
    detail: Optional[str] = None
    from_firmware: Optional[str] = None
    to_firmware: Optional[str] = None
    related_thread: Optional[str] = None


class NodeDetail(BaseModel):
    node: Node
    knowledge: list[KnowledgeCard]
    events: list[Event]


class Stats(BaseModel):
    assertions: int
    valid_assertions: int
    devices: int
    sources: int
    terms: int
    feedback: int


class FeedbackResponse(BaseModel):
    ok: bool
    updated: list[dict]
    comment_queued: bool
