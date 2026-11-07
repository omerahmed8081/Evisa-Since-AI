"""
Retrieval: "what do we know that applies to this device?"

This is the function the chatbot agent will call as a tool. It:
  1. finds knowledge observed on the device itself, or whose scope rule covers it
     (same device type, installed before the cutoff), that is still valid (valid_to is null),
  2. drops knowledge whose firmware limits exclude this device's firmware:
     firmware_below ("workaround only needed below 3.4") and firmware_at_least ("fixed from 3.4 on"),
  3. GROUPS duplicates: the same fix captured from several chats/emails/devices becomes ONE
     result with all its sources and devices, and a confidence that grows with confirmations,
  4. optionally ranks by how well the stored symptoms match the symptoms in the question.

Command line: python scripts/retrieve.py TRN-077 [--symptoms ...] [--json]
"""


from pipeline import graph


QUERY = """
MATCH (d:Device {node_id: $node_id})
MATCH (a:Assertion)
WHERE a.valid_to IS NULL
  AND ( EXISTS { (a)-[:OBSERVED_ON]->(d) }
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
       collect(DISTINCT s {.id, .channel, timestamp: toString(s.timestamp)}) AS sources,
       collect(DISTINCT p.name) AS authors,
       collect(DISTINCT od.node_id) AS devices
"""

CONFIRMATION_BONUS = 0.1   # per extra independent source
MAX_CONFIDENCE = 0.95


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
        return False  # "worked" and "unknown" can merge; a failed attempt never merges with a fix
    x, y = set(a["actions"]), set(b["actions"])
    return x <= y or y <= x or len(x & y) / len(x | y) >= 0.5


def find_knowledge(node_id: str, symptoms: list[str] | None = None) -> dict:
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
            "age_limited": False, "latest": a["valid_from"],
        })
        g["knowledge_ids"].append(a["id"])
        g["members"].append(a)
        if len(a["actions"] or []) > len(g["actions"] or []):
            g["actions"] = a["actions"]  # keep the most complete list of steps
        g["events"].update(a["events"] or [])
        g["symptoms"].update(a["symptoms"] or [])
        g["avoid"].update(a["avoid"] or [])
        if a.get("details") and a["details"] not in g["details"]:
            g["details"].append(a["details"])
        g["age_limited"] |= a.get("scope_installed_before") not in (None, "", "null")
        g["status"].add(a.get("status") or "auto_captured")
        g["base_confidence"] = max(g["base_confidence"], a["confidence"] or 0)
        if a["outcome"] == "worked":
            g["outcome"] = "worked"  # one confirmed success is enough for the merged result
        for s in r["sources"]:
            if s.get("id"):
                g["sources"][s["id"]] = s
        g["authors"].update(r["authors"])
        g["seen_on_devices"].update(r["devices"])
        g["observed_on_this_device"] |= bool(r["direct"])
        if a["valid_from"] and a["valid_from"] > (g["latest"] or ""):
            g["latest"], g["summary"] = a["valid_from"], a["summary"]  # newest wording wins

    results = []
    wanted = set(symptoms or [])
    for g in groups.values():
        n_sources = len(g["sources"])
        confidence = min(MAX_CONFIDENCE, g["base_confidence"] + CONFIRMATION_BONUS * max(0, n_sources - 1))
        if g["outcome"] == "failed":
            confidence = g["base_confidence"]  # repeated failures don't make a fix more trustworthy
        match = len(wanted & g["symptoms"]) / len(wanted) if wanted else None
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
            "how_it_applies": "observed on this device" if g["observed_on_this_device"]
                              else ("applies to similar devices (same type and age)" if g["age_limited"]
                                    else "applies to all devices of this type"),
            "seen_on_devices": sorted(g["seen_on_devices"]),
            "sources": sorted(g["sources"].values(), key=lambda s: s.get("timestamp") or ""),
            "authors": sorted(x for x in g["authors"] if x),
            "disputed": "disputed" in g["status"],
            "knowledge_ids": g["knowledge_ids"],
        })

    results.sort(key=lambda r: (
        r["outcome"] == "failed",                      # what worked first, failed attempts last
        -(r["symptom_match"] or 0),
        not r["how_it_applies"].startswith("observed on this"),
        not r["how_it_applies"].startswith("applies to similar"),
        -r["confidence"],
    ))
    if wanted:  # with symptoms given, drop knowledge that shares none of them (access info is kept)
        results = [r for r in results if r["symptom_match"] or r["knowledge_type"] == "access_info"]
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
              + (f" · symptom match {r['symptom_match']}" if r["symptom_match"] is not None else "") + flag)
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
