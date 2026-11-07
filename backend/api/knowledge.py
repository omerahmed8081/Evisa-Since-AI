"""
Step B · RETRIEVE (Neo4j only, no Gemini).

  - device(s) known  -> retrieve.find_knowledge() for each device (scope, validity, firmware filter,
                        duplicate merging, symptom ranking: all from the existing pipeline code)
  - no device        -> symptom/event search over all valid knowledge (optionally one device type)

Then every result is enriched into a KnowledgeCard: authors and excerpts per source, plain-English
scope, status, the conflicting tip ("Experts disagree"), failed attempts attached to the fix they
relate to, and firmware-excluded knowledge as an "outdated" card with a scope_note.
"""
from dataclasses import dataclass, field

from pipeline import graph
from pipeline import retrieve
from api import cards as C
from api.config import MAX_CARDS, MAX_OUTDATED_CARDS

ENRICH_QUERY = """
MATCH (a:Assertion) WHERE a.id IN $ids
OPTIONAL MATCH (a)-[:FROM]->(s:Source)
OPTIONAL MATCH (a)-[:BY]->(p:Person)
OPTIONAL MATCH (a)-[:CONFLICTS_WITH]-(c:Assertion)
OPTIONAL MATCH (a)-[:OBSERVED_ON]->(d:Device)
RETURN a.id AS id,
       a {.knowledge_type, .summary, .actions, .avoid, .symptoms, .events, .outcome, .details,
          .confidence, .status, .scope_node_type, .scope_firmware_below, .scope_firmware_at_least,
          scope_installed_before: toString(a.scope_installed_before),
          valid_from: toString(a.valid_from), valid_to: toString(a.valid_to)} AS a,
       collect(DISTINCT s {.id, .channel, .text, timestamp: toString(s.timestamp)}) AS sources,
       head(collect(DISTINCT p.name)) AS author,
       collect(DISTINCT c.id) AS conflicts,
       collect(DISTINCT d.node_id) AS devices
"""

SEARCH_QUERY = """
MATCH (a:Assertion)
WHERE a.valid_to IS NULL
  AND ($node_type IS NULL OR a.scope_node_type = $node_type
       OR EXISTS { (a)-[:OBSERVED_ON]->(:Device {node_type: $node_type}) })
  AND ( any(x IN coalesce(a.symptoms, []) WHERE x IN $symptoms)
        OR any(x IN coalesce(a.events, []) WHERE x IN $events)
        OR ($access AND a.knowledge_type = 'access_info') )
RETURN a.id AS id
"""


@dataclass
class KnowledgeResult:
    cards: list[dict] = field(default_factory=list)
    devices: list[dict] = field(default_factory=list)   # facts of the resolved devices
    mode: str = "none"                                   # device | search | none
    notes: list[str] = field(default_factory=list)       # e.g. "symptom filter relaxed"


# ---------- database access ----------
def fetch_assertions(ids) -> dict[str, dict]:
    ids = sorted(set(ids))
    if not ids:
        return {}
    out = {}
    for r in graph.run(ENRICH_QUERY, ids=ids):
        out[r["id"]] = {"a": dict(r["a"]), "sources": [dict(s) for s in r["sources"] if s.get("id")],
                        "author": r["author"], "conflicts": list(r["conflicts"]), "devices": list(r["devices"])}
    return out


# ---------- grouping (used when we don't go through retrieve.find_knowledge) ----------
def _as_retrieve_shape(aid: str, info: dict) -> dict:
    a = info["a"]
    return {"id": aid, "knowledge_type": a["knowledge_type"], "actions": a.get("actions") or [],
            "scope_node_type": a.get("scope_node_type"), "outcome": a.get("outcome")}


