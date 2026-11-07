"""Generates the template noise conversations in data/noise_threads (pre-filter training/testing).

    python data/generator/noise.py"""
import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "noise_threads"
TZ = ZoneInfo("Europe/Helsinki")
random.seed(2026)

PEOPLE = [("Veikko Vikkelä", "Field Engineer"), ("Pekka Pylväs", "Field Engineer"),
          ("Laura Lahti", "Field Engineer"), ("Mikko Mäkelä", "Field Engineer"),
          ("Tiina Tuominen", "NOC Operator"), ("Erkki Expert", "Network Expert"),
          ("Sanna Siirto", "Network Expert"), ("Jari Jänne", "Network Expert"),
          ("Antti Aalto", "Network Expert")]
DEVICES = [r["node_id"] for r in csv.DictReader(open(ROOT / "inventory" / "nodes.csv", encoding="utf-8"))]
LOCATION = {r["node_id"]: r["location"] for r in csv.DictReader(open(ROOT / "inventory" / "nodes.csv", encoding="utf-8"))}
EVENTS = json.loads((ROOT / "events" / "events.json").read_text(encoding="utf-8"))

TEMPLATES = [
    ("social", "fi", ["Lounas klo 11:30?", "joo, mennään siihen uuteen paikkaan", "sopii 👍"]),
    ("social", "en", ["Anyone up for pizza on Friday?", "count me in", "same 🍕"]),
    ("social", "mixed", ["Pikkujoulut on 12.12, ilmoittautuminen perjantaihin mennessä", "ok, I'll sign up", "kiitos!"]),
    ("schedule", "fi", ["Voitko vaihtaa päivystysvuoron kanssani ensi viikolla?", "Joo käy, otan sun tiistain", "Kiitos paljon!"]),
    ("schedule", "en", ["I'm on call this weekend, who has next week?", "Me, from Monday", "ok great"]),
    ("hr", "en", ["Reminder: log your hours in the system before Friday", "done", "will do tonight"]),
    ("hr", "fi", ["Muistakaa tehdä kulukorvaukset kuun loppuun mennessä", "ok"]),
    ("smalltalk", "fi", ["Huhhuh mikä pakkanen tänään, -28 Kittilässä", "täällä -31 😅", "kahvia lisää"]),
    ("smalltalk", "en", ["Congrats on the new car!", "thanks! finally something with seat heating 😄"]),
    ("training", "en", ["The safety training is on Thursday at 9 in the Oulu office", "Is it mandatory?", "yes for all field staff"]),
    ("logistics", "en", ["Do we have SFPs in stock in the Oulu warehouse?", "I think 4 left", "ok I'll order more"]),
    ("logistics", "fi", ["Tuleeko ne uudet patch-kaapelit huomenna?", "Pitäisi tulla aamulla", "hyvä"]),
    ("planning", "en", ["Firmware upgrade window for the routers is next Tuesday 01-04", "noted", "I'll be on call"]),
    ("planning", "mixed", ["Huoltoikkuna ensi yönä klo 02, firmware upgrade parille laitteelle", "ok, I'll inform NOC", "kiitos"]),
    ("question", "en", ["Does anyone know when the new laptops arrive?", "no idea, ask IT", "ok"]),
    ("status", "en", ["All done at {dev}, heading back", "ok thanks", "drive safe"]),
    ("status", "fi", ["Valmista tuli {dev}:llä, lähden takaisin", "ok, kiitos"]),
    ("status", "mixed", ["{dev} done, ajan nyt {loc}sta Rovaniemelle", "ok 👍"]),
    ("ticket", "en", ["Closed {wo} for {dev}", "thanks, I'll update the report"]),
    ("ticket", "fi", ["Suljin työmääräyksen {wo} ({dev})", "selvä"]),
    ("dispatch", "en", ["Who can go to {dev} in {loc} tomorrow?", "I can, morning", "great, I'll assign it"]),
    ("dispatch", "fi", ["Kuka ehtii {dev}:lle huomenna?", "Mä voin mennä iltapäivällä", "ok, laitan sulle"]),
    ("alarm_no_answer", "en", ["Anyone else seeing alarms on {dev}?", "not me", "I'll check tomorrow then"]),
    ("alarm_no_answer", "fi", ["Onko {dev}:llä taas hälytyksiä?", "En oo kattonut", "katon huomenna"]),
    ("report", "en", ["Can you send me the report for the {dev} visit?", "sure, after lunch"]),
    ("car", "en", ["Is the 4WD free tomorrow? Need to go to {loc}", "booked by Pekka until noon", "ok I'll take it after"]),
    ("car", "fi", ["Onko pakettiauto vapaa torstaina {loc}n keikkaa varten?", "on", "varaan sen"]),
    ("photo", "mixed", ["Kuvat {dev}:n kaapista liitteenä", "thanks, got them"]),
    ("handover", "en", ["Handing over the {dev} case to the night shift", "ok, got it"]),
    ("thanks", "en", ["Thanks for the help at {dev} yesterday!", "no problem 👍"]),
]


def event_time_for(dev: str) -> datetime | None:
    evs = [e for e in EVENTS if e["node_id"] == dev]
    if not evs:
        return None
    e = random.choice(evs)
    return datetime.fromisoformat(e["timestamp"]) + timedelta(hours=random.randint(1, 6))


def random_time() -> datetime:
    start = datetime(2023, 3, 1, tzinfo=TZ)
    t = start + timedelta(days=random.randint(0, 1300), hours=random.randint(7, 16), minutes=random.randint(0, 59))
    return t.astimezone(TZ)


def build(i: int, template) -> dict:
    category, lang, texts = template
    dev = random.choice(DEVICES)
    uses_device = any("{dev}" in t or "{loc}" in t for t in texts)
    start = (event_time_for(dev) if uses_device and random.random() < 0.5 else None) or random_time()
    start = start.astimezone(TZ).replace(second=0, microsecond=0)
    people = random.sample(PEOPLE, 3)
    fill = {"dev": dev, "loc": LOCATION.get(dev, "Oulu"), "wo": f"WO-{random.randint(55000, 59999)}"}
    messages, t = [], start
    for seq, text in enumerate(texts, start=1):
        author, role = people[(seq - 1) % len(people)]
        stamp = t.astimezone(TZ)
        messages.append({"seq": seq, "time": stamp.strftime("%H:%M"), "timestamp": stamp.isoformat(),
                         "author": author, "role": role, "text": text.format(**fill)})
        t += timedelta(minutes=random.randint(1, 6))
    return {
        "thread_id": f"N{i:03d}", "channel": "teams", "date": start.date().isoformat(), "language": lang,
        "note": f"Synthetic NOISE ({category}) for pre-filter testing; contains no reusable knowledge.",
        "participants": [{"name": p[0], "role": p[1]} for p in people],
        "messages": messages,
    }


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("N*.json"):
        old.unlink()
    for i in range(1, 61):
        template = TEMPLATES[(i - 1) % len(TEMPLATES)]
        thread = build(i, template)
        (OUT / f"{thread['thread_id']}.json").write_text(json.dumps(thread, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote 60 noise conversations to {OUT}")


if __name__ == "__main__":
    main()
