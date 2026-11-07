"""Retrieval: what applies to a device.

Direct observations, site-level tips and scope rules; only currently valid knowledge, firmware
filter, duplicate merging, symptom ranking and confidence. No LLM calls.

    python scripts/retrieve.py TRN-077"""
import math


from pipeline import graph


QUERY = """
MATCH (d:Device {node_id: $node_id})
MATCH (a:Assertion)
WHERE a.valid_to IS NULL
  AND ( EXISTS { (a)-[:OBSERVED_ON]->(d) }
        OR EXISTS { (a)-[:OBSERVED_AT]->(:Site)<-[:AT]-(d) }
        OR ( a.scope_node_type IS NOT NULL
             AND a.scope_node_type = d.node_type
             AND (a.scope_installed_before IS NULL OR d.install_date < a.scope_installed_before) ) )
OPTIONAL MATCH (a)-[:FROM]->(s:Source)
OPTIONAL MATCH (a)-[:BY]->(p:Person)
OPTIONAL MATCH (a)-[:OBSERVED_ON]->(od:Device)
RETURN d {.node_id, .node_type, .firmware, install_date: toString(d.install_date)} AS device,
       a {.id, .knowledge_type, .summary, .events, .symptoms, .actions, .avoid, .outcome,
          .details, .confidence, .status, .scope_node_type, .scope_firmware_below,
          .scope_firmware_at_least,
          scope_installed_before: toString(a.scope_installed_before),
          valid_from: toString(a.valid_from)} AS a,
       EXISTS { (a)-[:OBSERVED_ON]->(d) } AS direct,
       head([(a)-[ob:OBSERVED_ON]->(d) | {linked_by: coalesce(ob.linked_by, 'id'),
             link_confidence: coalesce(ob.link_confidence, 1.0), via: ob.via}]) AS link,
       head([(a)-[oa:OBSERVED_AT]->(st:Site)<-[:AT]-(d) | {site: st.name,
             link_confidence: coalesce(oa.link_confidence, 0.5), candidates: oa.candidates}]) AS site_link,
       ( a.scope_node_type IS NOT NULL AND a.scope_node_type = d.node_type
         AND (a.scope_installed_before IS NULL OR d.install_date < a.scope_installed_before) ) AS by_scope,
       collect(DISTINCT s {.id, .channel, timestamp: toString(s.timestamp)}) AS sources,
       collect(DISTINCT p.name) AS authors,
       collect(DISTINCT od.node_id) AS devices
"""

CONFIRMATION_BONUS = 0.1
MAX_CONFIDENCE = 0.95

RELATED_TERM_THRESHOLD = 0.825
RELATED_TERM_CREDIT = 0.5
OPPOSITES = [{"UP", "DOWN"}, {"NORMAL", "LOW"}, {"NORMAL", "HIGH"}, {"LOW", "HIGH"}, {"ZERO", "NORMAL"}]
_term_vectors: dict[tuple[str, str], list[float] | None] = {}


def _vectors(category: str, names: set[str]) -> dict[str, list[float] | None]:
    missing = [n for n in names if (category, n) not in _term_vectors]
    if missing:
        for r in graph.run("MATCH (t:Term) WHERE t.category = $cat AND t.name IN $names "
                           "RETURN t.name AS name, t.embedding AS emb", cat=category, names=missing):
            _term_vectors[(category, r["name"])] = r["emb"]
        for n in missing:
            _term_vectors.setdefault((category, n), None)
    return {n: _term_vectors[(category, n)] for n in names}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _opposites(a: str, b: str) -> bool:
    ta, tb = set(a.split("_")), set(b.split("_"))
    return any((pair & ta) and (pair & tb) and (pair & ta) != (pair & tb) for pair in OPPOSITES)


def _term_credit(wanted: str, have: set[str], category: str) -> float:
    if wanted in have:
        return 1.0
    candidates = [h for h in have if not _opposites(wanted, h)]
    if not candidates:
        return 0.0
    vecs = _vectors(category, set(candidates) | {wanted})
    w = vecs.get(wanted)
    if not w:
        return 0.0
    best = max((_cosine(w, vecs[h]) for h in candidates if vecs.get(h)), default=0.0)
    return RELATED_TERM_CREDIT if best >= RELATED_TERM_THRESHOLD else 0.0


def match_score(symptoms: set[str], events: set[str], tip_symptoms: set[str], tip_events: set[str]):
    """0..1 how well a tip matches the question's terms. None = nothing to compare
    (no terms in the question, or a tip without any symptom/event terms)."""
    wanted = [(s, "symptom", tip_symptoms) for s in symptoms] + [(e, "event", tip_events) for e in events]
    if not wanted or not (tip_symptoms or tip_events):
        return None
    return sum(_term_credit(t, have, cat) for t, cat, have in wanted) / len(wanted)


def version_tuple(v: str | None) -> tuple:
    parts = []
    for p in (v or "").split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts)


