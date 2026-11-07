"""
Structured feedback (vocabulary codes instead of free text) and the UI-language hint.
No Neo4j or Gemini needed. Run from backend/:  python -m pytest tests -q
"""
import pytest
from fastapi.testclient import TestClient

import api  # noqa: F401
from api import answer, feedback, store
from api.knowledge import KnowledgeResult
from api.main import app
from api.models import FeedbackRequest
from api.understand import Understood


# ---------- request model ----------
def test_feedback_request_accepts_codes():
    r = FeedbackRequest(assertion_id="T001-1", verdict="failed",
                        tried_actions=["BOUNCE_INTERFACE"], resolved_by_action="REPLACE_PATCH_CABLE")
    assert r.tried_actions == ["BOUNCE_INTERFACE"] and r.resolved_by_action == "REPLACE_PATCH_CABLE"


# ---------- route: which capture path is used ----------
@pytest.fixture
def route(monkeypatch):
    calls = {"record": [], "structured": [], "text": []}
    monkeypatch.setattr(store, "get_message", lambda mid: {"node_ids": ["TRN-031"], "question": "q",
                        "cards": {"T001-1": {"knowledge_ids": ["T001-1", "E001-1"], "summary": "bounce"}}})

    def record(ids, verdict, comment, mid, devices=None, user=None, tried_actions=None, resolved_by_action=None):
        calls["record"].append(dict(ids=ids, verdict=verdict, comment=comment, tried=tried_actions,
                                    resolved=resolved_by_action))
        return [{"id": i} for i in ids], ["FB-1"]

    monkeypatch.setattr(feedback, "record", record)
    monkeypatch.setattr(feedback, "valid_action_codes",
                        lambda codes: [c for c in codes if c in {"BOUNCE_INTERFACE", "REPLACE_PATCH_CABLE"}])
    monkeypatch.setattr(feedback, "capture_structured", lambda *a, **k: calls["structured"].append((a, k)))
    monkeypatch.setattr(feedback, "ingest_comment", lambda *a, **k: calls["text"].append(a))
    return TestClient(app), calls


def test_codes_are_captured_without_gemini(route):
    client, calls = route
    r = client.post("/api/feedback", json={"message_id": "m-1", "assertion_id": "T001-1", "verdict": "failed",
                                           "tried_actions": ["BOUNCE_INTERFACE", "NOT_A_CODE"],
                                           "resolved_by_action": "REPLACE_PATCH_CABLE",
                                           "comment": "the new cable fixed it right away"})
    assert r.status_code == 200 and r.json()["structured_queued"] is True
    assert r.json()["comment_queued"] is False            # the note is kept, but not sent through Gemini
    assert calls["record"][0]["tried"] == ["BOUNCE_INTERFACE"]          # unknown codes dropped
    assert calls["record"][0]["resolved"] == "REPLACE_PATCH_CABLE"
    assert len(calls["structured"]) == 1 and not calls["text"]


def test_something_else_text_still_goes_through_gemini(route):
    client, calls = route
    r = client.post("/api/feedback", json={"message_id": "m-1", "assertion_id": "T001-1", "verdict": "failed",
                                           "comment": "fan was blocked by snow, cleaned it"})
    assert r.json()["comment_queued"] is True and r.json()["structured_queued"] is False
    assert calls["text"] and not calls["structured"]


def test_unknown_fix_code_with_text_falls_back_to_gemini(route):
    client, calls = route
    r = client.post("/api/feedback", json={"message_id": "m-1", "assertion_id": "T001-1", "verdict": "failed",
                                           "resolved_by_action": "MADE_UP", "comment": "something odd happened"})
    assert r.json()["structured_queued"] is False and calls["text"]


def test_thumbs_up_one_tap_needs_no_codes(route):
    client, calls = route
    r = client.post("/api/feedback", json={"message_id": "m-1", "assertion_id": "T001-1", "verdict": "worked"})
    assert r.status_code == 200 and r.json()["structured_queued"] is False and not calls["text"]


# ---------- record() stores the codes on the Feedback node ----------
def test_record_stores_codes(monkeypatch):
    params = []

    def run(q, **p):
        params.append((q, p))
        if "RETURN a.id" in q:
            return [{"a.id": p["aid"]}]
        if "f.replaced IS NULL" in q:      # no earlier vote
            return []
        return [{"id": p.get("aid"), "confidence": 0.5, "status": "auto_captured", "worked": 0, "failed": 1}]

    monkeypatch.setattr(feedback.graph, "run", run)
    feedback.record(["T001-1"], "failed", None, "m-1", devices=["TRN-031"], user={"name": "Veikko"},
                    tried_actions=["BOUNCE_INTERFACE"], resolved_by_action="REPLACE_PATCH_CABLE")
    create = [p for q, p in params if "CREATE (f:Feedback" in q][0]
    assert create["tried_actions"] == ["BOUNCE_INTERFACE"] and create["resolved_by_action"] == "REPLACE_PATCH_CABLE"


