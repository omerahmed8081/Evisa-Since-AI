"""
Step A · UNDERSTAND (one Gemini call, structured output).

  "At TRN-077, swapped the SFP, link is up but no traffic"
    -> {node_ids: [TRN-077], symptoms: [INTERFACE_UP, TRAFFIC_COUNTERS_ZERO], events: [SFP_REPLACEMENT]}

Gemini sees the SAME vocabulary as the stored tips (the (:Term) nodes in Neo4j), so the question and
the knowledge speak the same language. Code then double-checks everything: device IDs must exist in the
inventory, terms must exist in the vocabulary (aliases are mapped), and IDs written in the message are
always picked up by regex even if Gemini is down.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, Field

from pipeline import graph
from pipeline import threads
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
    language: str = "en"
    by: str = "gemini"  # gemini | fallback


# ---------- inventory + vocabulary, cached for a minute ----------
_cache: dict = {"at": 0.0}


def _context() -> dict:
    if time.time() - _cache["at"] > 60:
        devices = [dict(r) for r in graph.run(
            "MATCH (d:Device) RETURN d.node_id AS node_id, d.node_type AS node_type, "
            "toString(d.install_date) AS install_date, d.firmware AS firmware, d.location AS location "
            "ORDER BY d.node_id")]
        terms: dict[str, dict[str, str]] = {"symptom": {}, "event": {}}
        for r in graph.run("MATCH (t:Term) WHERE t.category IN ['symptom', 'event'] "
                           "RETURN t.category AS cat, t.name AS name, t.aliases AS aliases"):
            terms[r["cat"]][r["name"]] = r["name"]
            for alias in r["aliases"] or []:
                terms[r["cat"]].setdefault(alias, r["name"])
        _cache.update(at=time.time(), devices=devices, terms=terms)
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

    written = sorted({m.group(0).upper() for m in threads.DEVICE_ID_RE.finditer(message.upper())})
    u = Understood(unknown_nodes=[x for x in written if x not in known_ids])
    nodes = [x for x in written if x in known_ids]
    if selected_node and selected_node.upper() in known_ids:
        nodes.insert(0, selected_node.upper())

    follow_up = False
    try:
        r = generate_json(_prompt(message, history, ctx, selected_node), SYSTEM, Understanding, "api_understand")
        nodes += [n.upper() for n in r.node_ids if n.upper() in known_ids]
        u.node_type = r.node_type
        u.symptoms = _normalise_terms(r.symptoms, ctx["terms"]["symptom"])
        u.events = _normalise_terms(r.events, ctx["terms"]["event"])
        u.wants_access_info = r.wants_access_info
        u.language = r.language
        follow_up = r.is_follow_up
    except Exception as e:
        log.warning("Step A fell back to regex only: %s", e)
        u.by = "fallback"
        low = message.lower()
        u.wants_access_info = any(w in low for w in ("gate", "code", "access", "key", "lock", "portti", "koodi", "avain"))

    u.node_ids = list(dict.fromkeys(nodes))
    if not u.node_ids and previous_nodes and (follow_up or u.by == "fallback") and not u.unknown_nodes:
        u.node_ids = list(previous_nodes)
    if not u.node_type and u.node_ids:
        u.node_type = types_by_id.get(u.node_ids[0])
    return u
