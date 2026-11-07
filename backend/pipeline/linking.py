"""Finds the devices a text is about: device IDs (also messy forms), nicknames (aliases.csv)
and places from the inventory. Each link carries how it was made and a confidence."""
import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from pipeline import DATA_DIR

ID_RE = re.compile(r"(?<![A-Za-z0-9])(TRN|AGG|BTS|MW)[-\s_]?(\d{2,4})(?![0-9])", re.IGNORECASE)

LINK_CONFIDENCE = {"id": 1.0, "alias": 0.9, "location": 0.8, "site": 0.5}

TYPE_WORDS = {
    "transmission": ["transmission", "siirtolaite", "siirtolaitte", "siirtoyhteys", "siirtosolmu", "siirron",
                     "optical node", "trn"],
    "aggregation_router": ["router", "reititin", "reitittim", "aggregation", "aggregaatio", "agg", "lacp",
                           "port-channel", "port channel"],
    "base_station": ["base station", "basestation", "tukiasema", "bts", "baseband", "enodeb", "gnodeb",
                     "cell site", "solu"],
    "microwave_link": ["microwave", "radio link", "radiolinkki", "linkkihyppy", "hop", "radome", "radomi",
                       "mw link", "mw-link"],
}

ENDINGS = ["", "n", "ssa", "ssä", "sta", "stä", "lla", "llä", "lta", "ltä", "lle", "ksi", "na", "nä",
           "in", "iin", "un", "uun", "yn", "yyn", "on", "oon", "ön", "an", "än", "en", "een", "hen",
           "lla", "ella", "ellä", "elle", "elta", "eltä", "en", "s", "'s"]


def _word_start(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![a-zåäö0-9])" + re.escape(phrase))


@dataclass
class Match:
    """Result of resolving one piece of text against the inventory."""
    ids: set[str] = field(default_factory=set)
    unknown_ids: set[str] = field(default_factory=set)
    aliases: dict[str, str] = field(default_factory=dict)
    locations: list[str] = field(default_factory=list)
    type_hints: set[str] = field(default_factory=set)

    @property
    def named(self) -> set[str]:
        """Devices named directly (ID or nickname)."""
        return self.ids | set(self.aliases)


