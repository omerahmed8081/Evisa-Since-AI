"""Capture pipeline: conversation -> extract -> link to devices -> store -> reconcile.

    python scripts/ingest.py data/threads [--dry-run] [--force] [--refresh] [--prefilter]"""
import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

from pipeline import DATA_DIR, extract, linking, threads
from pipeline.vocabulary import Vocabulary

BASE_CONFIDENCE = {"worked": 0.7, "unknown": 0.5, "failed": 0.3}
ACCESS_INFO_CONFIDENCE = 0.7
ROLE_CONFIDENCE = {"network expert": 0.7, "noc operator": 0.7, "field engineer": 0.6}


def reporter_confidence(reporter: dict | None) -> float:
    if not reporter:
        return 0.0
    return ROLE_CONFIDENCE.get((reporter.get("role") or "").strip().lower(), 0.5)


INVENTORY_CSV = DATA_DIR / "inventory" / "nodes.csv"


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
        pass
    elif k.scope_hint == "all_devices_of_same_type":
        scope["node_type"] = node_type
    elif k.scope_hint == "older_devices_of_same_type":
        scope["node_type"] = node_type
        if not observed_devices or all(is_older(d) for d in observed_devices):
            scope["installed_before"] = older_cutoff()
        else:
            print(f"  scope: 'older units' ignored, {[d['node_id'] for d in observed_devices]} are not older units")
    elif k.outcome == "failed" and observed_devices:
        scope["node_type"] = node_type
        if all(is_older(d) for d in observed_devices):
            scope["installed_before"] = older_cutoff()

    below, at_least = scope["firmware_below"], scope["firmware_at_least"]
    if below and at_least:
        from pipeline.retrieve import compare_versions
        if compare_versions(below, at_least) <= 0:
            if k.actions:
                print(f"  scope: contradictory firmware limits; tip has actions -> workaround, keeping 'below {below}'")
                scope["firmware_at_least"] = None
            else:
                print(f"  scope: contradictory firmware limits; tip has no actions -> fix, keeping 'from {at_least}'")
                scope["firmware_below"] = None
    return scope


def sort_key(thread: dict):
    """Threads without a timestamp go last."""
    ts = thread["messages"][0].get("timestamp")
    return (0, datetime.fromisoformat(ts).timestamp()) if ts else (1, 0)


def process(thread: dict, dry_run: bool, vocab: Vocabulary) -> dict:
    """Run one conversation through the pipeline. Returns
    {"thread_id", "useful", "reason", "tips": [{"id", "summary", "devices", "knowledge_type", "outcome"}]}"""
    if not dry_run:
        from pipeline import graph
        from pipeline import reconcile

    text = threads.thread_to_prompt_text(thread)
    inv = linking.Inventory.from_csv(Path(INVENTORY_CSV)) if dry_run else linking.Inventory.from_graph()
    raw = (thread.get("subject") or "") + "\n" + "\n".join(m["text"] for m in thread["messages"])
    match = inv.resolve(raw)
    mentioned_ids = threads.find_device_ids(thread) | match.ids | set(match.aliases)

    if dry_run:
        devices = [d for d in csv_inventory(INVENTORY_CSV) if d["node_id"] in mentioned_ids]
    else:
        devices = graph.get_devices(list(mentioned_ids))
    known_ids = {d["node_id"] for d in devices}
    unknown = (mentioned_ids | match.unknown_ids) - known_ids
    if unknown and not dry_run:
        print(f"  warning: devices not in inventory: {sorted(unknown)}")
    if match.aliases:
        print(f"  nicknames: {', '.join(f'{a!r} = {n}' for n, a in match.aliases.items())}")
    if not known_ids and match.locations:
        print(f"  no device named; places mentioned: {', '.join(match.locations)}")

    result = extract.extract(text, device_context(devices), vocab.prompt_text())
    print(f"[{thread['thread_id']}] useful={result.useful} - {result.reason}")

    for k in result.knowledge:
        k.events = vocab.normalize_list(k.events, "event", thread["thread_id"])
        k.symptoms = vocab.normalize_list(k.symptoms, "symptom", thread["thread_id"])
        k.actions = vocab.normalize_list(k.actions, "action", thread["thread_id"])
        k.avoid = vocab.normalize_list(k.avoid, "action", thread["thread_id"])

    summary = {"thread_id": thread["thread_id"], "useful": result.useful, "reason": result.reason, "tips": []}
    if dry_run:
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        summary["tips"] = [{"id": None, "summary": k.summary, "devices": k.device_mentions,
                            "knowledge_type": k.knowledge_type, "outcome": k.outcome} for k in result.knowledge]
        return summary

    graph.save_source(thread, text)
    if not result.useful:
        graph.mark_source_done(thread["thread_id"])
        return summary

    for i, k in enumerate(result.knowledge, start=1):
        mentions = {inv.aliases.get(m.strip().lower(), m.strip().upper()) for m in k.device_mentions}
        observed = sorted(mentions & known_ids)
        if not observed and (k.knowledge_type == "access_info" or k.scope_hint == "this_device_only"):
            observed = sorted(known_ids)
        links = [{"node_id": n, "linked_by": "alias" if n in match.aliases and n not in match.ids else "id",
                  "link_confidence": linking.LINK_CONFIDENCE["alias" if n in match.aliases and n not in match.ids else "id"],
                  "via": f"called '{match.aliases[n]}' in the conversation" if n in match.aliases and n not in match.ids else None}
                 for n in observed]
        site_links = []
        if not known_ids and match.locations:
            loc = linking.location_links(match, inv, k.node_type)
            links, site_links = loc["devices"], loc["sites"]
            observed = [l["node_id"] for l in links]
            print(f"  {loc['note']}")
        observed_devices = [inv.devices[n] for n in observed if n in inv.devices]
        if not dry_run:
            observed_devices = graph.get_devices(observed) if observed else []
        site_types = {inv.devices[c]["node_type"] for s in site_links for c in s["candidates"]}
        node_type = k.node_type or (observed_devices[0]["node_type"] if observed_devices else None) \
            or (next(iter(site_types)) if len(site_types) == 1 else None)
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
            "links": links,
            "site_links": site_links,
            "scope_node_type": scope["node_type"],
            "scope_installed_before": scope["installed_before"],
            "scope_firmware_below": scope["firmware_below"],
            "scope_firmware_at_least": scope["firmware_at_least"],
            "confidence": BASE_CONFIDENCE[k.outcome] if k.outcome == "failed" else max(
                ACCESS_INFO_CONFIDENCE if k.knowledge_type == "access_info" else BASE_CONFIDENCE[k.outcome],
                reporter_confidence(thread.get("reported_by"))),
            "valid_from": threads.message_timestamp(thread, k.confirmed_at_seq),
        }
        graph.save_assertion(assertion)
        graph.link_terms(assertion)
        print(f"  saved {assertion['id']}: {k.summary[:80]}...")
        reconcile.reconcile(assertion["id"], thread.get("reported_by"))
        summary["tips"].append({"id": assertion["id"], "summary": k.summary, "devices": observed,
                                "knowledge_type": k.knowledge_type, "outcome": k.outcome})
    graph.mark_source_done(thread["thread_id"])
    return summary


