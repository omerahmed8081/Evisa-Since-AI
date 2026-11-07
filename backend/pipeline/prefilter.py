"""Local pre-filter that skips obvious noise before any LLM call.

Rule score first, then a small TF-IDF + logistic regression classifier (models/prefilter.joblib)."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from pipeline import DATA_DIR, BACKEND_DIR, linking, threads

MODEL_PATH = BACKEND_DIR / "models" / "prefilter.joblib"
MIN_SCORE = 3
EVENT_WINDOW = timedelta(hours=48)

TECH_TERMS = [
    "sfp", "optic", "optiik", "link", "port", "interface", "rajapin", "liitän", "liityn", "counter",
    "laskur", "alarm", "hälyt", "firmware", "reboot", "buut", "boot", "traffic", "liikenne", "radome",
    "radomi", "psu", "virtaläh", "power supply", "fuse", "sulake", "baseband", "gps", "atpc", "crc",
    "patch", "kaapel", "cable", "lacp", "rectifier", "tasasuunt", "battery", "akku", "fan ", "tuuletin",
    "console", "baud", "rx ", "signal", "signaal", "module", "moduul", "line card", "radio", "antenn",
    "transmission", "router", "reititin", "cell", "solu", "forwarding", "uplink", "sync",
]
RESOLUTION = [
    "works now", "working now", "traffic is back", "is back", "back up", "fixed", "stable now",
    "stable since", "resolved", "solved", "did the trick", "that helped", "there you go", "solved it",
    "toimii", "kulkee taas", "korjaantui", "korjasi", "kunnossa", "tuli takaisin", "nyt ok",
]
FAILURE = [
    "didn't help", "did not help", "didn't work", "did not work", "no change", "same problem",
    "same result", "same thing", "still zero", "still down", "still no", "still not",
    "ei auttanut", "sama ongelma", "ei muutosta", "ei toiminut", "edelleen",
]
ADVICE = [
    "usually", "always", "never", "don't", "do not", "make sure", "check ", "try ", "only use",
    "yleensä", "aina", "älä", "tarkista", "kokeile", "katso ensin", "muista",
]
ACCESS_WORDS = ["code", "koodi", "gate", "portin", "key", "avain", "lockbox", "barrier", "puomi", "padlock", "lukko"]
CODE_RE = re.compile(r"\b\d{4}\b")
DEVICE_TOKEN_RE = threads.DEVICE_ID_RE


_PATTERNS: dict[str, re.Pattern] = {}


def _found(text: str, phrases: list[str]) -> list[str]:
    """Phrases that occur at the START of a word (so "fuse" doesn't match "refuse",
    but Finnish endings still match: "linkki" -> "link", "hälytykset" -> "hälyt")."""
    out = []
    for p in phrases:
        pat = _PATTERNS.get(p) or _PATTERNS.setdefault(p, re.compile(r"(?<![a-zåäö0-9])" + re.escape(p.strip())))
        if pat.search(text):
            out.append(p.strip())
    return out


class Prefilter:
    def __init__(self, data_dir: Path = DATA_DIR, model_path: Path = MODEL_PATH, use_classifier: bool = True):
        self.inv = linking.Inventory.from_csv(data_dir / "inventory" / "nodes.csv",
                                              data_dir / "inventory" / "aliases.csv")
        self.inventory = set(self.inv.devices)
        events_file = data_dir / "events" / "events.json"
        self.events: dict[str, list[datetime]] = {}
        if events_file.exists():
            for e in json.loads(events_file.read_text(encoding="utf-8")):
                self.events.setdefault(e["node_id"], []).append(datetime.fromisoformat(e["timestamp"]))
        self.model = None
        self.threshold = None
        if use_classifier and Path(model_path).exists():
            import joblib
            bundle = joblib.load(model_path)
            self.model, self.threshold = bundle["pipeline"], bundle["threshold"]

    def score(self, thread: dict) -> tuple[int, list[str]]:
        text = ((thread.get("subject") or "") + "\n" + "\n".join(m["text"] for m in thread["messages"])).lower()
        reasons, score = [], 0

        raw = (thread.get("subject") or "") + "\n" + "\n".join(m["text"] for m in thread["messages"])
        match = self.inv.resolve(raw)
        devices = sorted({d for d in threads.find_device_ids(thread) if d in self.inventory} | match.named)
        if devices:
            score += 2
            reasons.append(f"device {', '.join(devices)} (+2)")
        elif match.locations:
            score += 1
            reasons.append(f"place {', '.join(match.locations)} (+1)")

        tech = _found(text, TECH_TERMS)
        if tech:
            pts = min(3, len(tech))
            score += pts
            reasons.append(f"technical terms {tech[:4]} (+{pts})")

        for name, phrases, pts in (("resolution", RESOLUTION, 2), ("failure", FAILURE, 2), ("advice", ADVICE, 1)):
            hit = _found(text, phrases)
            if hit:
                score += pts
                reasons.append(f"{name} '{hit[0]}' (+{pts})")

        access = _found(text, ACCESS_WORDS)
        if access and (CODE_RE.search(text) or {"key", "avain", "lockbox", "barrier", "puomi"} & set(access)):
            score += 2
            reasons.append(f"access info '{access[0]}' (+2)")

        msgs = thread["messages"]
        for i, m in enumerate(msgs):
            if "?" in m["text"] and any(
                    n["author"] != m["author"] and any(r in (n.get("role") or "") for r in ("Expert", "NOC"))
                    for n in msgs[i + 1:]):
                score += 1
                reasons.append("question answered by an expert (+1)")
                break

        start = msgs[0].get("timestamp")
        if devices and start:
            t0 = datetime.fromisoformat(start)
            near = [d for d in devices if any(abs(t0 - e) <= EVENT_WINDOW for e in self.events.get(d, []))]
            if near:
                score += 3
                reasons.append(f"event on {near[0]} within 48 h (+3)")
        return score, reasons

    @staticmethod
    def model_text(thread: dict) -> str:
        """Text the classifier sees: device IDs and numbers masked so it learns wording, not IDs."""
        text = (thread.get("subject") or "") + "\n" + "\n".join(m["text"] for m in thread["messages"])
        text = DEVICE_TOKEN_RE.sub(" DEVICEID ", text)
        return re.sub(r"\d", "0", text.lower())

    def probability(self, thread: dict) -> float | None:
        if self.model is None:
            return None
        return float(self.model.predict_proba([self.model_text(thread)])[0][1])

    def decide(self, thread: dict) -> dict:
        score, reasons = self.score(thread)
        if score < MIN_SCORE:
            return {"keep": False, "stage": "rules", "score": score, "reasons": reasons, "p_useful": None}
        p = self.probability(thread)
        protected = any(r.startswith("access info") for r in reasons)
        if p is not None and p < self.threshold and not protected:
            return {"keep": False, "stage": "classifier", "score": score, "reasons": reasons, "p_useful": round(p, 3)}
        return {"keep": True, "stage": "passed", "score": score, "reasons": reasons,
                "p_useful": None if p is None else round(p, 3)}
