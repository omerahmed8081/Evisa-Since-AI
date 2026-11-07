"""
Evaluate the graph against data/ground_truth.json. Uses NO Gemini calls.

  python evaluate.py                 # full report
  python evaluate.py --details       # also list every mismatch per thread

Sections:
  1. Capture   - per conversation: useful/noise decision, devices linked, scope, outcome, actions
  2. Change    - did later messages update earlier knowledge as expected (merge, narrow, supersede, conflict)
  3. Retrieval - demo questions: does the right knowledge come back for the right device (PASS/FAIL)
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

import graph
import retrieve

load_dotenv()
GT_PATH = Path("data/ground_truth.json")


def jaccard(a, b) -> float:
    a, b = set(a or []), set(b or [])
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def load_graph():
    rows = graph.run("""
        MATCH (a:Assertion)
        OPTIONAL MATCH (a)-[:OBSERVED_ON]->(d:Device)
        OPTIONAL MATCH (a)-[:BY]->(p:Person)
        RETURN a {.id, .knowledge_type, .outcome, .actions, .symptoms, .scope_node_type,
                  .scope_firmware_below, .scope_firmware_at_least, .status,
                  installed_before: toString(a.scope_installed_before),
                  valid_to: toString(a.valid_to)} AS a,
               collect(DISTINCT d.node_id) AS devices, head(collect(p.name)) AS author
    """)
    by_thread = {}
    for r in rows:
        a = dict(r["a"])
        a["devices"], a["author"] = r["devices"], r["author"]
        by_thread.setdefault(a["id"].rsplit("-", 1)[0], []).append(a)
    processed = {r["id"] for r in graph.run("MATCH (s:Source) WHERE s.processed = true RETURN s.id AS id")}
    links = {(r["n"], r["c"]) for r in graph.run("MATCH (n)-[:REINFORCES]->(c) RETURN n.id AS n, c.id AS c")}
    new_terms = [r["t"] for r in graph.run("MATCH (t:Term {status:'new'}) RETURN t.category + ':' + t.name AS t ORDER BY t")]
    return by_thread, processed, links, new_terms


def best_match(gt_k: dict, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    return max(candidates, key=lambda a: (jaccard(gt_k.get("actions"), a.get("actions")),
                                          a.get("knowledge_type") == gt_k.get("knowledge_type")))


def capture_section(gt, by_thread, processed, show_details):
    print("\n=== 1. CAPTURE (extraction + linking), per conversation ===")
    counts = {k: [0, 0] for k in ("useful_decision", "devices", "scope", "outcome", "actions>=0.5", "symptoms>=0.5")}
    problems = []
    for g in gt:
        tid = g["thread_id"]
        if tid not in processed:
            problems.append(f"{tid}: NOT PROCESSED (run ingest.py again)")
            continue
        found = by_thread.get(tid, [])
        counts["useful_decision"][1] += 1
        if bool(found) == g["useful"]:
            counts["useful_decision"][0] += 1
        else:
            problems.append(f"{tid}: useful expected {g['useful']}, got {bool(found)}")
        if not (g["useful"] and found):
            continue
        k = g["knowledge"]
        a = best_match(k, found)
        exp_scope = k.get("scope") or {}
        checks = {
            "devices": set(a["devices"]) == set(k.get("observed_on") or []),
            "scope": (a.get("scope_node_type"), a.get("installed_before")) ==
                     (exp_scope.get("node_type"), exp_scope.get("installed_before")),
            "outcome": a.get("outcome") == k.get("outcome"),
            "actions>=0.5": jaccard(k.get("actions"), a.get("actions")) >= 0.5,
            "symptoms>=0.5": (not k.get("symptoms")) or
                             len(set(k["symptoms"]) & set(a.get("symptoms") or [])) / len(k["symptoms"]) >= 0.5,
        }
        for name, ok in checks.items():
            counts[name][1] += 1
            counts[name][0] += ok
        if show_details:
            bad = [n for n, ok in checks.items() if not ok]
            if bad:
                problems.append(
                    f"{tid} [{a['id']}]: " + "; ".join(
                        {"devices": f"devices {sorted(a['devices'])} vs {sorted(k.get('observed_on') or [])}",
                         "scope": f"scope ({a.get('scope_node_type')}, {a.get('installed_before')}) vs "
                                  f"({exp_scope.get('node_type')}, {exp_scope.get('installed_before')})",
                         "outcome": f"outcome {a.get('outcome')} vs {k.get('outcome')}",
                         "actions>=0.5": f"actions {a.get('actions')} vs {k.get('actions')}",
                         "symptoms>=0.5": f"symptoms {a.get('symptoms')} vs {k.get('symptoms')}"}[n] for n in bad))
    for name, (ok, total) in counts.items():
        pct = f"{100 * ok / total:.0f}%" if total else "-"
        print(f"  {name:16} {ok:>2}/{total:<2} {pct}")
    for p in problems:
        print(f"  - {p}")
    return counts


def change_section(gt, by_thread, links):
    print("\n=== 2. CHANGE OVER TIME (later messages updating earlier knowledge) ===")
    ok_count = total = 0
    for g in gt:
        for eff in g.get("expected_effects") or []:
            target, source = eff["target"], g["thread_id"]
            t_k = next((x["knowledge"] for x in gt if x["thread_id"] == target), None) or {}
            t_a = best_match(t_k, by_thread.get(target, []))
            s_a = best_match(g.get("knowledge") or {}, by_thread.get(source, []))
            if not t_a:
                result, ok = f"target {target} not in graph", False
            elif eff.get("action") == "merge":
                linked = s_a and ((s_a["id"], t_a["id"]) in links or retrieve.same_knowledge(
                    {**s_a, "knowledge_type": s_a["knowledge_type"]}, t_a))
                result, ok = ("merged" if linked else "NOT merged"), bool(linked)
            elif "scope.firmware_below" in (eff.get("set") or {}):
                want = eff["set"]["scope.firmware_below"]
                got = t_a.get("scope_firmware_below")
                ok = bool(got) and retrieve.compare_versions(got, want) == 0 and t_a.get("valid_to") in (None, "None")
                result = f"firmware_below={got} (want {want}), valid_to={t_a.get('valid_to')} (want empty)"
            elif "status" in (eff.get("set") or {}):
                ok = t_a.get("status") == eff["set"]["status"]
                result = f"status={t_a.get('status')} (want {eff['set']['status']})"
            elif eff.get("valid_to"):
                got = t_a.get("valid_to")
                ok = got not in (None, "None") and str(got)[:10] == eff["valid_to"][:10]
                result = f"valid_to={got} (want {eff['valid_to'][:16]})"
            else:
                continue
            total += 1
            ok_count += ok
            print(f"  {'PASS' if ok else 'FAIL'}  {source} -> {target}: {result}")
    print(f"  {ok_count}/{total} expected changes applied")
    return ok_count, total


def retrieval_section():
    print("\n=== 3. RETRIEVAL (demo questions) ===")

    def res(node):
        return retrieve.find_knowledge(node)["results"]

    def has_action(rs, action, outcome=None):
        return any(action in (r["actions"] or []) and (outcome is None or r["outcome"] == outcome) for r in rs)

    def text_has(rs, s):
        return any(s in (r["summary"] + " ".join(r["details"])) for r in rs)

    cache = {}

    def R(node):
        if node not in cache:
            cache[node] = res(node)
        return cache[node]

    def bounce_sources(node):
        for r in R(node):
            if "BOUNCE_INTERFACE" in (r["actions"] or []) and r["outcome"] != "failed":
                return len(r["sources"])
        return 0

    checks = [
        ("TRN-042 gets the bounce fix (observed there)", lambda: has_action(R("TRN-042"), "BOUNCE_INTERFACE", "worked")),
        ("TRN-042 bounce fix merges >= 3 sources", lambda: bounce_sources("TRN-042") >= 3),
        ("TRN-042 gets the barrier key info (code 2580)", lambda: text_has(R("TRN-042"), "2580")),
        ("TRN-042 warns: reboot was tried and failed", lambda: has_action(R("TRN-042"), "REBOOT_UNIT", "failed")),
        ("TRN-042 warns: new SFP was tried and failed", lambda: has_action(R("TRN-042"), "REPLACE_SFP", "failed")),
        ("TRN-031 (older, fw 3.3) gets the bounce fix (reuse)", lambda: has_action(R("TRN-031"), "BOUNCE_INTERFACE", "worked")),
        ("TRN-077 (fw 3.4) does NOT get the bounce workaround", lambda: not has_action(R("TRN-077"), "BOUNCE_INTERFACE", "worked")),
        ("TRN-118 (newer) gets no older-unit tips", lambda: not has_action(R("TRN-118"), "BOUNCE_INTERFACE")
                                                         and not has_action(R("TRN-118"), "SET_CONSOLE_BAUD_9600")),
        ("TRN-112 gets the hot-swap tip (all transmission nodes)", lambda: has_action(R("TRN-112"), "WAIT_INVENTORY_REFRESH")),
        ("BTS-233 (fw 2.4) gets the cold restart fix", lambda: has_action(R("BTS-233"), "COLD_RESTART_BASEBAND", "worked")),
        ("BTS-210 (fw 2.6) does NOT get the cold restart workaround", lambda: not has_action(R("BTS-210"), "COLD_RESTART_BASEBAND", "worked")),
        ("BTS-210 gets the NEW gate code 9035", lambda: text_has(R("BTS-210"), "9035")),
        ("BTS-210 does NOT get the OLD gate code 4471 as current", lambda: not any("4471" in r["summary"] and "9035" not in r["summary"] + " ".join(r["details"]) for r in R("BTS-210"))),
        ("AGG-003 gets the patch cable fix learned on AGG-012", lambda: has_action(R("AGG-003"), "REPLACE_PATCH_CABLE", "worked")),
        ("MW-405 shows the ice/PSU advice as disputed", lambda: any(r["disputed"] for r in R("MW-405"))),
    ]
    passed = 0
    for name, fn in checks:
        try:
            ok = bool(fn())
        except Exception as e:
            ok, name = False, f"{name} (error: {e})"
        passed += ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"  {passed}/{len(checks)} retrieval checks passed")
    return passed, len(checks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))
    by_thread, processed, links, new_terms = load_graph()
    print(f"Graph: {sum(len(v) for v in by_thread.values())} tips from {len(processed)} processed conversations; "
          f"answer key: {len(gt)} conversations")
    capture_section(gt, by_thread, processed, args.details)
    change_section(gt, by_thread, links)
    retrieval_section()
    print(f"\nVocabulary terms added by Gemini during ingest ({len(new_terms)}): {', '.join(new_terms) or '-'}")


if __name__ == "__main__":
    main()
