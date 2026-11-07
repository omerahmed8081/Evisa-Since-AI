"""
Load Teams/call JSON and email .txt files into one common format,
and turn a thread into the text we send to Gemini.
"""
import json
import re
from pathlib import Path

DEVICE_ID_RE = re.compile(r"\b(TRN|AGG|BTS|MW)-\d{2,4}\b")


def load_thread(path: Path) -> dict:
    if path.suffix == ".json":
        return _load_json_thread(path)
    if path.suffix == ".txt":
        return _load_email(path)
    raise ValueError(f"Unknown thread file type: {path}")


def _load_json_thread(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "thread_id": data.get("thread_id", path.stem),
        "channel": data.get("channel", "teams"),
        "language": data.get("language"),
        "subject": None,
        "participants": [p["name"] for p in data.get("participants", [])],
        "messages": [
            {
                "seq": m["seq"],
                "timestamp": m.get("timestamp"),
                "author": m["author"],
                "role": m.get("role"),
                "text": m["text"],
            }
            for m in data["messages"]
        ],
    }


def _load_email(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    header_part, _, body = raw.partition("\n\n")
    headers = {}
    for line in header_part.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip().lower()] = value.strip()
    author, _, role = headers.get("from", "unknown").partition("<")
    recipients = [r.partition("<")[0].strip() for r in headers.get("to", "").split(",") if r.strip()]
    return {
        "thread_id": headers.get("thread-id", path.stem),
        "channel": "email",
        "language": None,
        "subject": headers.get("subject"),
        "participants": [author.strip()] + recipients,
        "messages": [
            {
                "seq": 1,
                "timestamp": headers.get("date"),
                "author": author.strip(),
                "role": role.rstrip(">").strip() or None,
                "text": body.strip(),
            }
        ],
    }


def thread_to_prompt_text(thread: dict) -> str:
    lines = [f"Channel: {thread['channel']}"]
    if thread.get("subject"):
        lines.append(f"Subject: {thread['subject']}")
    for m in thread["messages"]:
        who = f"{m['author']} ({m['role']})" if m.get("role") else m["author"]
        lines.append(f"[seq {m['seq']} | {m.get('timestamp')} | {who}]\n{m['text']}")
    return "\n\n".join(lines)


def find_device_ids(thread: dict) -> set[str]:
    """Device IDs written anywhere in the thread (including the email subject)."""
    text = (thread.get("subject") or "") + "\n" + "\n".join(m["text"] for m in thread["messages"])
    return {m.group(0) for m in DEVICE_ID_RE.finditer(text)}


def message_timestamp(thread: dict, seq: int | None) -> str | None:
    if seq is not None:
        for m in thread["messages"]:
            if m["seq"] == seq:
                return m.get("timestamp")
    return thread["messages"][-1].get("timestamp")


def full_name(name: str, participants: list[str]) -> str:
    """Map a short name Gemini returned ("Erkki") to the participant's full name ("Erkki Expert")."""
    if not name:
        return name
    clean = name.strip()
    for p in participants:
        if p.lower() == clean.lower():
            return p
    matches = [p for p in participants if p.lower().split()[0] == clean.lower().split()[0]]
    return matches[0] if len(matches) == 1 else clean