def group_assertions(ids, infos: dict, symptoms: list[str] | None = None, how: str | None = None) -> list[dict]:
    """Merge duplicates (same rule as retrieve.same_knowledge) into result dicts shaped like retrieve's."""
    groups: list[list[str]] = []
    for aid in ids:
        if aid not in infos:
            continue
        me = _as_retrieve_shape(aid, infos[aid])
        for g in groups:
            if any(retrieve.same_knowledge(me, _as_retrieve_shape(o, infos[o])) for o in g):
                g.append(aid)
                break
        else:
            groups.append([aid])

    wanted = set(symptoms or [])
    results = []
    for g in groups:
        members = [infos[i]["a"] for i in g]
        newest = max(members, key=lambda a: a.get("valid_from") or "")
        sources = {s["id"] for i in g for s in infos[i]["sources"]}
        base = max((a.get("confidence") or 0) for a in members)
        failed = all(a.get("outcome") == "failed" for a in members)
        sym = set().union(*[set(a.get("symptoms") or []) for a in members])
        results.append({
            "knowledge_ids": g,
            "knowledge_type": newest["knowledge_type"],
            "summary": newest["summary"],
            "outcome": "failed" if failed else ("worked" if any(a.get("outcome") == "worked" for a in members) else "unknown"),
            "actions": max((a.get("actions") or [] for a in members), key=len),
            "avoid": sorted(set().union(*[set(a.get("avoid") or []) for a in members])),
            "symptoms": sorted(sym),
            "details": [a["details"] for a in members if a.get("details")],
            "confidence": round(base if failed else min(retrieve.MAX_CONFIDENCE,
                                base + retrieve.CONFIRMATION_BONUS * max(0, len(sources) - 1)), 2),
            "symptom_match": round(len(wanted & sym) / len(wanted), 2) if wanted else None,
            "how_it_applies": how,
            "seen_on_devices": sorted({d for i in g for d in infos[i]["devices"]}),
        })
    results.sort(key=lambda r: (r["outcome"] == "failed", -(r["symptom_match"] or 0), -r["confidence"]))
    return results


# ---------- card building ----------
def build_card(group: dict, infos: dict, scope_note: str | None = None, force_status: str | None = None) -> dict:
    ids = group["knowledge_ids"]
    members = [infos[i] for i in ids if i in infos]
    a0 = members[0]["a"] if members else {}

    sources = {}
    for m in members:
        for s in m["sources"]:
            sources.setdefault(s["id"], {
                "thread_id": s["id"],
                "channel": s.get("channel") or "teams",
                "author": m["author"],
                "timestamp": s.get("timestamp"),
                "excerpt": C.excerpt(s["id"], m["author"], s.get("text")),
            })
    valid_froms = [m["a"].get("valid_from") for m in members if m["a"].get("valid_from")]
    valid_tos = [m["a"].get("valid_to") for m in members]
    valid_to = None if (not valid_tos or any(v is None for v in valid_tos)) else max(valid_tos)
    statuses = {m["a"].get("status") or "auto_captured" for m in members}
    if group.get("disputed"):
        statuses.add("disputed")
    # firmware limits: take them from the member that has them (merged members share type and actions)
    lim = next((m["a"] for m in members if m["a"].get("scope_firmware_below") or m["a"].get("scope_firmware_at_least")), a0)
    scope = {
        "node_type": a0.get("scope_node_type"),
        "installed_before": (a0.get("scope_installed_before") or None),
        "firmware_below": lim.get("scope_firmware_below"),
        "firmware_at_least": lim.get("scope_firmware_at_least"),
    }
    observed = group.get("seen_on_devices") or sorted({d for m in members for d in m["devices"]})
    details = group.get("details") or []
    if isinstance(details, str):
        details = [details]
    actions = list(group.get("actions") or [])
    avoid = list(group.get("avoid") or [])
    return {
        "assertion_id": ids[0],
        "knowledge_ids": list(ids),
        "knowledge_type": group["knowledge_type"],
        "summary": group["summary"],
        "actions": actions,
        "actions_text": [C.action_text(x) for x in actions],
        "avoid": avoid,
        "avoid_text": [C.avoid_text(x) for x in avoid],
        "outcome": group.get("outcome") or "unknown",
        "status": force_status or C.card_status(statuses, group.get("outcome"), valid_to),
        "confidence": group.get("confidence") or 0.0,
        "symptom_match": group.get("symptom_match"),
        "how_it_applies": group.get("how_it_applies"),
        "symptoms": list(group.get("symptoms") or []),
        "scope": scope,
        "scope_text": C.scope_text(scope, observed),
        "scope_note": scope_note,
        "observed_on": observed,
        "valid_from": min(valid_froms) if valid_froms else None,
        "valid_to": valid_to,
        "details": "\n".join(dict.fromkeys(details)) or None,
        "sources": sorted(sources.values(), key=lambda s: s.get("timestamp") or ""),
        "conflicts_with": [],
        "related_failed": [],
        "_conflict_ids": sorted({c for m in members for c in m["conflicts"]} - set(ids)),
    }


