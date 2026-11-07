"""
Step C · ANSWER (Gemini, streamed).

Gemini gets ONLY the question, the recent turns and Step B's cards. Rule: answer only from these
tips; if there are none, say there is no recorded knowledge. If Gemini is unavailable, a plain
template answer is built from the cards so the demo never goes silent.
"""
from api import cards as C
from api.knowledge import KnowledgeResult
from api.llm import stream_text
from api.understand import Understood

SYSTEM = """You are the Network Knowledge Assistant for field engineers and NOC operators of a telecom
operator. You answer ONLY from the captured expert tips given to you as JSON. Never invent steps,
device IDs, codes, part numbers, dates or names that are not in the tips.

How to answer:
- Reply in the language of the user's message (Finnish or English). Keep the tips' codes and IDs as-is.
- Start with one sentence: the likely cause or the direct answer.
- Then the steps to take, numbered, in order. Then what NOT to do, if the tips say so.
- If a tip "tried_and_failed" exists, say briefly what did not work.
- If tips are "disputed" or "experts_disagree_with" is present, say clearly that experts disagree and give both views.
- If a tip has "not_applicable_because", explain in one line that it does not apply to this device and why.
- Mention how sure we are in plain words (e.g. "confirmed on 3 devices by 2 sources") and name the source
  briefly: author, channel and date.
- If a tip applies by symptom only (no device named), say it may not apply to every device.
- Include "details" (codes, part numbers, values) exactly when they are relevant.
- If there are no tips: say "No captured expert knowledge for this yet." and suggest asking an expert,
  in one or two sentences. Do not give generic advice from your own knowledge.
- Be short: field engineers read this on a phone. At most about 150 words. Markdown is allowed
  (numbered lists, bold), no tables, no headings."""


def build_prompt(message: str, history: list[tuple[str, str]], u: Understood, k: KnowledgeResult) -> str:
    devices = [{key: d.get(key) for key in ("node_id", "node_type", "install_date", "firmware")} for d in k.devices]
    tips = [C.compact_for_llm(c) for c in k.cards]
    hist = "\n".join(f"{role}: {text[:600]}" for role, text in history) or "(none)"
    unknown = f"\nDevice IDs not found in the inventory: {', '.join(u.unknown_nodes)}" if u.unknown_nodes else ""
    notes = "\n".join(k.notes)
    return (f"PREVIOUS TURNS\n{hist}\n\nDEVICES\n{C.dumps(devices)}{unknown}\n\n"
            f"RETRIEVAL NOTES\n{notes or '(none)'}\n\nTIPS\n{C.dumps(tips)}\n\nUSER MESSAGE\n{message}")


def stream_answer(message: str, history, u: Understood, k: KnowledgeResult):
    yield from stream_text(build_prompt(message, history, u, k), SYSTEM)


def fallback_answer(u: Understood, k: KnowledgeResult) -> str:
    """Template answer from the cards (used when Gemini is unavailable)."""
    if not k.cards:
        extra = f" ({', '.join(u.unknown_nodes)} is not in the inventory.)" if u.unknown_nodes else ""
        return "No captured expert knowledge for this yet." + extra + " Consider asking an expert."
    c = k.cards[0]
    lines = [f"**{c['summary']}**"]
    if c["status"] == "disputed":
        lines.append("\n⚠️ Experts disagree on this one; see the cards below.")
    if c.get("scope_note"):
        lines.append(f"\n{c['scope_note']}")
    if c["actions_text"] and c["outcome"] != "failed":
        lines.append("\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(c["actions_text"], 1)))
    if c["avoid_text"]:
        lines.append("\n" + "\n".join(f"- ⛔ {t}" for t in c["avoid_text"]))
    if c.get("details"):
        lines.append(f"\nDetails: `{c['details']}`")
    if c["sources"]:
        s = c["sources"][0]
        lines.append(f"\nSource: {s.get('author') or 'unknown'} ({s['channel']}, {C.short_date(s.get('timestamp'))})"
                     + (f" and {len(c['sources']) - 1} more" if len(c["sources"]) > 1 else ""))
    if len(k.cards) > 1:
        lines.append(f"\n{len(k.cards) - 1} more related tip(s) below.")
    return "\n".join(lines)