def test_record_attaches_codes_to_the_earlier_click(monkeypatch):
    """The UI sends the 👎 click first, then the chosen option with the same verdict."""
    params = []

    def run(q, **p):
        params.append((q, p))
        if "RETURN a.id" in q:
            return [{"a.id": p["aid"]}]
        if "f.replaced IS NULL" in q:
            return [{"id": "FB-old", "verdict": "failed"}]
        return [{"id": p.get("aid"), "confidence": 0.3, "status": "auto_captured", "worked": 0, "failed": 1}]

    monkeypatch.setattr(feedback.graph, "run", run)
    _, note_ids = feedback.record(["T001-1"], "failed", None, "m-1", tried_actions=["BOUNCE_INTERFACE"],
                                  resolved_by_action="REPLACE_PATCH_CABLE")
    upd = [p for q, p in params if "f.tried_actions" in q and "SET" in q and "CREATE" not in q]
    assert upd and upd[0]["id"] == "FB-old" and upd[0]["resolved_by_action"] == "REPLACE_PATCH_CABLE"
    assert "FB-old" in note_ids                       # linked to the tips it becomes
    assert not [q for q, p in params if "CREATE (f:Feedback" in q]   # not counted twice


# ---------- capture_structured() builds tips from the codes ----------
def test_structured_capture_builds_tips_from_codes(monkeypatch):
    saved, sources, linked, reconciled = [], [], [], []
    monkeypatch.setattr(feedback.graph, "save_source", lambda t, text: sources.append((t, text)))
    monkeypatch.setattr(feedback.graph, "save_assertion", lambda a: saved.append(a))
    monkeypatch.setattr(feedback.graph, "link_terms", lambda a: linked.append(a["id"]))
    monkeypatch.setattr(feedback.graph, "mark_source_done", lambda sid: None)

    def run(q, **p):
        if "a.id IN $ids" in q and "symptoms" in q:     # the card's context
            return [{"symptoms": ["INTERFACE_UP", "TRAFFIC_COUNTERS_ZERO"], "events": ["SFP_REPLACEMENT"],
                     "knowledge_type": "troubleshooting_rule"}]
        return []

    monkeypatch.setattr(feedback.graph, "run", run)
    monkeypatch.setattr(feedback, "_reconcile", lambda aid, reporter: reconciled.append(aid))

    feedback.capture_structured("failed", ["T001-1"], {"node_ids": ["TRN-031"], "question": "no traffic"},
                                "bounce the interface", ["BOUNCE_INTERFACE"], "REPLACE_PATCH_CABLE",
                                "new cable fixed it", ["FB-old"], {"name": "Veikko Vikkelä", "role": "Field Engineer"})

    assert sources and sources[0][0]["channel"] == feedback.APP_NAME
    failed = [a for a in saved if a["outcome"] == "failed"][0]
    fixed = [a for a in saved if a["outcome"] == "worked"][0]
    assert failed["actions"] == ["BOUNCE_INTERFACE"] and fixed["actions"] == ["REPLACE_PATCH_CABLE"]
    for a in (failed, fixed):
        assert a["symptoms"] == ["INTERFACE_UP", "TRAFFIC_COUNTERS_ZERO"] and a["events"] == ["SFP_REPLACEMENT"]
        assert a["observed_on"] == ["TRN-031"] and a["author"] == "Veikko Vikkelä"
        assert a["source_id"] == sources[0][0]["thread_id"]
    assert "patch cable" in fixed["summary"].lower() and fixed["details"] == "new cable fixed it"
    assert sorted(linked) == sorted(a["id"] for a in saved) and sorted(reconciled) == sorted(linked)


def test_structured_capture_without_fix_only_records_failed_attempt(monkeypatch):
    saved = []
    monkeypatch.setattr(feedback.graph, "save_source", lambda t, text: None)
    monkeypatch.setattr(feedback.graph, "save_assertion", lambda a: saved.append(a))
    monkeypatch.setattr(feedback.graph, "link_terms", lambda a: None)
    monkeypatch.setattr(feedback.graph, "mark_source_done", lambda sid: None)
    monkeypatch.setattr(feedback.graph, "run", lambda q, **p: [])
    monkeypatch.setattr(feedback, "_reconcile", lambda aid, reporter: None)
    feedback.capture_structured("failed", ["T001-1"], {"node_ids": ["TRN-031"]}, "s", ["BOUNCE_INTERFACE"],
                                None, None, [], None)
    assert [a["outcome"] for a in saved] == ["failed"]


# ---------- UI-language hint ----------
def _chat(monkeypatch, message, understood, ui_language):
    from api.routes import chat as chat_route
    seen = {}
    monkeypatch.setattr(chat_route.understand, "understand", lambda *a, **k: understood)
    monkeypatch.setattr(chat_route.knowledge, "for_devices", lambda *a, **k: KnowledgeResult(cards=[]))
    monkeypatch.setattr(chat_route.knowledge, "search", lambda *a, **k: KnowledgeResult(cards=[]))

    def stream(message, hist, u, k):
        seen["language"] = u.language
        yield "ok"

    monkeypatch.setattr(chat_route.answer, "stream_answer", stream)
    TestClient(app).post("/api/chat?stream=false", json={"message": message, "ui_language": ui_language})
    return seen["language"]


def test_ui_language_used_for_very_short_messages(monkeypatch):
    assert _chat(monkeypatch, "TRN-031?", Understood(node_ids=["TRN-031"], language="en"), "fi") == "fi"


def test_ui_language_used_when_gemini_is_down(monkeypatch):
    u = Understood(node_ids=["TRN-031"], language="en", by="fallback")
    assert _chat(monkeypatch, "SFP vaihdettu mutta liikenne ei kulje", u, "fi") == "fi"


def test_question_language_wins_otherwise(monkeypatch):
    u = Understood(node_ids=["TRN-031"], language="en")
    assert _chat(monkeypatch, "SFP replaced but no traffic on the link", u, "fi") == "en"


def test_template_answer_in_finnish():
    text = answer.fallback_answer(Understood(language="fi"), KnowledgeResult(cards=[]))
    assert "asiantuntija" in text.lower() and "No captured" not in text
