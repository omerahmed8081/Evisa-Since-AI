"""
Regression tests for the chat bugs found on 7 Nov 2026 (no Neo4j or Gemini needed).

Run from backend/:   python -m pytest tests/test_chat_fixes.py -q
"""
import csv
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

import api  # noqa: F401  (sets up paths)
from api import answer, cards, llm, understand
from api.knowledge import KnowledgeResult
from api.understand import Understood
from pipeline import cache, linking

BACKEND = Path(__file__).resolve().parents[1]


# ---------- helpers ----------
def bounce_card(**over):
    """The TRN-031 bounce-fix card as the API builds it (4 sources, seen on 3 devices)."""
    card = {
        "assertion_id": "T001-1", "knowledge_ids": ["T001-1", "E001-1", "T002-1", "E006-1"],
        "knowledge_type": "troubleshooting_rule", "status": "confirmed", "outcome": "worked",
        "summary": "Zero traffic after SFP swap on older transmission nodes: bounce the interface.",
        "actions": ["CHECK_TRAFFIC_COUNTERS", "BOUNCE_INTERFACE"], "avoid": ["REBOOT_UNIT", "REPLACE_SFP"],
        "scope": {"node_type": "transmission", "installed_before": "2020-01-01", "firmware_below": "3.4",
                  "firmware_at_least": None},
        "actions_text": ["Check that the traffic counters are increasing", "Disable and re-enable the interface"],
        "avoid_text": ["Don't reboot the whole unit", "Don't replace the SFP"],
        "scope_text": "Transmission nodes installed before 2020, firmware below 3.4",
        "how_it_applies": "observed on this device", "confidence": 0.95,
        "observed_on": ["TRN-031", "TRN-042", "TRN-077"],
        "sources": [
            {"thread_id": "T001", "channel": "teams", "author": "Erkki Expert", "timestamp": "2025-03-12T09:14:00+02:00"},
            {"thread_id": "E001", "channel": "email", "author": "Erkki Expert", "timestamp": "2025-03-12T14:02:00+02:00"},
            {"thread_id": "T002", "channel": "teams", "author": "Erkki Expert", "timestamp": "2025-09-04T10:05:00+03:00"},
            {"thread_id": "E006", "channel": "email", "author": "Erkki Expert", "timestamp": "2026-02-16T10:20:00+02:00"},
        ],
        "details": None, "valid_to": None, "scope_note": None, "related_failed": [], "conflicts_with": [],
    }
    card.update(over)
    return card


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(cache, "ENABLED", True, raising=False)
    return tmp_path


class FakeResponse:
    def __init__(self, parsed):
        self.parsed, self.text = parsed, parsed.model_dump_json()


def fake_client(result, calls):
    class Models:
        def generate_content(self, **kw):
            calls.append(kw)
            return FakeResponse(result)

    class Client:
        models = Models()

    return lambda: Client()


# ---------- Bug 1: Step A cache ignores the schema ----------
class OldSchema(BaseModel):
    node_ids: list[str]


class NewSchema(BaseModel):
    node_ids: list[str]
    wants_overview: bool = Field(default=False)


def test_schema_change_does_not_reuse_old_cached_understanding(tmp_cache, monkeypatch):
    prompt, system = "MESSAGE\nwhat are possible faults related to TRN-031", "SYSTEM"
    # an entry written by the code BEFORE wants_overview existed, under the old key format
    cache.put("api_understand", cache.make_key(llm._chat_model(), system, prompt), {"node_ids": ["TRN-031"]})
    calls = []
    monkeypatch.setattr(llm, "client", fake_client(NewSchema(node_ids=["TRN-031"], wants_overview=True), calls))

    r = llm.generate_json(prompt, system, NewSchema, "api_understand")

    assert calls, "a schema change must not be answered from the old cache"
    assert r.wants_overview is True


def test_same_schema_is_still_cached(tmp_cache, monkeypatch):
    calls = []
    monkeypatch.setattr(llm, "client", fake_client(NewSchema(node_ids=["TRN-031"], wants_overview=True), calls))
    llm.generate_json("p", "s", NewSchema, "api_understand")
    llm.generate_json("p", "s", NewSchema, "api_understand")
    assert len(calls) == 1


# ---------- Bug 2: one answer format for every question type ----------
def captured_system(monkeypatch, u):
    seen = {}

    def fake_stream(prompt, system, namespace="api_answer"):
        seen["system"], seen["prompt"] = system, prompt
        yield "ok"

    monkeypatch.setattr(answer, "stream_text", fake_stream)
    list(answer.stream_answer("q", [], u, KnowledgeResult(cards=[bounce_card()])))
    return seen["system"]


def test_overview_instructions_do_not_ask_for_one_likely_cause(monkeypatch):
    system = captured_system(monkeypatch, Understood(node_ids=["TRN-031"], wants_overview=True))
    low = system.lower()
    assert "likely cause" not in low
    assert "steps to take, numbered" not in low
    assert "one line per tip" in low


def test_problem_instructions_keep_the_troubleshooting_format(monkeypatch):
    system = captured_system(monkeypatch, Understood(node_ids=["TRN-031"]))
    assert "likely cause" in system.lower()
    assert "one line per tip" not in system.lower()


