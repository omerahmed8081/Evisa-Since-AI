"""Step A of the chat: parse the question with Gemini (structured output).

Returns devices, symptoms/events (mapped onto the graph vocabulary), language and question type.
Devices are resolved in code: written ID / nickname / place first, then the UI selection."""
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, Field

from pipeline import graph
from pipeline import linking
from api.llm import generate_json
from pipeline.schema import NodeType
from pipeline.vocabulary import clean_term

log = logging.getLogger("api.understand")


class Understanding(BaseModel):
    node_ids: list[str] = Field(description="Device IDs from the inventory the user is asking about. Resolve indirect references (a place name, 'the same node', a previous turn) only if they point to exactly the devices listed. Empty if unclear.")
    node_type: Optional[NodeType] = Field(description="Device type the question is about, if it can be told (e.g. 'old transmission boxes' -> transmission). Else null.")
    symptoms: list[str] = Field(description="Symptom terms from the vocabulary that the user describes. Only use listed terms.")
    events: list[str] = Field(description="Event terms from the vocabulary: what happened before the problem. Only use listed terms.")
    wants_access_info: bool = Field(description="True if the user asks how to get to / into a site (gate, code, key, road, lockbox).")
    is_follow_up: bool = Field(description="True if the message continues the previous turn about the same device (e.g. 'what if that doesn't work?').")
    wants_overview: bool = Field(default=False, description="True if the user wants EVERYTHING known about a device rather than help with one problem (e.g. 'all possible faults on BTS-210', 'what do we know about TRN-042', 'list the known issues').")
    wants_history: bool = Field(default=False, description="True if the user asks about the PAST: older or previous values, what changed, what it used to be (e.g. 'older gate codes', 'what was the code before'). NOT for 'older units' / 'old devices', which is about device age.")
    language: Literal["en", "fi", "other"] = Field(description="Language of the user's message.")


SYSTEM = """You turn a field engineer's or NOC operator's chat message about a telecom network into
structured search terms. Messages may be in English, Finnish or a mix, informal, with typos.
Use ONLY device IDs from the inventory and ONLY terms from the vocabulary. Do not guess: if a symptom
is not described, leave it out. Return nothing beyond the requested fields."""


@dataclass
class Understood:
    node_ids: list[str] = field(default_factory=list)
    unknown_nodes: list[str] = field(default_factory=list)
    node_type: str | None = None
    symptoms: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    wants_access_info: bool = False
    wants_overview: bool = False
    wants_history: bool = False
    language: str = "en"
    by: str = "gemini"
    resolved_by: str | None = None
    resolution_note: str | None = None
    ignored_selection: str | None = None


OVERVIEW_RE = re.compile(
    r"\b(all|every|possible|known|common|typical)\s+(\w+\s+)?(faults|issues|problems|failures|tips)\b"
    r"|\bwhat\s+(do\s+we|does\s+\w+)\s+know\b|\blist\b.*\b(faults?|issues?|problems?|tips?)\b"
    r"|\boverview\b|\bmit(ä|a)\s+(vikoja|ongelmia|tiedet(ää|aan))\b"
    r"|\b(kaikki|tunnetut|mahdolliset)\s+(\w+\s+)?(viat|vikoja|ongelmat|ongelmia)\b",
    re.IGNORECASE)
HISTORY_RE = re.compile(
    r"\b(older|previous|old|earlier|former)\s+(gate\s+|lockbox\s+|access\s+)?(codes?|values?|keys?|passwords?)\b"
    r"|\bwhat\s+was\b.*\bbefore\b|\bused\s+to\s+be\b|\bwhat\s+changed\b"
    r"|\b(vanha|vanhat|vanhoja|aiempi|aiemmat|edellinen|edelliset)\s+(\w+\s+)?(koodi|koodit|koodeja|arvot)\b",
    re.IGNORECASE)


def keyword_intent(message: str) -> tuple[bool, bool]:
    """(wants_overview, wants_history) from keywords; used only when Gemini is down."""
    return bool(OVERVIEW_RE.search(message)), bool(HISTORY_RE.search(message))


_cache: dict = {"at": 0.0}


def _context() -> dict:
    if time.time() - _cache["at"] > 60:
        devices = [dict(r) for r in graph.run(
            "MATCH (d:Device) RETURN d.node_id AS node_id, d.node_type AS node_type, "
            "toString(d.install_date) AS install_date, d.firmware AS firmware, d.location AS location, "
            "coalesce(d.aliases, []) AS aliases ORDER BY d.node_id")]
        terms: dict[str, dict[str, str]] = {"symptom": {}, "event": {}}
        for r in graph.run("MATCH (t:Term) WHERE t.category IN ['symptom', 'event'] "
                           "RETURN t.category AS cat, t.name AS name, t.aliases AS aliases"):
            terms[r["cat"]][r["name"]] = r["name"]
            for alias in r["aliases"] or []:
                terms[r["cat"]].setdefault(alias, r["name"])
        inventory = linking.Inventory(devices, {a: d["node_id"] for d in devices for a in d.get("aliases") or []})
        _cache.update(at=time.time(), devices=devices, terms=terms, inventory=inventory)
    return _cache