def compare_versions(a: str, b: str) -> int:
    """-1 if a < b, 0 if equal, 1 if a > b ('3.4' == '3.4.0')."""
    x, y = version_tuple(a), version_tuple(b)
    n = max(len(x), len(y))
    x, y = x + (0,) * (n - len(x)), y + (0,) * (n - len(y))
    return (x > y) - (x < y)


def firmware_exclusion(device_fw: str | None, below: str | None, at_least: str | None) -> str | None:
    """Reason why the device's firmware rules this knowledge out, or None if it applies."""
    if not device_fw:
        return None
    if below and compare_versions(device_fw, below) >= 0:
        return f"only applies below firmware {below}, device has {device_fw}"
    if at_least and compare_versions(device_fw, at_least) < 0:
        return f"only applies from firmware {at_least} upward, device has {device_fw}"
    return None


def same_knowledge(a: dict, b: dict) -> bool:
    """Two assertions describe the same knowledge if they are the same kind, for the same device
    type, with the same outcome, and one's actions contain the other's (or they mostly overlap).
    e.g. [BOUNCE_INTERFACE] and [CHECK_TRAFFIC_COUNTERS, BOUNCE_INTERFACE] are the same fix.
    Access info is never merged (two gate codes are not duplicates), nor is anything without actions."""
    if "access_info" in (a["knowledge_type"], b["knowledge_type"]):
        return False
    if not a["actions"] or not b["actions"]:
        return False
    if (a["knowledge_type"], a["scope_node_type"]) != (b["knowledge_type"], b["scope_node_type"]):
        return False
    if (a["outcome"] == "failed") != (b["outcome"] == "failed"):
        return False
    x, y = set(a["actions"]), set(b["actions"])
    return x <= y or y <= x or len(x & y) / len(x | y) >= 0.5


def how_it_applies(g: dict, device: dict) -> str:
    link = g.get("link") or {}
    how = link.get("how")
    if how == "id" or (g["observed_on_this_device"] and how not in ("alias", "location")):
        return "observed on this device"
    if how == "alias":
        return f"observed on this device ({link.get('via') or 'by its nickname'})"
    if how == "location":
        return f"observed on this device (identified by place: {link.get('via')}; no device ID was written)"
    if how == "site":
        others = [c for c in link.get("candidates") or [] if c != device["node_id"]]
        return (f"reported at the {link.get('site')} site without naming the device"
                + (f" (also possible: {', '.join(others)})" if others else "") + "; not confirmed for this device")
    if g["age_limited"]:
        return "applies to similar devices (same type and age)"
    return "applies to all devices of this type"


