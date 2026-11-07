"""Step C of the chat: writes the answer with Gemini (streamed) from the retrieved cards only.

Falls back to a plain template built from the cards if Gemini is unavailable."""
from api import cards as C
from api.knowledge import KnowledgeResult
from api.llm import stream_text
from api.understand import Understood

COMMON = """You are the Network Knowledge Assistant for field engineers and NOC operators of a telecom
operator. You answer ONLY from the captured expert tips given to you as JSON. Never invent steps,
device IDs, codes, part numbers, dates or names that are not in the tips.

Always:
- Facts, codes, steps and names come ONLY from TIPS. PREVIOUS TURNS are only for understanding what the
  user means; never repeat a code or step from them that is not in TIPS.
- Reply in the REPLY LANGUAGE given in the input (the language of the user's message), even if the tips,
  names or places are Finnish; never mix in other languages or scripts. Keep the tips' codes and IDs as-is.
- How sure we are: use each tip's "source_count", "device_count" and "authors" exactly as given (for
  example "confirmed on <device_count> devices by <source_count> sources"). Never count sources or devices
  yourself and never round them.
- A tip with "valid_until" is HISTORY: it was replaced and is no longer valid. Never tell the user to use it.
  The current value is the tip without "valid_until".
- A tip with "not_needed_on_this_device": the device's firmware already fixes this problem, so this fix is
  NOT needed here. Say so and why in one line; if the user's problem matches it, the cause is probably
  something else, so suggest asking an expert.
- A tip with "upgrade_fixes_this": the device runs an older firmware than the one that fixes the problem.
  The other tips' workaround still applies today; add that upgrading the firmware fixes it permanently.
  Never say this tip "does not apply".
- If a tip "tried_and_failed" exists, say briefly what did not work. Only name a device for it if it is
  given in that entry; never guess which device something was tried on.
- If tips are "disputed" or "experts_disagree_with" is present, say clearly that experts disagree and give
  each view separately: who said it (author, channel, date) and whether it was confirmed to work
  (outcome "worked") or never confirmed.
- For access information (codes, keys, gates), give the details exactly, once, and never mention
  confidence, "unconfirmed" or "unverified" for it; just name the source briefly.
- If "how_it_applies" says the device was identified by place or nickname, or that a tip was only
  reported at the site without naming the device, say so in a few words (e.g. "reported at the Kolari
  site, device not confirmed"). Follow DEVICE RESOLUTION when it is given.
- If a tip applies by symptom only (no device named), say it may not apply to every device.
- Include "details" (codes, part numbers, values) exactly when they are relevant.
- If any tips are given, never answer that there is no captured knowledge: explain what the tips say,
  even if they only say what does not apply or what did not work.
- If there are no tips: say "No captured expert knowledge for this yet." and suggest asking an expert,
  in one or two sentences. Do not give generic advice from your own knowledge.
- Field engineers read this on a phone. Markdown is allowed (lists, bold), no tables, no headings.
"""

FORMATS = {
    "problem": """
This question is about ONE problem. Format:
- Start with one sentence: the likely cause or the direct answer.
- Then the steps to take, numbered, in order. Number only real actions the engineer can do; never number
  an explanation or a conclusion, and never repeat the opening sentence as a step. If the only step is
  "ask an expert", write it as a sentence, not a list. Then what NOT to do, if the tips say so.
- At most about 150 words.""",
    "overview": """
This question asks for an OVERVIEW of everything known (for example all known faults of a device).
Format:
- Start with one sentence saying how many tips there are and for which device(s).
- Then a bulleted list with one line per tip, in the order given: the problem in a few words, then what to
  do (or what is known), then its status (confirmed / disputed / outdated) and its source count.
- Do not pick a single cause, do not merge tips into one list of steps and do not number steps.
- End with one short question asking which of these problems the user is seeing.
- At most about 250 words.""",
    "history": """
This question is about the PAST (older values, what changed). Format:
- Start with the current value first (the tip without "valid_until"), with its source.
- Then the older values from the tips with "valid_until", newest first, each with its dates
  ("9035, valid until 7 Nov 2026, replaced by 3000") and source.
- At most about 150 words.""",
}


