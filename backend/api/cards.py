"""
Pure helpers (no database, no Gemini) that turn stored knowledge into the KnowledgeCard
shape the frontend expects: readable steps, scope in plain words, status, source excerpts.
"""
import json
from functools import lru_cache

from pipeline import threads
from api.config import THREADS_DIR

# ---------- vocabulary codes -> readable text ----------
ACTION_TEXT = {
    "CHECK_TRAFFIC_COUNTERS": "Check that the traffic counters are increasing",
    "BOUNCE_INTERFACE": "Disable and re-enable the interface",
    "REBOOT_UNIT": "Reboot the whole unit",
    "REPLACE_SFP": "Replace the SFP",
    "CLEAN_CONNECTOR": "Clean the optical connector",
    "CLEAR_ICE_RADOME": "Clear ice from the radome",
    "REPLACE_PSU": "Replace the power supply unit",
    "READD_PORT_CHANNEL_MEMBER": "Remove and re-add the port-channel member",
    "CHECK_TEMP_SENSOR": "Check the temperature sensor",
    "CHECK_CHASSIS_TEMP": "Check the chassis temperature",
    "CHECK_MOUNT_BOLTS": "Check the antenna mount bolts",
    "REALIGN_ANTENNA": "Realign the antenna",
    "REPLACE_FUSE": "Replace the fuse",
    "USE_APPROVED_PART": "Use only the approved part",
    "SET_CONSOLE_BAUD_9600": "Set the console speed to 9600 baud",
    "REPLACE_PATCH_CABLE": "Replace the patch cable",
    "REPLACE_LINE_CARD": "Replace the line card",
    "COLD_RESTART_BASEBAND": "Cold-restart the baseband unit",
    "WARM_REBOOT": "Do a warm reboot",
    "ENABLE_ATPC": "Enable ATPC (automatic transmit power control)",
    "WAIT_INVENTORY_REFRESH": "Wait for the inventory to refresh",
    "RESEAT_MODULE": "Reseat the module",
    "NO_DISPATCH_NEEDED": "No site visit needed",
}
ACRONYMS = {"SFP", "PSU", "ATPC", "CPU", "GPS", "CRC", "LACP", "BTS", "TRN", "AGG", "MW", "UPS", "NOC", "ID"}

NODE_TYPE_TEXT = {
    "transmission": "Transmission nodes",
    "aggregation_router": "Aggregation routers",
    "base_station": "Base stations",
    "microwave_link": "Microwave links",
}


def humanize(code: str) -> str:
    """BOUNCE_INTERFACE -> 'Bounce interface', REPLACE_SFP -> 'Replace SFP'."""
    words = [w if w in ACRONYMS else w.lower() for w in (code or "").split("_") if w]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def action_text(code: str) -> str:
    return ACTION_TEXT.get(code) or humanize(code)


def avoid_text(code: str) -> str:
    t = action_text(code)
    first = t.split(" ", 1)[0]
    if first not in ACRONYMS:
        t = t[:1].lower() + t[1:]
    return f"Don't {t}"


# ---------- scope / status ----------
def scope_text(scope: dict, observed_on: list[str], link: dict | None = None) -> str:
    if not scope.get("node_type"):
        if (link or {}).get("how") == "site" and not observed_on:
            cands = link.get("candidates") or []
            return f"Devices at the {link.get('site')} site" + (f": {', '.join(cands)}" if cands else "")
        if observed_on:
            return "Only the device" + ("s" if len(observed_on) > 1 else "") + " it was seen on: " + ", ".join(observed_on)
        return "Specific devices only"
    parts = [NODE_TYPE_TEXT.get(scope["node_type"], humanize(scope["node_type"]))]
    if scope.get("installed_before"):
        d = scope["installed_before"][:10]
        parts[0] += f" installed before {d[:4] if d.endswith('-01-01') else d}"
    if scope.get("firmware_below"):
        parts.append(f"firmware below {scope['firmware_below']}")
    if scope.get("firmware_at_least"):
        parts.append(f"firmware {scope['firmware_at_least']} or later")
    if len(parts) == 1 and not scope.get("installed_before"):
        parts[0] = "All " + parts[0][:1].lower() + parts[0][1:]
    return ", ".join(parts)


def card_status(statuses: set[str], outcome: str, valid_to: str | None) -> str:
    if "disputed" in statuses:
        return "disputed"
    if valid_to or "superseded" in statuses:
        return "outdated"
    if outcome == "worked":
        return "confirmed"
    return "unconfirmed"


# ---------- source excerpts ----------
@lru_cache(maxsize=512)
def _thread(thread_id: str) -> dict | None:
    for suffix in (".json", ".txt"):
        path = THREADS_DIR / f"{thread_id}{suffix}"
        if path.exists():
            try:
                return threads.load_thread(path)
            except Exception:
                return None
    return None


def excerpt(source_id: str, author: str | None, fallback_text: str | None = None, limit: int = 320) -> str | None:
    """The author's own words from the original conversation (that is where the knowledge is)."""
    t = _thread(source_id)
    if t:
        mine = [m["text"] for m in t["messages"] if author and m["author"] == author]
        text = " … ".join(mine or [m["text"] for m in t["messages"]])
    else:
        text = fallback_text or ""
    text = " ".join(text.split())
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + " …"


def short_date(ts: str | None) -> str:
    return (ts or "")[:10]


def compact_for_llm(card: dict) -> dict:
    """What Gemini sees of a card in Step C (small, no excerpts beyond a short quote)."""
    out = {
        "id": card["assertion_id"],
        "type": card["knowledge_type"],
        "status": card["status"],
        "outcome": card["outcome"],
        "summary": card["summary"],
        "steps": card["actions_text"],
        "avoid": card["avoid_text"],
        "applies_to": card["scope_text"],
        "how_it_applies": card.get("how_it_applies"),
        "confidence": card["confidence"],
        "seen_on": card["observed_on"],
        "sources": [f"{s.get('author') or 'unknown'} ({s['channel']}, {short_date(s.get('timestamp'))})"
                    for s in card["sources"]],
    }
    if card.get("details"):
        out["details"] = card["details"]
    if card.get("scope_note"):
        out["not_applicable_because"] = card["scope_note"]
    if card.get("related_failed"):
        out["tried_and_failed"] = [
            f["summary"] + (f" (seen on {', '.join(f['observed_on'])})" if f.get("observed_on") else "")
            for f in card["related_failed"]]
    if card.get("conflicts_with"):
        out["experts_disagree_with"] = [c["summary"] for c in card["conflicts_with"]]
    return out


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=list)
