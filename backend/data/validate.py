"""Quality checks for the synthetic dataset (brief section 10 + v4 amendments).

Usage:  python3 data/validate.py      (exit code 0 = all checks pass)
Self-contained: reads only the files in data/, not the generator.
"""
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Helsinki")

VOCAB = {
    "knowledge_type": {"troubleshooting_rule", "known_false_alarm", "hardware_compatibility", "practical_tip", "access_info"},
    "events": {"SFP_REPLACEMENT", "PATCH_CABLE_CHANGE", "MODULE_HOT_SWAP", "FIRMWARE_UPGRADE", "POWER_OUTAGE", "STORM",
               "HEAVY_SNOW_ICE", "COLD_WEATHER", "MAINTENANCE"},
    "symptoms": {"INTERFACE_UP", "INTERFACE_DOWN", "OPTICAL_LEVELS_NORMAL", "OPTICAL_LEVELS_LOW", "ALARMS_CLEARED",
                 "TRAFFIC_COUNTERS_ZERO", "LINK_FLAPPING", "LINK_DOWN", "LACP_BUNDLE_DOWN", "HIGH_CPU", "BATTERY_ALARM",
                 "FAN_ALARM", "GPS_SYNC_LOST", "ALIGNMENT_LOST", "SFP_NOT_RECOGNISED", "CRC_ERRORS", "CELL_DOWN",
                 "MODULE_UNKNOWN", "LINK_FADING"},
    "actions": {"CHECK_TRAFFIC_COUNTERS", "BOUNCE_INTERFACE", "REBOOT_UNIT", "REPLACE_SFP", "CLEAN_CONNECTOR",
                "CLEAR_ICE_RADOME", "REPLACE_PSU", "READD_PORT_CHANNEL_MEMBER", "CHECK_TEMP_SENSOR", "CHECK_CHASSIS_TEMP",
                "CHECK_MOUNT_BOLTS", "REALIGN_ANTENNA", "REPLACE_FUSE", "USE_APPROVED_PART", "SET_CONSOLE_BAUD_9600",
                "REPLACE_PATCH_CABLE", "REPLACE_LINE_CARD", "COLD_RESTART_BASEBAND", "WARM_REBOOT", "ENABLE_ATPC",
                "WAIT_INVENTORY_REFRESH", "RESEAT_MODULE", "NO_DISPATCH_NEEDED"},
    "outcome": {"worked", "failed", "unknown"},
}
CATEGORIES = {"correct_fix", "reinforcing", "wrong_advice", "narrows_scope", "superseding", "conflicting",
              "access_info", "noise"}
EVENT_TYPES = {"alarm_raised", "alarm_cleared", "work_order", "dispatch", "firmware_upgrade", "hw_replacement"}
RELATION_TYPES = {"same_knowledge_as", "reinforces", "narrows_scope", "supersedes", "conflicts_with"}

EXPECTED_IDS = (["T%03d" % i for i in range(1, 27)] + ["E%03d" % i for i in range(1, 9)] + ["C001", "C002"])

# Required firmware histories (section 3.1); extra devices may add their own.
REQUIRED_FW = {
    "TRN-042": [], "TRN-031": [], "TRN-101": [], "TRN-112": [], "TRN-118": [], "AGG-003": [], "AGG-012": [],
    "BTS-233": [], "BTS-250": [], "BTS-261": [],
    "TRN-077": [("3.2.1", "3.4.0", "2026-03-24")],
    "TRN-015": [("3.1.2", "3.4.0", "2026-03-25")],
    "AGG-007": [("7.3.5", "7.4.0", "2025-05-21")],
    "BTS-210": [("2.4.0", "2.6.0", "2026-02-18")],
    "MW-401": [("1.3.0", "1.4.0", "2023-10-17")],
    "MW-405": [("1.3.2", "1.4.0", "2023-10-18")],
    "MW-412": [("1.3.4", "1.4.0", "2023-10-19")],
}