def question_type(u: Understood) -> str:
    if getattr(u, "wants_history", False):
        return "history"
    return "overview" if getattr(u, "wants_overview", False) else "problem"


def system_for(qtype: str) -> str:
    return COMMON + FORMATS.get(qtype, FORMATS["problem"])


SYSTEM = system_for("problem")


def build_prompt(message: str, history: list[tuple[str, str]], u: Understood, k: KnowledgeResult) -> str:
    devices = [{key: d.get(key) for key in ("node_id", "node_type", "install_date", "firmware")} for d in k.devices]
    tips = [C.compact_for_llm(c) for c in k.cards]
    hist = "\n".join(f"{role}: {text[:600]}" for role, text in history) or "(none)"
    unknown = f"\nDevice IDs not found in the inventory: {', '.join(u.unknown_nodes)}" if u.unknown_nodes else ""
    if getattr(u, "resolution_note", None):
        unknown += f"\nDEVICE RESOLUTION: {u.resolution_note}"
    notes = "\n".join(k.notes)
    lang = {"fi": "Finnish", "en": "English"}.get(getattr(u, "language", "en"), "the language of the user's message")
    qtype = question_type(u)
    return (f"REPLY LANGUAGE: {lang}\nQUESTION TYPE: {qtype}\n\nPREVIOUS TURNS\n{hist}\n\nDEVICES\n{C.dumps(devices)}{unknown}\n\n"
            f"RETRIEVAL NOTES\n{notes or '(none)'}\n\nTIPS\n{C.dumps(tips)}\n\nUSER MESSAGE\n{message}")


def stream_answer(message: str, history, u: Understood, k: KnowledgeResult):
    yield from stream_text(build_prompt(message, history, u, k), system_for(question_type(u)))


TEMPLATE = {
    "en": {"none": "No captured expert knowledge for this yet.", "unknown": "{ids} is not in the inventory.",
           "ask": "Consider asking an expert.", "disputed": "⚠️ Experts disagree on this one; see the cards below.",
           "details": "Details", "source": "Source", "more_src": "and {n} more",
           "more_tips": "{n} more related tip(s) below."},
    "fi": {"none": "Tästä ei ole vielä tallennettua asiantuntijatietoa.", "unknown": "{ids} ei ole laiterekisterissä.",
           "ask": "Kysy asiantuntijalta.", "disputed": "⚠️ Asiantuntijat ovat tästä eri mieltä; katso kortit alla.",
           "details": "Tiedot", "source": "Lähde", "more_src": "ja {n} muuta",
           "more_tips": "{n} muuta liittyvää vinkkiä alla."},
}


def fallback_answer(u: Understood, k: KnowledgeResult) -> str:
    """Template answer from the cards (used when Gemini is unavailable), in English or Finnish."""
    t = TEMPLATE.get(getattr(u, "language", "en"), TEMPLATE["en"])
    if not k.cards:
        extra = " " + t["unknown"].format(ids=", ".join(u.unknown_nodes)) if u.unknown_nodes else ""
        return t["none"] + extra + " " + t["ask"]
    c = k.cards[0]
    lines = [f"**{c['summary']}**"]
    if c["status"] == "disputed":
        lines.append("\n" + t["disputed"])
    if c.get("scope_note"):
        lines.append(f"\n{c['scope_note']}")
    if c["actions_text"] and c["outcome"] != "failed":
        lines.append("\n" + "\n".join(f"{i}. {x}" for i, x in enumerate(c["actions_text"], 1)))
    if c["avoid_text"]:
        lines.append("\n" + "\n".join(f"- ⛔ {x}" for x in c["avoid_text"]))
    if c.get("details"):
        lines.append(f"\n{t['details']}: `{c['details']}`")
    if c["sources"]:
        s = c["sources"][0]
        lines.append(f"\n{t['source']}: {s.get('author') or '?'} ({s['channel']}, {C.short_date(s.get('timestamp'))})"
                     + (" " + t["more_src"].format(n=len(c["sources"]) - 1) if len(c["sources"]) > 1 else ""))
    if len(k.cards) > 1:
        lines.append("\n" + t["more_tips"].format(n=len(k.cards) - 1))
    return "\n".join(lines)
