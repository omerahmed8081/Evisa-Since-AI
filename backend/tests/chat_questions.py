"""
End-to-end chat test: sends the 4 demo questions to the RUNNING API and checks the answers.

  1. start the API in another terminal:   uvicorn api.main:app --port 8000
  2. python tests/chat_questions.py                  # all 4 questions
     python tests/chat_questions.py --show           # also print the full answers
     python tests/chat_questions.py --url http://localhost:8001

Uses only the Python standard library. Costs at most 2 Gemini calls per question
(understand + answer), 0 when the same question was asked before (cache/api_*).

What is checked per question:
  - the API understood the device (Step A, not the regex fallback)
  - the right knowledge cards come back (Step B, from Neo4j)
  - Gemini wrote the answer (Step C, not the template fallback) and it mentions the key fact
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

QUESTIONS = [
    {
        "name": "TRN-042 · Finnish · SFP swapped, no traffic",
        "message": "TRN-042: vaihdoin SFP:n, linkki on ylhäällä ja hälytykset poistuivat, "
                   "mutta liikennelaskurit ovat nollassa. Mitä teen?",
        "device": "TRN-042",
    },
    {
        "name": "TRN-077 · newer firmware, same symptom",
        "message": "TRN-077: replaced the SFP, link is up and alarms cleared but traffic counters stay at zero. What should I do?",
        "device": "TRN-077",
    },
    {
        "name": "BTS-210 · site access",
        "message": "How do I get into the BTS-210 site? What is the gate code?",
        "device": "BTS-210",
    },
    {
        "name": "MW-405 · cold weather link flapping",
        "message": "MW-405 keeps flapping since the cold weather started. Any known fix?",
        "device": "MW-405",
    },
]


# ---------- helpers ----------
def all_cards(cards):
    """Cards plus the ones nested under 'Experts disagree'."""
    for c in cards:
        yield c
        yield from c.get("conflicts_with") or []


def card_text(c):
    return " ".join([c.get("summary") or "", c.get("details") or "", " ".join(c.get("actions_text") or [])])


def has_action(cards, action, outcome=None):
    return any(action in (c.get("actions") or []) and (outcome is None or c["outcome"] == outcome) for c in all_cards(cards))


def failed_actions(cards):
    """Actions that were tried and failed: own failed cards + failed attempts attached to a fix."""
    out = set()
    for c in all_cards(cards):
        if c["outcome"] == "failed":
            out |= set(c.get("actions") or [])
        for f in c.get("related_failed") or []:
            out.add(" ".join(f.get("actions_text") or []) + " " + f.get("summary", ""))
    return " ".join(out).upper()


def checks_for(q, meta, cards, answer):
    """[(description, passed)] for one question."""
    ids = meta.get("resolved_nodes") or []
    gemini_answer = bool(answer.strip()) and not (cards and answer.startswith(f"**{cards[0]['summary']}**"))
    common = [
        (f"device understood as {q['device']}", ids == [q["device"]]),
        ("Step A done by Gemini (not regex fallback)", meta.get("understood_by") == "gemini"),
        ("at least one knowledge card", len(cards) > 0),
        ("Step C answer written by Gemini (not template)", gemini_answer),
    ]
    d = q["device"]
    if d == "TRN-042":
        failed = failed_actions(cards)
        return common + [
            ("bounce-interface fix that worked", has_action(cards, "BOUNCE_INTERFACE", "worked")),
            ("warns that reboot / new SFP already failed",
             "REBOOT" in failed or "UUDELLEENK" in failed or "REPLACE_SFP" in failed or "SFP" in failed),
            ("no site-access cards for a troubleshooting question",
             all(c["knowledge_type"] != "access_info" for c in cards)),
            ("answer is in Finnish", any(w in answer.lower() for w in (" ja ", "liitäntä", "portti", " ei ", "älä"))),
        ]
    if d == "TRN-077":
        bounce = [c for c in all_cards(cards) if "BOUNCE_INTERFACE" in (c.get("actions") or []) and c["outcome"] == "worked"]
        return common + [
            ("bounce workaround NOT offered as a current fix (fw 3.4 fixed it)",
             all(c["status"] == "outdated" or c.get("scope_note") for c in bounce)),
        ]
    if d == "BTS-210":
        return common + [
            ("only site-access cards", all(c["knowledge_type"] == "access_info" for c in cards)),
            ("new gate code 9035 in the cards", any("9035" in card_text(c) for c in all_cards(cards))),
            ("answer gives 9035", "9035" in answer),
            ("old code 4471 not given as the current one", "4471" not in answer or "9035" in answer),
        ]
    if d == "MW-405":
        return common + [
            ("shows the experts disagree (disputed / conflicting tip)",
             any(c["status"] == "disputed" or c.get("conflicts_with") for c in cards)),
        ]
    return common


def ask(url, message):
    """POST /api/chat (streamed) -> (meta, answer, cards, error, seconds)."""
    req = urllib.request.Request(f"{url}/api/chat", data=json.dumps({"message": message}).encode(),
                                 headers={"content-type": "application/json", "accept": "text/event-stream"})
    meta, cards, tokens, error = {}, [], [], None
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        event = None
        for raw in r:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if event == "meta":
                    meta = data
                elif event == "token":
                    tokens.append(data["text"])
                elif event == "cards":
                    cards = data["cards"]
                elif event == "error":
                    error = data.get("message")
    return meta, "".join(tokens), cards, error, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--show", action="store_true", help="print the full answers")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    try:
        with urllib.request.urlopen(f"{url}/api/health?deep=true", timeout=30) as r:
            health = json.loads(r.read())
        print(f"API health: {json.dumps(health)}\n")
    except (urllib.error.URLError, ConnectionError) as e:
        print(f"Cannot reach the API at {url} ({e}).\nStart it first:  uvicorn api.main:app --port 8000")
        sys.exit(2)

    total_ok = total = 0
    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i}/{len(QUESTIONS)}] {q['name']}")
        try:
            meta, answer, cards, error, secs = ask(url, q["message"])
        except Exception as e:
            print(f"  FAIL  request failed: {e.__class__.__name__}: {e}\n")
            total += 1
            continue
        results = checks_for(q, meta, cards, answer)
        if error:
            results.append((f"no stream error ({error})", False))
        for desc, ok in results:
            print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
        print(f"  ({secs:.1f}s, {len(cards)} cards: {', '.join(c['assertion_id'] + '/' + c['status'] for c in cards)})")
        if args.show or not all(ok for _, ok in results):
            print("  answer: " + answer.replace("\n", "\n          ")[:1500])
        print()
        total_ok += sum(ok for _, ok in results)
        total += len(results)

    print(f"{total_ok}/{total} chat checks passed")
    sys.exit(0 if total_ok == total else 1)


if __name__ == "__main__":
    main()