# Section 8.3 (+ v4 firmware_at_least). (observed_on, node_type, installed_before, firmware_below, firmware_at_least)
# node_type None => scope must be null.  Whole tuple None => useful: false.
O = "2020-01-01"
EXPECTED_SCOPE = {
    "T001": (["TRN-042"], "transmission", O, None, None),
    "E001": (["TRN-042"], "transmission", O, None, None),
    "T002": (["TRN-077"], "transmission", O, None, None),
    "E006": (["TRN-031"], "transmission", O, None, None),
    "T014": (["TRN-015"], "transmission", O, None, None),
    "T015": (["TRN-031"], "transmission", O, None, None),
    "E005": ([], "transmission", O, None, None),
    "T013": ([], "transmission", O, None, None),
    "T007": (["TRN-015"], "transmission", None, "3.2", None),
    "E004": (["TRN-101"], "transmission", None, None, None),
    "T009": (["TRN-112"], "transmission", None, None, None),
    "E002": (["AGG-012"], "aggregation_router", None, None, None),
    "T012": (["AGG-003"], "aggregation_router", None, None, None),
    "T010": (["AGG-003"], "aggregation_router", None, None, None),
    "T005": (["AGG-007"], "aggregation_router", None, None, None),
    "T018": (["AGG-012"], "aggregation_router", O, None, None),
    "T004": (["BTS-233"], "base_station", O, None, None),
    "C001": (["BTS-210"], "base_station", O, None, None),
    "T006": (["BTS-250"], "base_station", None, None, None),
    "T011": (["BTS-261"], "base_station", None, None, None),
    "T003": (["MW-405"], "microwave_link", None, None, None),
    "T017": (["MW-405"], "microwave_link", None, None, None),
    "E003": (["MW-401", "MW-405", "MW-412"], "microwave_link", None, None, None),
    "T008": (["MW-412"], "microwave_link", None, None, None),
    "E007": (["TRN-077", "TRN-015"], "transmission", O, None, "3.4"),
    "T016": (["BTS-210"], "base_station", O, None, "2.6"),
    "E008": (["TRN-042", "BTS-233"], None, None, None, None),
    "T022": (["BTS-210"], None, None, None, None),
    "T023": (["BTS-210"], None, None, None, None),
    # linking without a device ID: by place, by site, by nickname
    "T024": (["TRN-042"], None, None, None, None),
    "T025": ([], None, None, None, None),
    "T026": (["MW-412"], None, None, None, None),
    "T019": None, "T020": None, "T021": None, "C002": None,
}

# thread ids, or ("FW", node_id) for that node's firmware upgrade
ORDER_CHAINS = [
    ["T001", "T002", "E006", "E007"],
    ["T004", "C001", "T016"],
    ["E002", "T012"],
    ["T003", "T017"],
    ["T022", "T023"],
    [("FW", "MW-401"), "E003"], [("FW", "MW-405"), "E003"], [("FW", "MW-412"), "E003"],
    [("FW", "AGG-007"), "T005"],
    [("FW", "BTS-210"), "T016"],
    [("FW", "TRN-077"), "E007"], [("FW", "TRN-015"), "E007"],
]

NODE_RE = re.compile(r"\b(?:TRN|AGG|BTS|MW)-\d{3}\b")

errors = []


def err(msg):
    errors.append(msg)


def ver(v):
    parts = [int(x) for x in v.split(".")]
    return tuple(parts + [0] * (3 - len(parts)))


def check_ts(value, where):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        err("%s: bad timestamp %r" % (where, value))
        return None
    if dt.tzinfo is None:
        err("%s: timestamp without offset %r" % (where, value))
        return None
    local = dt.replace(tzinfo=None)
    expected = local.replace(tzinfo=TZ).utcoffset()
    if dt.utcoffset() != expected:
        err("%s: offset %s wrong for Helsinki local time %s (expected %s)" % (where, dt.utcoffset(), local, expected))
    return dt