class Inventory:
    def __init__(self, devices: list[dict], aliases: dict[str, str] | None = None):
        """devices: dicts with node_id, node_type, location (and anything else).
        aliases: nickname (any case) -> node_id."""
        self.devices = {d["node_id"]: d for d in devices}
        self.by_location: dict[str, list[dict]] = {}
        for d in devices:
            if d.get("location"):
                self.by_location.setdefault(d["location"], []).append(d)
        self.aliases = {a.strip().lower(): nid for a, nid in (aliases or {}).items()
                        if a.strip() and nid in self.devices}
        self.alias_names = {a.strip().lower(): a.strip() for a in (aliases or {})}
        self._alias_res = [(a, nid, _word_start(a)) for a, nid in sorted(self.aliases.items(), key=lambda x: -len(x[0]))]
        self._place_forms = {loc: self._forms(loc) for loc in self.by_location}

    @classmethod
    def from_csv(cls, nodes_csv: Path = DATA_DIR / "inventory" / "nodes.csv",
                 aliases_csv: Path = DATA_DIR / "inventory" / "aliases.csv") -> "Inventory":
        with open(nodes_csv, encoding="utf-8") as f:
            devices = list(csv.DictReader(f))
        return cls(devices, load_aliases(aliases_csv))

    @classmethod
    def from_graph(cls) -> "Inventory":
        from pipeline import graph
        rows = graph.run("MATCH (d:Device) RETURN d.node_id AS node_id, d.node_type AS node_type, "
                         "d.location AS location, toString(d.install_date) AS install_date, "
                         "d.firmware AS firmware, coalesce(d.aliases, []) AS aliases")
        devices = [dict(r) for r in rows]
        aliases = {a: d["node_id"] for d in devices for a in d.get("aliases") or []}
        return cls(devices, aliases)

    @staticmethod
    def _forms(place: str) -> set[str]:
        p = place.lower()
        stems = {p}
        if p.endswith("i"):
            stems.add(p[:-1] + "e")
        return {s + e for s in stems for e in ENDINGS}

    def find_ids(self, text: str) -> tuple[set[str], set[str]]:
        """(known, unknown) device IDs written in the text, normalised to 'TRN-042'."""
        found = {f"{a.upper()}-{b}" for a, b in ID_RE.findall(text)}
        return {i for i in found if i in self.devices}, {i for i in found if i not in self.devices}

    def find_aliases(self, text: str) -> dict[str, str]:
        low, out = text.lower(), {}
        for alias, nid, rx in self._alias_res:
            if rx.search(low):
                out.setdefault(nid, self.alias_names.get(alias, alias))
        return out

    def find_locations(self, text: str) -> list[str]:
        words = set(re.findall(r"[a-zåäö']+", text.lower()))
        return [loc for loc, forms in self._place_forms.items() if words & forms]

    @staticmethod
    def find_type_hints(text: str) -> set[str]:
        low = text.lower()
        return {t for t, words in TYPE_WORDS.items() if any(_word_start(w).search(low) for w in words)}

    def resolve(self, text: str) -> Match:
        known, unknown = self.find_ids(text)
        return Match(ids=known, unknown_ids=unknown, aliases=self.find_aliases(text),
                     locations=self.find_locations(text), type_hints=self.find_type_hints(text))

    def candidates(self, locations: list[str], node_types: set[str] | None = None) -> list[dict]:
        """Devices at these places, narrowed to the given device types (if any match)."""
        at = [d for loc in locations for d in self.by_location.get(loc, [])]
        if node_types:
            typed = [d for d in at if d.get("node_type") in node_types]
            return typed
        return at


def load_aliases(path: Path = DATA_DIR / "inventory" / "aliases.csv") -> dict[str, str]:
    """nickname -> node_id. File columns: node_id, alias (several rows per device allowed)."""
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["alias"].strip(): r["node_id"].strip() for r in csv.DictReader(f) if r.get("alias")}


def location_links(match: Match, inv: Inventory, node_type: str | None) -> dict:
    """How to link knowledge from a conversation that names NO device, only a place.

    Returns {"devices": [{node_id, linked_by, link_confidence, via}], "sites": [{site, link_confidence,
    candidates}], "note": str}. One device left after the type filter -> link it ('location').
    Several (or none of the right type) -> link the Site(s) instead of guessing ('site')."""
    if not match.locations:
        return {"devices": [], "sites": [], "note": ""}
    types = {node_type} if node_type else set(match.type_hints)
    cands = inv.candidates(match.locations, types or None)
    places = ", ".join(match.locations)
    if len(cands) == 1:
        d = cands[0]
        why = f"the only {d['node_type'].replace('_', ' ')} in {d['location']}" if types \
            else f"the only device in {d['location']}"
        return {"devices": [{"node_id": d["node_id"], "linked_by": "location",
                             "link_confidence": LINK_CONFIDENCE["location"], "via": why}],
                "sites": [], "note": f"linked to {d['node_id']} by location ({why})"}
    all_at = inv.candidates(match.locations)
    pool = cands or all_at
    sites = sorted({d["location"] for d in pool} or set(match.locations))
    return {"devices": [],
            "sites": [{"site": s, "link_confidence": LINK_CONFIDENCE["site"],
                       "candidates": sorted(d["node_id"] for d in pool if d["location"] == s)} for s in sites],
            "note": f"linked to site {places} ({len(pool)} possible devices: "
                    f"{', '.join(sorted(d['node_id'] for d in pool))})"}


_csv_inventory: Inventory | None = None


def csv_inventory() -> Inventory:
    global _csv_inventory
    if _csv_inventory is None:
        _csv_inventory = Inventory.from_csv()
    return _csv_inventory
