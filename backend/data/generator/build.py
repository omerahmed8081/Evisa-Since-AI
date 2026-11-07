"""Builds the synthetic dataset in data/ from scenarios.py.

    python data/generator/build.py"""
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
ROOT = DATA.parent
ELISA = ROOT / "ELISA_HIDDEN_KNOWLEDGE_EXAMPLE_2026" / "ELISA_HIDDEN_KNOWLEDGE_EXAMPLE_2026"
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402

TZ = ZoneInfo("Europe/Helsinki")
SYNTH_NOTE = "Synthetic, based on Elisa's example. Names and node IDs are illustrative."
CALL_NOTE = "Synthetic phone call transcript (spoken turns), based on Elisa's example. Names and node IDs are illustrative."
ELISA_NOTE = ("Elisa's original example, copied word for word. Added by our team: thread_id, date, language "
              "and per-message timestamp (Elisa gave times only; date 2025-03-12 chosen by us).")


def ts(date, hhmm):
    y, m, d = map(int, date.split("-"))
    hh, mm = map(int, hhmm.split(":"))
    return datetime(y, m, d, hh, mm, tzinfo=TZ).isoformat()


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_inventory():
    out = DATA / "inventory" / "nodes.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["node_id", "node_type", "install_date", "firmware", "location", "status"])
        for row in S.NODES:
            w.writerow(list(row) + ["in_service"])
    return len(S.NODES)


def build_events():
    rows = []
    for date, hhmm, node, etype, detail, related, extra in S.EVENTS:
        rows.append((ts(date, hhmm), node, etype, detail, related, extra))
    rows.sort(key=lambda r: (datetime.fromisoformat(r[0]), r[1]))
    events = []
    for i, (t, node, etype, detail, related, extra) in enumerate(rows, 1):
        ev = {"event_id": "EV-%04d" % i, "timestamp": t, "node_id": node, "event_type": etype}
        ev.update(extra)
        ev["detail"] = detail
        ev["related_thread"] = related
        events.append(ev)
    write_json(DATA / "events" / "events.json", events)
    return len(events)


def chat_from_elisa(th):
    src = json.loads((ELISA / "teams_chat.json").read_text(encoding="utf-8"))
    msgs = []
    for m in src["messages"]:
        msgs.append({"seq": m["seq"], "time": m["time"], "timestamp": ts(th["date"], m["time"]),
                     "author": m["author"], "role": m["role"], "text": m["text"]})
    return {"thread_id": th["id"], "channel": "teams", "date": th["date"], "language": th["language"],
            "note": ELISA_NOTE, "participants": src["participants"], "messages": msgs}


def chat(th):
    msgs = []
    for seq, (hhmm, author, text) in enumerate(th["messages"], 1):
        msgs.append({"seq": seq, "time": hhmm, "timestamp": ts(th["date"], hhmm),
                     "author": author, "role": S.ROLES[author], "text": text})
    return {"thread_id": th["id"], "channel": th["channel"], "date": th["date"], "language": th["language"],
            "note": CALL_NOTE if th["channel"] == "call" else SYNTH_NOTE,
            "participants": [{"name": p, "role": S.ROLES[p]} for p in th["participants"]],
            "messages": msgs}


def email_text(th):
    if th.get("elisa_original"):
        raw = (ELISA / "email.txt").read_text(encoding="utf-8")
        header, body = raw.split("\n\n", 1)
        subject = [l for l in header.splitlines() if l.startswith("Subject:")][0][len("Subject: "):]
    else:
        subject, body = th["subject"], th["body"]
    to = ", ".join("%s <%s>" % (p, S.ROLES[p]) for p in th["to"])
    head = [
        "Thread-ID: %s" % th["id"],
        "Date: %s" % ts(th["date"], th["time"]),
        "From: %s <%s>" % (th["sender"], S.ROLES[th["sender"]]),
        "To: %s" % to,
        "Subject: %s" % subject,
    ]
    return "\n".join(head) + "\n\n" + body


def build_threads():
    built = {}
    tdir = DATA / "threads"
    tdir.mkdir(parents=True, exist_ok=True)
    for th in S.THREADS:
        if th["channel"] == "email":
            (tdir / ("%s.txt" % th["id"])).write_text(email_text(th), encoding="utf-8")
            built[th["id"]] = {"email_date": ts(th["date"], th["time"])}
        else:
            obj = chat_from_elisa(th) if th.get("elisa_original") else chat(th)
            write_json(tdir / ("%s.json" % th["id"]), obj)
            built[th["id"]] = {"messages": {m["seq"]: m["timestamp"] for m in obj["messages"]}}
    return built


KNOWLEDGE_ORDER = ["knowledge_type", "summary", "observed_on", "scope", "events", "symptoms", "actions",
                   "avoid", "outcome", "details", "author", "source_message_seqs", "valid_from"]


def build_ground_truth(built):
    lang = {th["id"]: th["language"] for th in S.THREADS}
    entries = []
    valid_from = {}
    for th in S.THREADS:
        tid = th["id"]
        gt = S.GROUND_TRUTH[tid]
        k = gt["knowledge"]
        if k is not None:
            k = dict(k)
            seq = k.pop("valid_from_seq", None)
            if "email_date" in built[tid]:
                k["valid_from"] = built[tid]["email_date"]
            else:
                k["valid_from"] = built[tid]["messages"][seq]
            valid_from[tid] = k["valid_from"]
            k = {key: k[key] for key in KNOWLEDGE_ORDER}
        entries.append({"thread_id": tid, "category": gt["category"], "useful": k is not None,
                        "language": lang[tid], "knowledge": k, "relations": gt["relations"],
                        "expected_effects": gt["expected_effects"], "notes": gt["notes"]})
    for e in entries:
        for eff in e["expected_effects"]:
            v = eff.get("valid_to")
            if isinstance(v, str) and v.startswith("<"):
                eff["valid_to"] = valid_from[v[1:].split(".")[0]]
    write_json(DATA / "ground_truth.json", entries)
    return entries


def main():
    n_nodes = build_inventory()
    n_events = build_events()
    built = build_threads()
    gt = build_ground_truth(built)
    print("nodes: %d, events: %d, threads: %d, ground truth entries: %d" % (n_nodes, n_events, len(built), len(gt)))


if __name__ == "__main__":
    main()