def _failed_ref(card: dict) -> dict:
    return {"assertion_id": card["assertion_id"], "knowledge_ids": card["knowledge_ids"],
            "summary": card["summary"], "actions_text": card["actions_text"], "sources": card["sources"],
            "observed_on": card["observed_on"]}


def _attach_failed(main: list[dict], failed: list[dict]) -> list[dict]:
    """Put each failed attempt under the fix it relates to; returns failed cards that fit nowhere."""
    leftover = []
    for f in failed:
        best, best_score = None, 0
        for c in main:
            if c["knowledge_type"] == "access_info":
                continue
            score = 2 * len(set(f["actions"]) & set(c["avoid"])) + len(set(f["symptoms"]) & set(c["symptoms"]))
            if c["scope"]["node_type"] and f["scope"]["node_type"] and c["scope"]["node_type"] != f["scope"]["node_type"]:
                score = 0
            if score > best_score:
                best, best_score = c, score
        if best is not None and best_score >= 2:
            best["related_failed"].append(_failed_ref(f))
        else:
            leftover.append(f)
    return leftover


def _attach_conflicts(cards: list[dict], infos: dict) -> list[dict]:
    """'Experts disagree': nest the conflicting tip inside the first card; drop it from the top level."""
    missing = {cid for c in cards for cid in c["_conflict_ids"]} - set(infos)
    infos.update(fetch_assertions(missing))
    by_id = {kid: c for c in cards for kid in c["knowledge_ids"]}
    nested: set[int] = set()
    for c in cards:
        if id(c) in nested:
            continue
        for cid in c["_conflict_ids"]:
            other = by_id.get(cid)
            if other is not None and other is not c and id(other) not in nested:
                nested.add(id(other))
                c["conflicts_with"].append(other)
            elif other is None and cid in infos:
                g = group_assertions([cid], infos, how="conflicting expert opinion")[0]
                c["conflicts_with"].append(build_card(g, infos))
        if c["conflicts_with"]:
            c["status"] = "disputed"
    return [c for c in cards if id(c) not in nested]


def _clean(card: dict) -> dict:
    card.pop("_conflict_ids", None)
    card.pop("symptoms", None)
    for c in card["conflicts_with"]:
        _clean(c)
    return card


def finish_cards(groups: list[dict], infos: dict, wants_access: bool, outdated: list[dict],
                 has_symptoms: bool = False, max_cards: int = MAX_CARDS) -> list[dict]:
    built = [build_card(g, infos) for g in groups]
    main = [c for c in built if c["outcome"] != "failed"]
    failed = [c for c in built if c["outcome"] == "failed"]
    leftover_failed = _attach_failed(main, failed)
    if wants_access:
        access = [c for c in main if c["knowledge_type"] == "access_info"]
        main = access or main
        outdated = []
    elif has_symptoms:  # a troubleshooting question: gate codes etc. are noise here
        main = [c for c in main if c["knowledge_type"] != "access_info"] or main
    cards = _attach_conflicts(main[:max_cards], infos)
    cards += leftover_failed[: max(0, max_cards - len(cards))]
    cards += outdated[:MAX_OUTDATED_CARDS]
    return [_clean(c) for c in cards]


