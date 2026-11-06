"""
Run the pipeline on conversation files:  filter -> extract -> link -> store.

  python ingest.py data/threads              # process all, oldest conversation first, write to Neo4j
  python ingest.py data/threads --dry-run    # only print Gemini's output (no Neo4j needed)
  python ingest.py data/threads --force      # re-process threads that are already in Neo4j
  python ingest.py data/threads --refresh    # ignore the Gemini cache (costs API calls)

Gemini answers are cached in cache/, so re-running after a reset costs no API calls
unless a conversation or the prompt changed.

Threads already in Neo4j are skipped by default, so if the free-tier rate limit stops a run,
just start it again and it continues where it stopped.

Design rule: the LLM handles LANGUAGE (what was said), code handles FACTS
(which devices exist, install dates, timestamps). That keeps the graph correct.
"""
import argparse
import csv
import json
import os
from datetime import datetime
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

import extract
import threads
from vocabulary import Vocabulary

load_dotenv()

BASE_CONFIDENCE = {"worked": 0.7, "unknown": 0.5, "failed": 0.3}
INVENTORY_CSV = Path("data/inventory/nodes.csv")


def csv_inventory(path: Path) -> list[dict]:
    """Used in --dry-run so device context works without Neo4j."""
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def device_context(devices: list[dict]) -> str:
    return "\n".join(
        f"{d['node_id']}: type={d['node_type']}, installed={d['install_date']}, firmware={d['firmware']}"
        for d in devices
    )


def older_cutoff() -> str:
    """The organisation's definition of an "older" unit: installed before this date.
    One fixed definition (not derived from a single device) so "older units" means the same
    thing in every conversation. In production this would be a hardware generation field."""
    return os.environ.get("DEFAULT_OLDER_BEFORE", "2020-01-01")


def is_older(device: dict) -> bool:
    return str(device["install_date"]) < older_cutoff()


def compute_scope(k, observed_devices: list[dict], node_type: str | None) -> dict:
    """Turn Gemini's scope_hint + inventory facts into the stored scope rule."""
    scope = {"node_type": None, "installed_before": None,
             "firmware_below": k.firmware_below, "firmware_at_least": k.firmware_at_least}

    if k.knowledge_type == "access_info" or not node_type:
        pass  # access info and unknown device types stay bound to the named devices only
    elif k.scope_hint == "all_devices_of_same_type":
        scope["node_type"] = node_type
    elif k.scope_hint == "older_devices_of_same_type":
        scope["node_type"] = node_type
        # Only keep the age limit if the observed devices really are older units
        if not observed_devices or all(is_older(d) for d in observed_devices):
            scope["installed_before"] = older_cutoff()
        else:
            print(f"  scope: 'older units' ignored, {[d['node_id'] for d in observed_devices]} are not older units")
    elif k.outcome == "failed" and observed_devices:
        # A failed attempt is a warning for similar devices, not only for the one where it happened
        scope["node_type"] = node_type
        if all(is_older(d) for d in observed_devices):
            scope["installed_before"] = older_cutoff()

    # Contradictory firmware limits (e.g. below 3.4 AND from 3.4): keep the "from" reading
    below, at_least = scope["firmware_below"], scope["firmware_at_least"]
    if below and at_least:
        from retrieve import compare_versions
        if compare_versions(below, at_least) <= 0:
            print(f"  scope: contradictory firmware limits (below {below}, from {at_least}); keeping 'from {at_least}'")
            scope["firmware_below"] = None
    return scope


def sort_key(thread: dict):
    """Threads without a timestamp go last."""
    ts = thread["messages"][0].get("timestamp")
    return (0, datetime.fromisoformat(ts).timestamp()) if ts else (1, 0)


