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
import extract
import graph
from prompts import build_relation_prompt
from retrieve import same_knowledge


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
    if new["knowledge_type"] != "access_info" and not has_limits and all(same_knowledge(new, c) for c in candidates):
        for c in candidates:
            graph.apply_relation(new_id, c["id"], "same_knowledge", None, "same actions (decided by code)")
            print(f"  relation: {new_id} reinforces {c['id']}")
        return

    result = extract.classify_relations(build_relation_prompt(new, candidates))
    valid_ids = {c["id"] for c in candidates}
    for j in result.judgements:
        if j.existing_id not in valid_ids or j.relation == "unrelated":
            continue
        graph.apply_relation(new_id, j.existing_id, j.relation, j.firmware_below, j.reason)
        extra = f" (below {j.firmware_below})" if j.firmware_below else ""
        print(f"  relation: {new_id} {j.relation}{extra} {j.existing_id}: {j.reason}")