# --------------------------------------------------------------------------
def load_nodes():
    with (DATA / "inventory" / "nodes.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    nodes = {}
    for r in rows:
        if r["node_id"] in nodes:
            err("nodes.csv: duplicate %s" % r["node_id"])
        nodes[r["node_id"]] = r
        if r["status"] != "in_service":
            err("nodes.csv: %s status %r" % (r["node_id"], r["status"]))
        ver(r["firmware"])
    return nodes


def parse_email(path):
    text = path.read_text(encoding="utf-8")
    header, body = text.split("\n\n", 1)
    h = {}
    for line in header.splitlines():
        k, v = line.split(": ", 1)
        h[k] = v
    for k in ("Thread-ID", "Date", "From", "To", "Subject"):
        if k not in h:
            err("%s: missing header %s" % (path.name, k))
    return {"thread_id": h.get("Thread-ID"), "channel": "email", "date_ts": h.get("Date"),
            "text": h.get("Subject", "") + "\n" + body, "seqs": {1}}


def load_threads():
    threads = {}
    for p in sorted((DATA / "threads").iterdir()):
        if p.suffix == ".json":
            obj = json.loads(p.read_text(encoding="utf-8"))
            prev = None
            for i, m in enumerate(obj["messages"], 1):
                if m["seq"] != i:
                    err("%s: seq %s out of order" % (p.name, m["seq"]))
                dt = check_ts(m["timestamp"], "%s seq %s" % (p.name, m["seq"]))
                if dt and m["time"] != dt.strftime("%H:%M"):
                    err("%s seq %s: time %s != timestamp" % (p.name, m["seq"], m["time"]))
                if dt and dt.date().isoformat() != obj["date"]:
                    err("%s seq %s: timestamp date differs from thread date" % (p.name, m["seq"]))
                if dt and prev and dt < prev:
                    err("%s: messages not in ascending time order at seq %s" % (p.name, m["seq"]))
                prev = dt or prev
            t = {"thread_id": obj["thread_id"], "channel": obj["channel"], "language": obj.get("language"),
                 "start": datetime.fromisoformat(obj["messages"][0]["timestamp"]),
                 "text": "\n".join(m["text"] for m in obj["messages"]),
                 "seqs": {m["seq"] for m in obj["messages"]},
                 "ts_by_seq": {m["seq"]: m["timestamp"] for m in obj["messages"]}}
        elif p.suffix == ".txt":
            t = parse_email(p)
            t["start"] = check_ts(t["date_ts"], p.name)
            t["ts_by_seq"] = {1: t["date_ts"]}
        else:
            continue
        if t["thread_id"] != p.stem:
            err("%s: thread_id %s does not match file name" % (p.name, t["thread_id"]))
        threads[p.stem] = t
    return threads


# --------------------------------------------------------------------------
def main():
    nodes = load_nodes()
    events = json.loads((DATA / "events" / "events.json").read_text(encoding="utf-8"))
    threads = load_threads()
    gt = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))

    # 1. ids
    gt_ids = [e["thread_id"] for e in gt]
    if sorted(gt_ids) != sorted(EXPECTED_IDS) or len(set(gt_ids)) != len(gt_ids):
        err("ground_truth ids mismatch: %s" % sorted(set(gt_ids) ^ set(EXPECTED_IDS)))
    if sorted(threads) != sorted(EXPECTED_IDS):
        err("thread files mismatch: %s" % sorted(set(threads) ^ set(EXPECTED_IDS)))

    # 2. events + node references
    fw_events = {}
    prev_id = None
    for ev in events:
        where = ev.get("event_id")
        if ev["node_id"] not in nodes:
            err("%s: unknown node %s" % (where, ev["node_id"]))
        if ev["event_type"] not in EVENT_TYPES:
            err("%s: bad event_type %s" % (where, ev["event_type"]))
        ev["_dt"] = check_ts(ev["timestamp"], where)
        if ev.get("related_thread") is not None and ev["related_thread"] not in threads:
            err("%s: related_thread %s missing" % (where, ev["related_thread"]))
        if ev["event_type"] == "firmware_upgrade":
            if "from_firmware" not in ev or "to_firmware" not in ev:
                err("%s: firmware_upgrade without from/to" % where)
            else:
                fw_events.setdefault(ev["node_id"], []).append(ev)
        if prev_id and ev["event_id"] <= prev_id:
            err("%s: event ids not increasing" % where)
        prev_id = ev["event_id"]

    # 3. firmware consistency
    for node, evs in fw_events.items():
        evs.sort(key=lambda e: e["_dt"])
        for a, b in zip(evs, evs[1:]):
            if a["to_firmware"] != b["from_firmware"]:
                err("%s: firmware chain broken %s -> %s" % (node, a["to_firmware"], b["from_firmware"]))
        if evs[-1]["to_firmware"] != nodes[node]["firmware"]:
            err("%s: last upgrade ends at %s but nodes.csv says %s" % (node, evs[-1]["to_firmware"], nodes[node]["firmware"]))
        for e in evs:
            if ver(e["to_firmware"]) <= ver(e["from_firmware"]):
                err("%s: upgrade does not increase version" % e["event_id"])
    for node, hist in REQUIRED_FW.items():
        got = [(e["from_firmware"], e["to_firmware"], e["_dt"].date().isoformat()) for e in fw_events.get(node, [])]
        if got != hist:
            err("%s: firmware history %s != required %s" % (node, got, hist))

    # 4. a thread's first related event happens before the thread starts
    #    (later ones, e.g. alarm_cleared when the fix works, may fall inside it)
    first_ev = {}
    for ev in events:
        rt = ev.get("related_thread")
        if rt and rt not in first_ev:
            first_ev[rt] = ev
    for rt, ev in first_ev.items():
        if rt in threads and threads[rt]["start"] and ev["_dt"] > threads[rt]["start"]:
            err("%s: first related event %s is after the conversation starts" % (rt, ev["event_id"]))

    # 5. node ids mentioned in text exist
    for tid, t in threads.items():
        for nid in NODE_RE.findall(t["text"]):
            if nid not in nodes:
                err("%s: mentions unknown node %s" % (tid, nid))

    # 6. ordering
    def when(x):
        if isinstance(x, tuple):
            return fw_events[x[1]][0]["_dt"]
        return threads[x]["start"]
    for chain in ORDER_CHAINS:
        for a, b in zip(chain, chain[1:]):
            if not when(a) < when(b):
                err("ordering: %s should be before %s" % (a, b))

    # 7. label leak
    terms = VOCAB["events"] | VOCAB["symptoms"] | VOCAB["actions"]
    for tid, t in threads.items():
        for term in terms:
            if re.search(r"(?<![A-Z0-9_])%s(?![A-Z0-9_])" % re.escape(term), t["text"]):
                err("%s: label leak %s" % (tid, term))

    # 8. ground truth content
    by_id = {e["thread_id"]: e for e in gt}
    for e in gt:
        tid = e["thread_id"]
        t = threads.get(tid)
        if e["category"] not in CATEGORIES:
            err("%s: bad category %s" % (tid, e["category"]))
        if t and t.get("language") and t["language"] != e["language"]:
            err("%s: language %s in thread vs %s in ground truth" % (tid, t["language"], e["language"]))
        for r in e["relations"]:
            if r["type"] not in RELATION_TYPES or r["target"] not in by_id:
                err("%s: bad relation %s" % (tid, r))
            elif t and threads[r["target"]]["start"] >= t["start"]:
                err("%s: relation target %s is not earlier" % (tid, r["target"]))
        k = e["knowledge"]
        exp = EXPECTED_SCOPE[tid]
        if not e["useful"]:
            if k is not None:
                err("%s: useful false but knowledge set" % tid)
            if exp is not None:
                err("%s: expected useful" % tid)
            continue
        if k is None or exp is None:
            err("%s: useful true needs knowledge / expected noise" % tid)
            continue
        if k["knowledge_type"] not in VOCAB["knowledge_type"]:
            err("%s: bad knowledge_type" % tid)
        for field in ("events", "symptoms", "actions", "avoid"):
            allowed = VOCAB["actions"] if field == "avoid" else VOCAB[field]
            for term in k[field]:
                if term not in allowed:
                    err("%s: %s term %s not in vocabulary" % (tid, field, term))
        if k["outcome"] not in VOCAB["outcome"]:
            err("%s: bad outcome" % tid)
        if e["category"] == "wrong_advice" and (k["outcome"] != "failed" or not k["actions"]):
            err("%s: wrong_advice needs outcome failed and the failed action" % tid)
        for nid in k["observed_on"]:
            if nid not in nodes:
                err("%s: observed_on unknown node %s" % (tid, nid))
        if t:
            for s in k["source_message_seqs"]:
                if s not in t["seqs"]:
                    err("%s: source seq %s does not exist" % (tid, s))
            if k["valid_from"] not in t["ts_by_seq"].values():
                err("%s: valid_from is not the timestamp of any message" % tid)
        check_ts(k["valid_from"], "%s valid_from" % tid)
        # scope vs 8.3
        obs, ntype, ib, fb, fal = exp
        if sorted(k["observed_on"]) != sorted(obs):
            err("%s: observed_on %s != expected %s" % (tid, k["observed_on"], obs))
        sc = k["scope"]
        if ntype is None:
            if sc is not None:
                err("%s: scope should be null" % tid)
        else:
            want = {"node_type": ntype, "installed_before": ib, "firmware_below": fb, "firmware_at_least": fal}
            if sc != want:
                err("%s: scope %s != expected %s" % (tid, sc, want))
            for nid in k["observed_on"]:
                if nodes[nid]["node_type"] != ntype:
                    err("%s: %s is not a %s" % (tid, nid, ntype))

    # 9. language ratio
    fi = sum(1 for e in gt if e["language"] in ("fi", "mixed"))
    if not (0.28 <= fi / len(gt) <= 0.40):
        err("language: %d/%d fi/mixed, want about a third" % (fi, len(gt)))

    if errors:
        print("FAILED: %d problem(s)" % len(errors))
        for m in errors:
            print("  -", m)
        sys.exit(1)
    print("OK: %d nodes, %d events, %d threads, %d ground truth entries, %d/%d fi/mixed"
          % (len(nodes), len(events), len(threads), len(gt), fi, len(gt)))


if __name__ == "__main__":
    main()