def process(thread: dict, dry_run: bool, vocab: Vocabulary):
    if not dry_run:
        import graph  # imported here so --dry-run works without Neo4j configured
        import reconcile

    text = threads.thread_to_prompt_text(thread)
    mentioned_ids = threads.find_device_ids(thread)

    if dry_run:
        devices = [d for d in csv_inventory(INVENTORY_CSV) if d["node_id"] in mentioned_ids]
    else:
        devices = graph.get_devices(list(mentioned_ids))
    known_ids = {d["node_id"] for d in devices}
    unknown = mentioned_ids - known_ids
    if unknown and not dry_run:
        print(f"  warning: devices not in inventory: {sorted(unknown)}")

    result = extract.extract(text, device_context(devices), vocab.prompt_text())
    print(f"[{thread['thread_id']}] useful={result.useful} - {result.reason}")

    # Normalise terms against the growing vocabulary (maps near-duplicates, adds new terms)
    for k in result.knowledge:
        k.events = vocab.normalize_list(k.events, "event", thread["thread_id"])
        k.symptoms = vocab.normalize_list(k.symptoms, "symptom", thread["thread_id"])
        k.actions = vocab.normalize_list(k.actions, "action", thread["thread_id"])
        k.avoid = vocab.normalize_list(k.avoid, "action", thread["thread_id"])

    if dry_run:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        return

    graph.save_source(thread, text)  # keep the raw source even if not useful
    if not result.useful:
        graph.mark_source_done(thread["thread_id"])
        return

    for i, k in enumerate(result.knowledge, start=1):
        # Link only to devices that really exist in the inventory
        observed = sorted(set(k.device_mentions) & known_ids) or sorted(known_ids)
        observed_devices = [d for d in devices if d["node_id"] in observed]
        node_type = k.node_type or (observed_devices[0]["node_type"] if observed_devices else None)
        scope = compute_scope(k, observed_devices, node_type)

        assertion = {
            "id": f"{thread['thread_id']}-{i}",
            "source_id": thread["thread_id"],
            "knowledge_type": k.knowledge_type,
            "summary": k.summary,
            "events": list(k.events),
            "symptoms": list(k.symptoms),
            "actions": list(k.actions),
            "avoid": list(k.avoid),
            "outcome": k.outcome,
            "details": k.details,
            "author": threads.full_name(k.author, thread.get("participants", [])),
            "observed_on": observed,
            "scope_node_type": scope["node_type"],
            "scope_installed_before": scope["installed_before"],
            "scope_firmware_below": scope["firmware_below"],
            "scope_firmware_at_least": scope["firmware_at_least"],
            "confidence": BASE_CONFIDENCE[k.outcome],
            "valid_from": threads.message_timestamp(thread, k.confirmed_at_seq),
        }
        graph.save_assertion(assertion)
        graph.link_terms(assertion)
        print(f"  saved {assertion['id']}: {k.summary[:80]}...")
        reconcile.reconcile(assertion["id"])
    graph.mark_source_done(thread["thread_id"])


def main():
    global INVENTORY_CSV
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="a thread file or a folder of thread files")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--inventory", default=str(INVENTORY_CSV), help="nodes.csv used for --dry-run")
    parser.add_argument("--force", action="store_true", help="re-process threads already in Neo4j")
    parser.add_argument("--refresh", action="store_true", help="ignore the Gemini cache and call the API again")
    args = parser.parse_args()
    INVENTORY_CSV = Path(args.inventory)
    if args.refresh:
        import cache
        cache.ENABLED = False

    p = Path(args.path)
    files = sorted(p.glob("*.json")) + sorted(p.glob("*.txt")) if p.is_dir() else [p]
    loaded = []
    for f in files:
        try:
            loaded.append(threads.load_thread(f))
        except Exception as e:
            print(f"SKIP {f.name}: could not read ({e})")

    # Oldest conversation first, so knowledge builds up in the order it happened
    loaded.sort(key=sort_key)

    if not args.dry_run and not args.force:
        import graph
        done = graph.existing_source_ids()
        skipped = [t["thread_id"] for t in loaded if t["thread_id"] in done]
        loaded = [t for t in loaded if t["thread_id"] not in done]
        if skipped:
            print(f"Skipping {len(skipped)} threads already in Neo4j (use --force to redo): {', '.join(skipped)}")

    vocab = Vocabulary(use_graph=not args.dry_run).load()
    print(f"Processing {len(loaded)} threads")
    failed = []
    for t in loaded:
        try:
            process(t, args.dry_run, vocab)
        except Exception as e:
            print(f"  ERROR in {t['thread_id']}: {e.__class__.__name__}: {e}")
            failed.append(t["thread_id"])
    if failed:
        print(f"\nFailed: {', '.join(failed)}. Run the same command again to retry them.")


if __name__ == "__main__":
    main()
