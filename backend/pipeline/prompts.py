"""
The instructions sent to Gemini. Written once, reused for every conversation.
The examples are deliberately NOT from our dataset, so they don't inflate test scores.
"""

SYSTEM_INSTRUCTION = """You read conversations between telecom network engineers (Teams chats, emails,
phone-call transcripts) and extract reusable operational knowledge for a knowledge graph.
Conversations may be in Finnish, English or mixed, with slang, typos and emojis.

STEP 1 - Is the conversation useful?
Useful = it contains knowledge another engineer could reuse later:
  - a fix or workaround, a diagnosis rule, a known false alarm, a hardware compatibility rule,
    a practical tip,
  - access information: how to physically get to equipment (keys, lockbox or gate codes,
    road or seasonal conditions),
  - advice that was tried and FAILED (outcome "failed"): knowing what does not work saves time.
    This is useful EVEN IF the conversation ends unresolved or with a ticket being opened:
    "replaced the SFP again, same problem" is a failed attempt worth keeping,
  - a claim that contradicts earlier advice, even if unconfirmed (outcome "unknown").
Not useful = small talk, scheduling, shift swaps, status updates ("all done, heading back"),
or speculation that ends without any conclusion. Mentioning a device does not make it useful.

STEP 2 - Extract each distinct piece of knowledge.
- One item per distinct fix, rule or access fact. Do not split one fix into several items;
  put related specifics of the same fix into one item.
- events / symptoms / actions / avoid: use the CURRENT VOCABULARY given with the conversation.
  Map by MEANING, not by exact words. Examples: "changed the optic" / "vaihdoin SFP:n" =
  SFP_REPLACEMENT; "disable and enable the port" / "bounce it" / "ota portti alas ja nosta
  takaisin" = BOUNCE_INTERFACE. Only if no term fits, create a NEW term: UPPER_SNAKE_CASE,
  1-4 words, generic and reusable (no device IDs, names or dates).
- symptoms: include what the field engineer observes and reports, not only what the expert says.
- avoid: include what the expert advises against or talks the engineer out of.
- actions: the recommended steps in order. For failed advice, the action that was tried.
- outcome: worked = success confirmed in the conversation or the author says it has worked
  before; failed = tried and did not help; unknown = no result reported. For access information
  the outcome is always "unknown".
- known false alarms: if the expert says no visit or action is needed, include NO_DISPATCH_NEEDED
  in actions.
- author: the person who gave the knowledge (not the person asking).
- device_mentions: only devices where the knowledge was actually observed or applied in THIS
  conversation. Do not include devices mentioned as earlier cases ("same as on TRN-042 last
  spring"), for comparison, or as still pending.
- scope_hint:
    "older_devices_of_same_type" when the knowledge is tied to old/older units ("these old
    units", "noissa vanhoissa", or the expert asks "is this one of the older units?" and it is),
    "all_devices_of_same_type" when it is stated as generally true for that kind of device
    ("on those routers it's always...", "it's usually a dirty connector", "almost always"),
    "this_device_only" otherwise, and always for access information.
- Firmware limits: firmware_below if the knowledge is only needed below a version;
  firmware_at_least if it only holds from a version upward. Use just the version, e.g. "3.4".
  NEVER set both to the same version. A message like "fixed in firmware 3.4, the workaround is only
  needed on older software" is knowledge about the FIX: set firmware_at_least "3.4", leave actions
  empty, and do not repeat the old workaround as a separate item.
- details: specifics the terms can't hold (codes, part numbers, thresholds, conditions),
  copied exactly. For access information the code or key location MUST be in details.
- summary: English, one or two sentences, actionable.
- Only extract what the conversation actually says. Never add your own technical advice.

The prompt may include device context from the inventory; use it to fill node_type.
"""