# ---------- public entry points ----------
def for_devices(node_ids: list[str], symptoms: list[str], events: list[str], wants_access: bool,
                panel: bool = False) -> KnowledgeResult:
    res = KnowledgeResult(mode="device")
    groups, seen = [], set()
    excluded: list[tuple[str, dict, dict]] = []  # (node_id, excluded entry, device)
    for nid in node_ids:
        out = retrieve.find_knowledge(nid, symptoms or None, events or None)
        if (symptoms or events) and not out["results"] and isinstance(out.get("device"), dict):
            out = retrieve.find_knowledge(nid, None)
            res.notes.append(f"No tip for {nid} matched the symptoms exactly; showing everything that applies to it.")
        dev = out.get("device")
        if isinstance(dev, dict):
            res.devices.append(dev)
        elif dev is None:
            res.notes.append(f"{nid} is not in the inventory.")
        for r in out["results"]:
            key = frozenset(r["knowledge_ids"])
            if key not in seen:
                seen.add(key)
                groups.append(r)
        for e in out.get("excluded_by_firmware", []):
            excluded.append((nid, e, dev))

    infos = fetch_assertions([i for g in groups for i in g["knowledge_ids"]] + [e["id"] for _, e, _ in excluded])
    # Firmware-hidden knowledge is only worth showing for a concrete problem (or in the device panel)
    outdated = _outdated_cards(excluded, infos, symptoms, events) if (symptoms or events or panel) else []
    res.cards = finish_cards(groups, infos, wants_access, outdated, has_symptoms=bool(symptoms or events),
                             max_cards=20 if panel else MAX_CARDS)
    return res


def _outdated_cards(excluded, infos: dict, symptoms: list[str], events: list[str]) -> list[dict]:
    """Knowledge hidden by the firmware filter, as 'outdated' cards that explain why."""
    wanted = set(symptoms) | set(events)
    by_node: dict[str, list[str]] = {}
    reasons: dict[str, str] = {}
    for nid, e, _ in excluded:
        a = infos.get(e["id"], {}).get("a")
        if not a or a.get("outcome") == "failed":
            continue
        if wanted and not (wanted & (set(a.get("symptoms") or []) | set(a.get("events") or []))):
            continue
        by_node.setdefault(nid, []).append(e["id"])
        reasons[e["id"]] = e["reason"]
    cards = []
    for nid, ids in by_node.items():
        for g in group_assertions(ids, infos, how=f"hidden for {nid} by the firmware rule"):
            reason = reasons[g["knowledge_ids"][0]]
            if reason.startswith("only applies below"):   # e.g. workaround no longer needed after an upgrade
                cards.append(build_card(g, infos, scope_note=f"Not needed on {nid}: {reason}", force_status="outdated"))
            else:                                          # e.g. "fixed from 3.4": tells you an upgrade helps
                cards.append(build_card(g, infos, scope_note=f"Not yet on {nid}: {reason}"))
    return cards


def search(symptoms: list[str], events: list[str], node_type: str | None, wants_access: bool) -> KnowledgeResult:
    res = KnowledgeResult(mode="search")
    if not symptoms and not events and not wants_access:
        res.mode = "none"
        return res
    ids = [r["id"] for r in graph.run(SEARCH_QUERY, symptoms=symptoms, events=events,
                                     node_type=node_type, access=wants_access)]
    infos = fetch_assertions(ids)
    how = "matched by symptoms" + (f" on {C.NODE_TYPE_TEXT.get(node_type, node_type).lower()}" if node_type else "")
    groups = group_assertions(ids, infos, symptoms or None, how=how)
    res.cards = finish_cards(groups, infos, wants_access, [], has_symptoms=bool(symptoms or events))
    res.notes.append("No device was named, so these tips were found by symptom and may not all apply to your device.")
    return res


def device_cards(node_id: str) -> list[dict]:
    """All knowledge that applies to one device (device side panel)."""
    return for_devices([node_id], [], [], False, panel=True).cards
