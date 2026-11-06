"""
The instructions sent to Gemini. Written once, reused for every conversation.
The examples are deliberately NOT from our dataset, so they don't inflate test scores.
"""

SYSTEM_INSTRUCTION = """You read conversations between telecom network engineers (Teams chats, emails,
phone-call transcripts) and extract reusable operational knowledge for a knowledge graph.

Step 1 - Decide if the conversation is useful.
Useful = it contains knowledge another engineer could reuse later: a fix or workaround,
a diagnosis rule, a known false alarm, a hardware compatibility rule, a practical tip,
or access information (how to physically get to equipment: keys, gate codes, road conditions).
For access information: scope_hint this_device_only, put the code/key location in details.
Also useful: advice that was tried and FAILED (record it with outcome "failed"), because
knowing what does not work saves time.
Not useful = small talk, scheduling, status updates, or pure speculation with no conclusion.

Step 2 - If useful, extract each piece of knowledge into the schema.
- For events, symptoms and actions, use the CURRENT VOCABULARY given with the conversation.
  Map what people say to those terms by MEANING, not by exact words.
  Conversations may be in Finnish, English or mixed, with slang and typos.
  Examples: "changed the optic" / "vaihdoin SFP:n" = SFP_REPLACEMENT;
  "disable and enable the port" / "bounce it" / "sammuta ja käynnistä portti" = BOUNCE_INTERFACE.
- Only if no existing term fits, create a NEW term: UPPER_SNAKE_CASE, 1-4 words, generic and
  reusable (no device IDs, names or dates), e.g. REPLACE_ANTENNA_CONNECTOR.
- Firmware limits: if knowledge is only needed below a version, set firmware_below; if it only holds
  from a version upward, set firmware_at_least. Use just the version, e.g. "3.4".
  NEVER set both to the same version. A message like "this is fixed in firmware 3.4, the workaround is
  only needed on older software" is knowledge about the FIX: set firmware_at_least "3.4", leave
  actions empty (or list only what to do on the new firmware), and do not repeat the old workaround.
- device_mentions: only devices where the knowledge was actually observed or applied, not every
  device that is mentioned.
- Put specifics that terms can't hold (part numbers, values, conditions) in details.
- Write the summary in English.
- Only extract what the conversation actually says. Do not add your own technical advice.
- scope_hint: "older_devices_of_same_type" when the expert refers to old/older units
  ("these old units", "ne vanhat laitteet"); "all_devices_of_same_type" when they say it
  is true for all such devices; otherwise "this_device_only".

The engineer may give extra context about the devices mentioned; use it to fill node_type.
"""

FEW_SHOT_EXAMPLES = """### Example 1 (useful)
Channel: teams
[seq 1 | 2024-02-01T10:02:00+02:00 | Laura (Field Engineer)]
AGG-099 port 3 keeps flapping since we moved the rack
[seq 2 | 2024-02-01T10:04:00+02:00 | Antti (Network Expert)]
on those routers it's nearly always the patch cord getting bent in the move. swap it before you touch the card
[seq 3 | 2024-02-01T10:15:00+02:00 | Laura (Field Engineer)]
new cord, stable now 👍

Expected output:
{"useful": true, "reason": "Expert gives a confirmed fix for link flapping after a rack move.",
 "knowledge": [{"knowledge_type": "troubleshooting_rule",
  "summary": "On aggregation routers, port flapping after physically moving equipment is usually a damaged patch cable; replace the cable before replacing the line card.",
  "device_mentions": ["AGG-099"], "node_type": "aggregation_router", "scope_hint": "all_devices_of_same_type",
  "firmware_below": null, "firmware_at_least": null, "events": ["MAINTENANCE"], "symptoms": ["LINK_FLAPPING"],
  "actions": ["REPLACE_PATCH_CABLE"], "avoid": ["REPLACE_LINE_CARD"], "outcome": "worked",
  "author": "Antti", "source_message_seqs": [2, 3], "confirmed_at_seq": 3, "details": null}]}

### Example 2 (not useful)
Channel: teams
[seq 1 | 2024-03-05T11:30:00+02:00 | Pekka (Field Engineer)]
lounas klo 12?
[seq 2 | 2024-03-05T11:31:00+02:00 | Laura (Field Engineer)]
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
  possibly on another device. Example: the same interface-bounce fix confirmed on another unit.
- narrows_scope: the existing tip is still true, but the new tip says it now only applies to some
  devices, e.g. "fixed in firmware 3.4, the workaround is only needed below 3.4".
  Set firmware_below to that version ("3.4").
- supersedes: the new tip makes the existing tip no longer true at all, e.g. "the gate code has
  changed, the old code no longer works".
- conflicts: the new tip contradicts the existing tip (different diagnosis or fix for the same
  problem) and the conversation does not settle who is right.
- unrelated: different problem, or no meaningful connection.

Judge only from what the tips say. Do not invent relations."""


def build_relation_prompt(new: dict, existing: list[dict]) -> str:
    def fmt(t: dict) -> str:
        lines = [f"id: {t['id']}", f"captured: {t.get('valid_from')}", f"type: {t.get('knowledge_type')}",
                 f"devices: {', '.join(t.get('devices') or []) or '-'}", f"summary: {t.get('summary')}"]
        if t.get("actions"):
            lines.append(f"actions: {', '.join(t['actions'])}")
        if t.get("details"):
            lines.append(f"details: {t['details']}")
        if t.get("scope_firmware_below") or t.get("scope_firmware_at_least"):
            lines.append(f"firmware: below={t.get('scope_firmware_below')} from={t.get('scope_firmware_at_least')}")
        return "\n".join(lines)

    return ("### NEW tip\n" + fmt(new) + "\n\n### EXISTING tips\n"
            + "\n\n".join(fmt(e) for e in existing))