def test_history_instructions_ask_for_current_value_first(monkeypatch):
    system = captured_system(monkeypatch, Understood(node_ids=["TRN-042"], wants_history=True))
    assert "current value first" in system.lower()
    assert "likely cause" not in system.lower()


# ---------- Bug 4: firmware notes sent to Gemini as "doesn't apply" in both directions ----------
def test_below_fixed_firmware_note_says_upgrade_fixes_it():
    c = bounce_card(knowledge_type="troubleshooting_rule",
                    scope_note="Not yet on TRN-031: only applies from firmware 3.4 upward, device has 3.3.0")
    out = cards.compact_for_llm(c)
    assert "not_applicable_because" not in out
    assert out["upgrade_fixes_this"].startswith("Not yet on TRN-031")


def test_already_fixed_firmware_note_says_not_needed():
    c = bounce_card(status="outdated",
                    scope_note="Not needed on TRN-077: only applies below firmware 3.4, device has 3.4.0")
    out = cards.compact_for_llm(c)
    assert "not_applicable_because" not in out
    assert out["not_needed_on_this_device"].startswith("Not needed on TRN-077")


def test_answer_rules_explain_both_firmware_notes(monkeypatch):
    system = captured_system(monkeypatch, Understood(node_ids=["TRN-031"]))
    assert "upgrade_fixes_this" in system and "not_needed_on_this_device" in system
    assert "not_applicable_because" not in system


# ---------- Bug 3: wrong source / device counts ----------
def test_tip_carries_exact_counts():
    out = cards.compact_for_llm(bounce_card())
    assert out["source_count"] == 4
    assert out["device_count"] == 3
    assert out["authors"] == ["Erkki Expert"]


def test_answer_rules_contain_no_numeric_example_to_copy(monkeypatch):
    for u in (Understood(node_ids=["X"]), Understood(node_ids=["X"], wants_overview=True)):
        system = captured_system(monkeypatch, u)
        assert "3 devices by 2 sources" not in system
        assert "source_count" in system


# ---------- Bug 6: no overview/history detection when Gemini is down ----------
@pytest.fixture
def gemini_down(monkeypatch):
    with open(BACKEND / "data" / "inventory" / "nodes.csv", encoding="utf-8") as f:
        devices = [dict(r, aliases=[]) for r in csv.DictReader(f)]
    ctx = {"at": 1e18, "devices": devices, "terms": {"symptom": {}, "event": {}},
           "inventory": linking.Inventory(devices, {})}
    monkeypatch.setattr(understand, "_context", lambda: ctx)

    def down(*a, **k):
        raise RuntimeError("Gemini unavailable")

    monkeypatch.setattr(understand, "generate_json", down)


@pytest.mark.parametrize("msg", [
    "what are possible faults related to TRN-031",
    "list all known issues on BTS-210",
    "What do we know about TRN-042?",
    "mitä vikoja TRN-031:ssä on tiedossa",
    "kaikki tunnetut ongelmat MW-405",
])
def test_fallback_detects_overview(gemini_down, msg):
    u = understand.understand(msg, None, [], [])
    assert u.by == "fallback" and u.wants_overview is True


@pytest.mark.parametrize("msg", [
    "what were the older gate codes for TRN-042",
    "what was the code before?",
    "TRN-042 vanhat koodit",
])
def test_fallback_detects_history(gemini_down, msg):
    u = understand.understand(msg, None, [], [])
    assert u.wants_history is True


@pytest.mark.parametrize("msg", [
    "TRN-031 SFP replaced, link up but no traffic",
    "CRC errors on the older units after maintenance",
    "How do I get to the TRN-042 site near Kolari?",
    "TRN-031 link down, is this a known issue?",
    "possible fault on the uplink after SFP swap",
])
def test_fallback_keeps_normal_questions_normal(gemini_down, msg):
    u = understand.understand(msg, None, [], [])
    assert u.wants_overview is False and u.wants_history is False


# ---------- Cards carry their symptom/event codes (device-specific example questions in the UI) ----------
def test_cards_keep_symptom_and_event_codes():
    from api import knowledge
    from api.models import KnowledgeCard
    infos = {"T001-1": {"a": {"knowledge_type": "troubleshooting_rule", "summary": "s", "actions": ["BOUNCE_INTERFACE"],
                              "avoid": [], "symptoms": ["TRAFFIC_COUNTERS_ZERO", "INTERFACE_UP"],
                              "events": ["SFP_REPLACEMENT"], "outcome": "worked", "confidence": 0.7,
                              "status": "auto_captured", "scope_node_type": "transmission",
                              "valid_from": "2025-03-12T09:25:00+02:00", "valid_to": None},
                        "sources": [], "author": "Erkki Expert", "conflicts": [], "devices": ["TRN-042"]}}
    group = knowledge.group_assertions(["T001-1"], infos)[0]
    card = knowledge._clean(knowledge.build_card(group, infos))
    assert card["symptoms"] == ["INTERFACE_UP", "TRAFFIC_COUNTERS_ZERO"]
    assert card["events"] == ["SFP_REPLACEMENT"]
    dumped = KnowledgeCard.model_validate(card).model_dump()       # what /api/nodes/{id} and JSON chat return
    assert dumped["symptoms"] and dumped["events"] == ["SFP_REPLACEMENT"]