def _normalise_terms(raw: list[str], known: dict[str, str]) -> list[str]:
    out = []
    for t in raw:
        name = known.get(clean_term(t))
        if name and name not in out:
            out.append(name)
    return out


def _prompt(message: str, history: list[tuple[str, str]], ctx: dict, selected: str | None) -> str:
    inv = "\n".join(f"{d['node_id']}: {d['node_type']}, installed {d['install_date']}, firmware {d['firmware']}, "
                    f"location {d['location']}" for d in ctx["devices"])
    vocab = "\n".join(f"{cat}: {', '.join(sorted({v for v in names.values()}))}" for cat, names in ctx["terms"].items())
    hist = "\n".join(f"{role}: {text[:400]}" for role, text in history) or "(none)"
    sel = f"\nDevice selected in the UI: {selected}" if selected else ""
    return (f"INVENTORY\n{inv}\n\nVOCABULARY\n{vocab}\n\nPREVIOUS TURNS\n{hist}{sel}\n\n"
            f"MESSAGE\n{message}")


def understand(message: str, selected_node: str | None, history: list[tuple[str, str]],
               previous_nodes: list[str]) -> Understood:
    ctx = _context()
    known_ids = {d["node_id"] for d in ctx["devices"]}
    types_by_id = {d["node_id"]: d["node_type"] for d in ctx["devices"]}

    inv: linking.Inventory = ctx["inventory"]
    match = inv.resolve(message)
    written = sorted(match.ids | match.unknown_ids)
    u = Understood(unknown_nodes=sorted(match.unknown_ids))
    named = sorted(match.ids) + sorted(set(match.aliases) - match.ids)
    selected = selected_node.upper() if selected_node and selected_node.upper() in known_ids else None
    message_names_device = bool(named or written or match.locations)

    follow_up = False
    gemini_nodes: list[str] = []
    try:
        r = generate_json(_prompt(message, history, ctx, None if message_names_device else selected),
                          SYSTEM, Understanding, "api_understand")
        gemini_nodes = [n.upper() for n in r.node_ids if n.upper() in known_ids]
        u.node_type = r.node_type
        u.symptoms = _normalise_terms(r.symptoms, ctx["terms"]["symptom"])
        u.events = _normalise_terms(r.events, ctx["terms"]["event"])
        u.wants_access_info = r.wants_access_info
        u.wants_overview = r.wants_overview
        u.wants_history = r.wants_history
        u.language = r.language
        follow_up = r.is_follow_up
    except Exception as e:
        log.warning("Step A fell back to regex only: %s", e)
        u.by = "fallback"
        low = message.lower()
        u.wants_access_info = any(w in low for w in ("gate", "code", "access", "key", "lock", "portti", "koodi", "avain"))
        u.wants_overview, u.wants_history = keyword_intent(message)

    nodes: list[str] = []
    if named:
        nodes = named
        u.resolved_by = "id" if match.ids else "alias"
        if match.aliases:
            u.resolution_note = "; ".join(f"'{a}' is the nickname of {n}" for n, a in match.aliases.items())
    elif written:
        pass
    elif match.locations:
        types = {u.node_type} if u.node_type else match.type_hints
        cands = inv.candidates(match.locations, types or None) or inv.candidates(match.locations)
        if cands:
            nodes = [d["node_id"] for d in cands]
            listed = ", ".join(f"{d['node_id']} ({d['node_type'].replace('_', ' ')})" for d in cands)
            if len(cands) == 1:
                u.resolved_by = "location"
                u.resolution_note = (f"No device ID was given; {cands[0]['node_id']} is the only matching device "
                                     f"in {cands[0]['location']}.")
            else:
                u.resolved_by = "site"
                u.resolution_note = (f"No device ID was given; {', '.join(match.locations)} has several matching "
                                     f"devices: {listed}. " + (
                                         "Site access information applies to the whole site." if u.wants_access_info
                                         else "Say which device each tip is for and ask which one the user means."))
    elif selected:
        nodes = [selected]
        u.resolved_by = "selected"
    elif gemini_nodes:
        nodes = gemini_nodes
        u.resolved_by = "gemini"
    if selected and message_names_device and selected not in nodes:
        u.ignored_selection = selected

    u.node_ids = list(dict.fromkeys(nodes))
    if not u.node_ids and previous_nodes and (follow_up or u.by == "fallback") and not u.unknown_nodes:
        u.node_ids = list(previous_nodes)
    if not u.node_type and u.node_ids:
        u.node_type = types_by_id.get(u.node_ids[0])
    return u