FEW_SHOT_EXAMPLES = """### Example 1 (useful: fix with field-engineer symptoms and an avoid)
Channel: teams
[seq 1 | 2024-02-01T10:02:00+02:00 | Laura Lahti (Field Engineer)]
AGG-099 port 3 keeps flapping since we moved the rack. Light levels look fine
[seq 2 | 2024-02-01T10:04:00+02:00 | Antti Aalto (Network Expert)]
on those routers it's nearly always the patch cord getting bent in the move
[seq 3 | 2024-02-01T10:05:00+02:00 | Laura Lahti (Field Engineer)]
should I swap the line card?
[seq 4 | 2024-02-01T10:06:00+02:00 | Antti Aalto (Network Expert)]
no, swap the cord first
[seq 5 | 2024-02-01T10:15:00+02:00 | Laura Lahti (Field Engineer)]
new cord, stable now 👍

Expected output:
{"useful": true, "reason": "Expert gives a confirmed fix for link flapping after a rack move.",
 "knowledge": [{"knowledge_type": "troubleshooting_rule",
  "summary": "On aggregation routers, port flapping after equipment is moved is usually a bent patch cable; replace the cable before replacing the line card.",
  "device_mentions": ["AGG-099"], "node_type": "aggregation_router", "scope_hint": "all_devices_of_same_type",
  "firmware_below": null, "firmware_at_least": null, "events": ["MAINTENANCE"],
  "symptoms": ["LINK_FLAPPING", "OPTICAL_LEVELS_NORMAL"],
  "actions": ["REPLACE_PATCH_CABLE"], "avoid": ["REPLACE_LINE_CARD"], "outcome": "worked",
  "author": "Antti Aalto", "source_message_seqs": [2, 4, 5], "confirmed_at_seq": 5, "details": null}]}

### Example 2 (useful: failed attempt)
Channel: teams
[seq 1 | 2024-04-11T13:20:00+03:00 | Pekka Pylväs (Field Engineer)]
BTS-299 alarm keeps coming back, any idea?
[seq 2 | 2024-04-11T13:22:00+03:00 | Mikko Mäkelä (Field Engineer)]
try resetting the alarm module, worked for me once
[seq 3 | 2024-04-11T13:40:00+03:00 | Pekka Pylväs (Field Engineer)]
did that, alarm back after 10 min 😕

Expected output:
{"useful": true, "reason": "A suggested fix was tried and did not help.",
 "knowledge": [{"knowledge_type": "troubleshooting_rule",
  "summary": "Resetting the alarm module did not stop a recurring alarm on a base station; the alarm returned after about 10 minutes.",
  "device_mentions": ["BTS-299"], "node_type": "base_station", "scope_hint": "this_device_only",
  "firmware_below": null, "firmware_at_least": null, "events": [], "symptoms": ["RECURRING_ALARM"],
  "actions": ["RESET_ALARM_MODULE"], "avoid": [], "outcome": "failed",
  "author": "Mikko Mäkelä", "source_message_seqs": [2, 3], "confirmed_at_seq": 3,
  "details": "Alarm returned about 10 minutes after the reset."}]}

### Example 3 (not useful)
Channel: teams
[seq 1 | 2024-03-05T11:30:00+02:00 | Pekka Pylväs (Field Engineer)]
lounas klo 12? oon vielä AGG-099:llä
[seq 2 | 2024-03-05T11:31:00+02:00 | Laura Lahti (Field Engineer)]
joo, nähdään

Expected output:
{"useful": false, "reason": "Lunch arrangement, no operational knowledge.", "knowledge": []}
"""


def build_prompt(conversation_text: str, device_context: str, vocabulary_text: str) -> str:
    return (
        FEW_SHOT_EXAMPLES
        + "\n### Current vocabulary (reuse these terms where they fit)\n"
        + vocabulary_text
        + "\n\n### Now process this conversation\n"
        + (f"Device context from inventory:\n{device_context}\n\n" if device_context else "")
        + conversation_text
    )


RELATION_INSTRUCTION = """You maintain a knowledge graph of operational knowledge for telecom network engineers.
A NEW tip was just captured from a conversation. Decide how it relates to each EXISTING tip
(captured earlier from other conversations). Give exactly one judgement per existing tip:

- same_knowledge: the new tip repeats or confirms the existing tip (same problem, same fix),
  possibly on another device or with extra details.
- narrows_scope: the existing tip is still true, but the new tip says it only applies to some
  devices now, e.g. "fixed in firmware 3.4, the workaround is only needed below 3.4".
  Set firmware_below to that version ("3.4"). Use this for every existing tip describing that
  workaround.
- supersedes: the new tip makes the existing tip no longer true at all, e.g. "the gate code has
  changed, the old code no longer works".
- conflicts: the new tip gives a DIFFERENT diagnosis or fix for the SAME problem (same kind of
  device, same symptoms) as the existing tip, and nothing settles who is right. Example: one expert
  says winter link drops are caused by ice on the radome, another says they are caused by the
  power supply: that is a conflict. Two fixes for clearly different problems are NOT a conflict.
- unrelated: different problem, or no meaningful connection.

Judge only from what the tips say. Do not invent relations."""


def build_relation_prompt(new: dict, existing: list[dict]) -> str:
    def fmt(t: dict) -> str:
        lines = [f"id: {t['id']}", f"captured: {t.get('valid_from')}", f"type: {t.get('knowledge_type')}",
                 f"devices: {', '.join(t.get('devices') or []) or '-'}", f"summary: {t.get('summary')}"]
        if t.get("outcome"):
            lines.append(f"outcome: {t['outcome']}")
        if t.get("events"):
            lines.append(f"happened before: {', '.join(t['events'])}")
        if t.get("symptoms"):
            lines.append(f"symptoms: {', '.join(t['symptoms'])}")
        if t.get("actions"):
            lines.append(f"actions: {', '.join(t['actions'])}")
        if t.get("details"):
            lines.append(f"details: {t['details']}")
        if t.get("scope_firmware_below") or t.get("scope_firmware_at_least"):
            lines.append(f"firmware: below={t.get('scope_firmware_below')} from={t.get('scope_firmware_at_least')}")
        return "\n".join(lines)

    return ("### NEW tip\n" + fmt(new) + "\n\n### EXISTING tips\n"
            + "\n\n".join(fmt(e) for e in existing))