def find_knowledge(node_id: str, symptoms: list[str] | None = None, events: list[str] | None = None) -> dict:
    rows = graph.run(QUERY, node_id=node_id)
    if not rows:
        exists = graph.run("MATCH (d:Device {node_id: $id}) RETURN d.node_id", id=node_id)
        return {"device": None if not exists else node_id, "results": [], "excluded_by_firmware": [],
                "message": "Unknown device" if not exists else "No recorded knowledge applies to this device"}

    device = dict(rows[0]["device"])
    groups: dict[str, dict] = {}
    excluded = []

    for r in rows:
        a = dict(r["a"])
        reason = firmware_exclusion(device["firmware"], a.get("scope_firmware_below"),
                                    a.get("scope_firmware_at_least"))
        if reason:
            excluded.append({"id": a["id"], "summary": a["summary"], "reason": reason})
            continue
        key = next((gk for gk, g in groups.items() if any(same_knowledge(a, m) for m in g["members"])), a["id"])
        g = groups.setdefault(key, {
            "members": [],
            "knowledge_ids": [], "knowledge_type": a["knowledge_type"], "summary": a["summary"],
            "events": set(), "symptoms": set(), "actions": a["actions"], "avoid": set(),
            "outcome": a["outcome"], "details": [], "status": set(), "base_confidence": 0.0,
            "sources": {}, "authors": set(), "seen_on_devices": set(), "observed_on_this_device": False,
            "age_limited": False, "firmware_limited": False, "latest": a["valid_from"],
            "link": None, "link_factor": 0.0,
        })
        g["knowledge_ids"].append(a["id"])
        g["members"].append(a)
        if len(a["actions"] or []) > len(g["actions"] or []):
            g["actions"] = a["actions"]
        g["events"].update(a["events"] or [])
        g["symptoms"].update(a["symptoms"] or [])
        g["avoid"].update(a["avoid"] or [])
        if a.get("details") and a["details"] not in g["details"]:
            g["details"].append(a["details"])
        g["age_limited"] |= a.get("scope_installed_before") not in (None, "", "null")
        g["firmware_limited"] |= bool(a.get("scope_firmware_below") or a.get("scope_firmware_at_least"))
        g["status"].add(a.get("status") or "auto_captured")
        g["base_confidence"] = max(g["base_confidence"], a["confidence"] or 0)
        if a["outcome"] == "worked":
            g["outcome"] = "worked"
        for s in r["sources"]:
            if s.get("id"):
                g["sources"][s["id"]] = s
        g["authors"].update(r["authors"])
        g["seen_on_devices"].update(r["devices"])
        g["observed_on_this_device"] |= bool(r["direct"])
        link, site = r.get("link"), r.get("site_link")
        if link:
            path = {"how": link["linked_by"], "factor": link["link_confidence"] or 1.0, "via": link.get("via")}
        elif r.get("by_scope"):
            path = {"how": "scope", "factor": 1.0, "via": None}
        elif site:
            path = {"how": "site", "factor": site["link_confidence"] or 0.5, "site": site["site"],
                    "candidates": site.get("candidates") or []}
        else:
            path = {"how": "scope", "factor": 1.0, "via": None}
        rank = {"id": 5, "alias": 4, "location": 3, "scope": 2, "site": 1}
        if g["link"] is None or rank[path["how"]] > rank[g["link"]["how"]]:
            g["link"], g["link_factor"] = path, path["factor"]
        if a["valid_from"] and a["valid_from"] > (g["latest"] or ""):
            g["latest"], g["summary"] = a["valid_from"], a["summary"]

    results = []
    wanted_symptoms, wanted_events = set(symptoms or []), set(events or [])
    wanted = wanted_symptoms | wanted_events
    for g in groups.values():
        n_sources = len(g["sources"])
        confidence = min(MAX_CONFIDENCE, g["base_confidence"] + CONFIRMATION_BONUS * max(0, n_sources - 1))
        if g["outcome"] == "failed":
            confidence = g["base_confidence"]
        confidence *= g["link_factor"] or 1.0
        match = match_score(wanted_symptoms, wanted_events, g["symptoms"], g["events"])
        results.append({
            "summary": g["summary"],
            "knowledge_type": g["knowledge_type"],
            "outcome": g["outcome"],
            "actions": g["actions"],
            "avoid": sorted(g["avoid"]),
            "symptoms": sorted(g["symptoms"]),
            "events": sorted(g["events"]),
            "details": g["details"],
            "confidence": round(confidence, 2),
            "symptom_match": None if match is None else round(match, 2),
            "how_it_applies": how_it_applies(g, device),
            "link": {k: v for k, v in (g["link"] or {}).items() if k != "factor"},
            "seen_on_devices": sorted(g["seen_on_devices"]),
            "sources": sorted(g["sources"].values(), key=lambda s: s.get("timestamp") or ""),
            "authors": sorted(x for x in g["authors"] if x),
            "disputed": "disputed" in g["status"],
            "knowledge_ids": g["knowledge_ids"],
            "_keep_unmatched": g["firmware_limited"],
        })

    results.sort(key=lambda r: (
        r["outcome"] == "failed",
        -(r["symptom_match"] or 0),
        not r["how_it_applies"].startswith("observed on this"),
        not r["how_it_applies"].startswith("applies to similar"),
        -r["confidence"],
    ))
    if wanted:
        results = [r for r in results if r["knowledge_type"] == "access_info"
                   or (r["symptom_match"] or 0) > 0
                   or (r["symptom_match"] is None and r["_keep_unmatched"])]
    for r in results:
        r.pop("_keep_unmatched", None)
    return {"device": device, "results": results, "excluded_by_firmware": excluded}


def print_readable(res: dict):
    if not res["device"] or isinstance(res["device"], str):
        print(res.get("message"))
        return
    d = res["device"]
    print(f"\n{d['node_id']}  ({d['node_type']}, installed {d['install_date']}, firmware {d['firmware']})")
    if not res["results"]:
        print("  No recorded knowledge applies to this device.")
    for i, r in enumerate(res["results"], 1):
        flag = "  ⚠ DISPUTED" if r["disputed"] else ""
        print(f"\n[{i}] {r['knowledge_type']} · outcome {r['outcome']} · confidence {r['confidence']}"
              + (f" · match {r['symptom_match']}" if r["symptom_match"] is not None else "") + flag)
        print(f"    {r['summary']}")
        if r["actions"] and r["outcome"] == "failed":
            print(f"    tried: {' -> '.join(r['actions'])}   (did NOT work)")
        elif r["actions"]:
            print(f"    do:    {' -> '.join(r['actions'])}")
        if r["avoid"]:
            print(f"    avoid: {', '.join(r['avoid'])}")
        for det in r["details"][:2]:
            print(f"    details: {det}")
        if len(r["details"]) > 2:
            print(f"    (+{len(r['details']) - 2} more details from other sources)")
        print(f"    {r['how_it_applies']}; seen on {', '.join(r['seen_on_devices']) or '-'}")
        srcs = ", ".join(f"{s['id']} ({s['channel']}, {(s.get('timestamp') or '')[:10]})" for s in r["sources"])
        print(f"    sources: {srcs}  ·  by {', '.join(r['authors'])}")
    for e in res["excluded_by_firmware"]:
        print(f"\n  (not shown: {e['id']}: {e['reason']})")