def run_prefilter(loaded: list[dict], dry_run: bool) -> list[dict]:
    """Drop conversations the local pre-filter is sure are noise. Skipped ones are still saved as
    Sources (marked prefiltered) so nothing disappears without a trace."""
    from pipeline.prefilter import Prefilter
    pf = Prefilter()
    print(f"Pre-filter: rules{' + classifier (threshold %s)' % pf.threshold if pf.model else ' only (no trained model)'}")
    keep, skipped = [], 0
    for t in loaded:
        d = pf.decide(t)
        if d["keep"]:
            keep.append(t)
            continue
        skipped += 1
        why = f"score {d['score']}" + (f", p_useful {d['p_useful']}" if d["p_useful"] is not None else "")
        print(f"  [{t['thread_id']}] skipped by {d['stage']} ({why})")
        if not dry_run:
            from pipeline import graph
            graph.save_source(t, threads.thread_to_prompt_text(t))
            graph.mark_source_prefiltered(t["thread_id"], d["stage"], d["score"], d["p_useful"])
    print(f"Pre-filter: {skipped} skipped, {len(keep)} sent to Gemini")
    return keep


def main():
    global INVENTORY_CSV
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="a thread file or a folder of thread files")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--inventory", default=str(INVENTORY_CSV), help="nodes.csv used for --dry-run")
    parser.add_argument("--force", action="store_true", help="re-process threads already in Neo4j")
    parser.add_argument("--refresh", action="store_true", help="ignore the Gemini cache and call the API again")
    parser.add_argument("--prefilter", action="store_true",
                        help="run the local pre-filter first; skipped conversations are never sent to Gemini")
    args = parser.parse_args()
    INVENTORY_CSV = Path(args.inventory)
    if args.refresh:
        from pipeline import cache
        cache.ENABLED = False

    p = Path(args.path)
    files = sorted(p.glob("*.json")) + sorted(p.glob("*.txt")) if p.is_dir() else [p]
    loaded = []
    for f in files:
        try:
            loaded.append(threads.load_thread(f))
        except Exception as e:
            print(f"SKIP {f.name}: could not read ({e})")

    loaded.sort(key=sort_key)

    if not args.dry_run and not args.force:
        from pipeline import graph
        done = graph.existing_source_ids()
        skipped = [t["thread_id"] for t in loaded if t["thread_id"] in done]
        loaded = [t for t in loaded if t["thread_id"] not in done]
        if skipped:
            print(f"Skipping {len(skipped)} threads already in Neo4j (use --force to redo): {', '.join(skipped)}")

    if args.prefilter:
        loaded = run_prefilter(loaded, args.dry_run)

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
