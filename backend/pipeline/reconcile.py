"""
Keep older knowledge up to date when new knowledge arrives (Elisa's valid_from / valid_to idea).

For each new tip:
  1. find older, still-valid tips about the same device, or the same device type with shared terms,
  2. decide how they relate:
       - by CODE (no API call) when the answer is obvious: a failed attempt stands alone;
         a plain repeat of the same fix just reinforces it,
       - by GEMINI otherwise (one call, cached): same / narrows_scope / supersedes / conflicts / unrelated,
  3. apply it in the graph:
       same_knowledge -> (new)-[:REINFORCES]->(old)
       narrows_scope  -> old.scope_firmware_below = "3.4"        (old stays valid for older firmware)
       supersedes     -> old.valid_to = new.valid_from            (old is no longer true)
       conflicts      -> both marked status = 'disputed'
"""
from pipeline import extract
from pipeline import graph
from pipeline.prompts import build_relation_prompt
from pipeline.retrieve import same_knowledge


def reconcile(new_id: str):
    new = graph.get_assertion(new_id)
    if not new:
        return
    if new["outcome"] == "failed":
        return  # failed attempts are kept as their own warnings

    candidates = [c for c in graph.candidate_assertions(new) if c["outcome"] != "failed"]
    if not candidates:
        return

    has_limits = new.get("scope_firmware_below") or new.get("scope_firmware_at_least")
    to_ask = candidates
    if new["knowledge_type"] != "access_info" and not has_limits:
        # Plain repeats of the same fix are decided by code (no API call) ...
        same = [c for c in candidates if same_knowledge(new, c)]
        for c in same:
            graph.apply_relation(new_id, c["id"], "same_knowledge", None, "same actions (decided by code)")
            print(f"  relation: {new_id} reinforces {c['id']}")
        # ... and only the remaining, different tips go to Gemini (possible conflicts)
        to_ask = [c for c in candidates if c not in same]
    if not to_ask:
        return

    result = extract.classify_relations(build_relation_prompt(new, to_ask))
    valid_ids = {c["id"] for c in to_ask}
    done = set()
    for j in result.judgements:
        if j.existing_id not in valid_ids or j.relation == "unrelated":
            continue
        # A narrowing or superseding decision applies to the whole group of tips that are the
        # same knowledge (linked by REINFORCES), so Gemini doesn't have to judge each copy right.
        targets = [j.existing_id]
        if j.relation in ("narrows_scope", "supersedes"):
            targets = graph.same_knowledge_cluster(j.existing_id) or targets
        for target in targets:
            if (target, j.relation) in done or target == new_id:
                continue
            done.add((target, j.relation))
            graph.apply_relation(new_id, target, j.relation, j.firmware_below, j.reason)
            extra = f" (below {j.firmware_below})" if j.firmware_below else ""
            via = "" if target == j.existing_id else f" [same knowledge as {j.existing_id}]"
            print(f"  relation: {new_id} {j.relation}{extra} {target}{via}: {j.reason}")
