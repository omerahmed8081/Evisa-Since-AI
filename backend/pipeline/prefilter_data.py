"""Training data for the pre-filter: labels from cached Gemini decisions plus template noise."""
import csv
import itertools
import os
from pathlib import Path

from pipeline import DATA_DIR, cache, linking, threads
from pipeline.ingest import device_context
from pipeline.prompts import FEW_SHOT_EXAMPLES, SYSTEM_INSTRUCTION


def _inventory() -> dict[str, dict]:
    with open(DATA_DIR / "inventory" / "nodes.csv", encoding="utf-8") as f:
        return {r["node_id"]: r for r in csv.DictReader(f)}


def gemini_label(thread: dict, inventory: dict, model: str) -> bool | None:
    """Gemini's cached useful/noise decision for this conversation, or None if never extracted."""
    text = threads.thread_to_prompt_text(thread)
    raw = (thread.get("subject") or "") + "\n" + "\n".join(m["text"] for m in thread["messages"])
    match = linking.csv_inventory().resolve(raw)
    ids = threads.find_device_ids(thread) | match.ids | set(match.aliases)
    devices = [inventory[i] for i in ids if i in inventory]
    orders = itertools.permutations(devices) if len(devices) <= 4 else [devices]
    for order in orders:
        key = cache.make_key(model, SYSTEM_INSTRUCTION, FEW_SHOT_EXAMPLES, text, device_context(list(order)))
        hit = cache.get("extract", key)
        if hit is not None:
            return bool(hit["useful"])
    return None


def load_examples(threads_dir: Path = DATA_DIR / "threads", noise_dir: Path = DATA_DIR / "noise_threads"):
    """[(thread, label 1/0, label source)] for real conversations (Gemini labels) + template noise."""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    inventory = _inventory()
    examples, missing = [], []
    for f in sorted(threads_dir.iterdir()):
        t = threads.load_thread(f)
        label = gemini_label(t, inventory, model)
        if label is None:
            missing.append(t["thread_id"])
            continue
        examples.append((t, int(label), "gemini"))
    if noise_dir.exists():
        for f in sorted(noise_dir.glob("*.json")):
            examples.append((threads.load_thread(f), 0, "template noise"))
    return examples, missing
