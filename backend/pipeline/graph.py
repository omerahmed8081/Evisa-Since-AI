"""
Everything that talks to Neo4j.

Graph shape:
  (:Device {node_id, node_type, install_date, firmware, location})      <- from inventory
  (:Assertion {...knowledge, scope_*, valid_from, valid_to, status})   <- from conversations
  (:Source {id, channel, timestamp, text})                             <- the raw chat/email
  (:Person {name, role})

  (Assertion)-[:OBSERVED_ON]->(Device)
  (Assertion)-[:FROM]->(Source)
  (Assertion)-[:BY]->(Person)

  (:Term {key, name, category, status: seed|new, aliases, embedding})  <- the growing vocabulary
  (Assertion)-[:AFTER_EVENT]->(Term)
  (Assertion)-[:HAS_SYMPTOM]->(Term)
  (Assertion)-[:RECOMMENDS {order}]->(Term)
  (Assertion)-[:AVOIDS]->(Term)
"""
import csv
import os
from pathlib import Path

from neo4j import GraphDatabase

_driver = None


def driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
            # hide informational warnings such as "property valid_to does not exist yet"
            notifications_min_severity="OFF",
        )
    return _driver


def run(query: str, **params):
    with driver().session() as session:
        return list(session.run(query, **params))


def setup_constraints():
    run("CREATE CONSTRAINT device_id IF NOT EXISTS FOR (d:Device) REQUIRE d.node_id IS UNIQUE")
    run("CREATE CONSTRAINT assertion_id IF NOT EXISTS FOR (a:Assertion) REQUIRE a.id IS UNIQUE")
    run("CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE")
    run("CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE")
    run("CREATE CONSTRAINT term_key IF NOT EXISTS FOR (t:Term) REQUIRE t.key IS UNIQUE")


def load_inventory(csv_path: Path) -> int:
    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    run(
        """
        UNWIND $rows AS r
        MERGE (d:Device {node_id: r.node_id})
        SET d.name = r.node_id,
            d.node_type = r.node_type,
            d.install_date = date(r.install_date),
            d.firmware = r.firmware,
            d.location = r.location,
            d.status = r.status
        """,
        rows=rows,
    )
    return len(rows)


def load_events(json_path: Path) -> int:
    """Event stream (alarms, work orders, firmware upgrades) as (:Event)-[:ON]->(:Device)."""
    import json
    events = json.loads(Path(json_path).read_text(encoding="utf-8"))
    for e in events:  # make optional keys explicit so Cypher gets nulls
        for key in ("from_firmware", "to_firmware", "detail", "related_thread"):
            e.setdefault(key, None)
    run(
        """
        UNWIND $rows AS r
        MERGE (e:Event {id: r.event_id})
        SET e.name = r.event_type, e.event_type = r.event_type, e.timestamp = datetime(r.timestamp),
            e.detail = r.detail, e.from_firmware = r.from_firmware, e.to_firmware = r.to_firmware,
            e.related_thread = r.related_thread
        WITH e, r
        MATCH (d:Device {node_id: r.node_id})
        MERGE (e)-[:ON]->(d)
        """,
        rows=events,
    )
    return len(events)


def existing_source_ids() -> set[str]:
    """Threads that were fully processed (so a crashed thread is retried next run)."""
    return {r["id"] for r in run("MATCH (s:Source) WHERE s.processed = true RETURN s.id AS id")}


def mark_source_done(source_id: str):
    run("MATCH (s:Source {id: $id}) SET s.processed = true", id=source_id)


def mark_source_prefiltered(source_id: str, stage: str, score: int, p_useful: float | None):
    """Skipped by the local pre-filter: never sent to Gemini, but kept so it can be audited."""
    run("""MATCH (s:Source {id: $id})
           SET s.processed = true, s.prefiltered = true, s.prefilter_stage = $stage,
               s.prefilter_score = $score, s.prefilter_p_useful = $p""",
        id=source_id, stage=stage, score=score, p=p_useful)


def get_devices(node_ids: list[str]) -> list[dict]:
    records = run(
        "MATCH (d:Device) WHERE d.node_id IN $ids RETURN d",
        ids=list(node_ids),
    )
    return [dict(r["d"]) for r in records]


def save_source(thread: dict, raw_text: str):
    first = thread["messages"][0]
    run(
        """
        MERGE (s:Source {id: $id})
        SET s.name = $id, s.channel = $channel, s.timestamp = datetime($ts), s.text = $text
        """,
        id=thread["thread_id"], channel=thread["channel"], ts=first.get("timestamp"), text=raw_text,
    )


def save_assertion(a: dict):
    """a = flat dict built in ingest.py"""
    run(
        """
        MERGE (x:Assertion {id: $a.id})
        SET x.name = $a.id,
            x.knowledge_type = $a.knowledge_type,
            x.summary = $a.summary,
            x.events = $a.events,
            x.symptoms = $a.symptoms,
            x.actions = $a.actions,
            x.avoid = $a.avoid,
            x.outcome = $a.outcome,
            x.details = $a.details,
            x.scope_node_type = $a.scope_node_type,
            x.scope_installed_before = CASE WHEN $a.scope_installed_before IS NULL THEN null
                                            ELSE date($a.scope_installed_before) END,
            x.scope_firmware_below = $a.scope_firmware_below,
            x.scope_firmware_at_least = $a.scope_firmware_at_least,
            x.confidence = $a.confidence,
            x.status = 'auto_captured',
            x.valid_from = datetime($a.valid_from),
            x.valid_to = null
        WITH x
        MATCH (s:Source {id: $a.source_id})
        MERGE (x)-[:FROM]->(s)
        WITH x
        MERGE (p:Person {name: $a.author})
        MERGE (x)-[:BY]->(p)
        WITH x
        UNWIND $a.observed_on AS dev_id
        MATCH (d:Device {node_id: dev_id})
        MERGE (x)-[:OBSERVED_ON]->(d)
        """,
        a=a,
    )


TERM_LINKS = [
    ("events", "event", "AFTER_EVENT"),
    ("symptoms", "symptom", "HAS_SYMPTOM"),
    ("actions", "action", "RECOMMENDS"),
    ("avoid", "action", "AVOIDS"),
]


def link_terms(a: dict):
    """Connect an assertion to its vocabulary terms (terms already exist: vocabulary.py created them)."""
    for field, category, rel in TERM_LINKS:
        run(
            f"""
            MATCH (x:Assertion {{id: $id}})
            OPTIONAL MATCH (x)-[old:{rel}]->(:Term)
            DELETE old
            WITH DISTINCT x
            UNWIND range(0, size($terms) - 1) AS i
            MATCH (t:Term {{key: $category + ':' + $terms[i]}})
            MERGE (x)-[r:{rel}]->(t)
            SET r.order = i
            """,
            id=a["id"], terms=a[field], category=category,
        )


ASSERTION_FIELDS = """
    {.id, .knowledge_type, .summary, .actions, .symptoms, .events, .outcome, .details, .scope_node_type,
     .scope_firmware_below, .scope_firmware_at_least, valid_from: toString(X.valid_from)}
"""


def get_assertion(assertion_id: str) -> dict | None:
    rows = run(
        f"""
        MATCH (a:Assertion {{id: $id}})
        OPTIONAL MATCH (a)-[:OBSERVED_ON]->(d:Device)
        OPTIONAL MATCH (a)-[:FROM]->(s:Source)
        RETURN a {ASSERTION_FIELDS.replace('X', 'a')} AS a,
               collect(DISTINCT d.node_id) AS devices, collect(DISTINCT d.node_type) AS types,
               head(collect(s.id)) AS source
        """,
        id=assertion_id,
    )
    if not rows:
        return None
    a = dict(rows[0]["a"])
    a["devices"], a["device_types"], a["source"] = rows[0]["devices"], rows[0]["types"], rows[0]["source"]
    return a


def candidate_assertions(new: dict, limit: int = 8) -> list[dict]:
    """Older, still-valid tips that could be related to the new one:
    same device, or same device type AND at least one shared vocabulary term."""
    rows = run(
        f"""
        MATCH (n:Assertion {{id: $id}})
        MATCH (c:Assertion)
        WHERE c.id <> n.id AND c.valid_to IS NULL AND c.valid_from <= n.valid_from
          AND NOT EXISTS {{ (c)-[:FROM]->(:Source)<-[:FROM]-(n) }}
        OPTIONAL MATCH (n)-[:OBSERVED_ON]->(sd:Device)<-[:OBSERVED_ON]-(c)
        WITH n, c, count(DISTINCT sd) AS shared_devices
        OPTIONAL MATCH (n)-->(t:Term)<--(c)
        WITH n, c, shared_devices, count(DISTINCT t) AS shared_terms
        OPTIONAL MATCH (c)-[:OBSERVED_ON]->(d:Device)
        RETURN c {ASSERTION_FIELDS.replace('X', 'c')} AS c, collect(DISTINCT d.node_id) AS devices,
               collect(DISTINCT d.node_type) AS types, shared_devices, shared_terms
        """,
        id=new["id"],
    )
    new_types = set(new["device_types"]) | ({new["scope_node_type"]} if new.get("scope_node_type") else set())
    is_access = new["knowledge_type"] == "access_info"
    out = []
    for r in rows:
        c = dict(r["c"])
        c["devices"] = r["devices"]
        c_types = set(r["types"]) | ({c["scope_node_type"]} if c.get("scope_node_type") else set())
        if (c["knowledge_type"] == "access_info") != is_access:
            continue
        if is_access:
            related = r["shared_devices"] > 0
        else:
            related = r["shared_devices"] > 0 or (bool(new_types & c_types) and r["shared_terms"] > 0)
        if related:
            c["_score"] = r["shared_devices"] * 3 + r["shared_terms"]
            out.append(c)
    out.sort(key=lambda c: -c["_score"])
    return out[:limit]


def apply_relation(new_id: str, existing_id: str, relation: str, firmware_below: str | None, reason: str):
    if relation == "same_knowledge":
        run("""MATCH (n:Assertion {id: $n}), (c:Assertion {id: $c})
               MERGE (n)-[r:REINFORCES]->(c) SET r.reason = $reason""", n=new_id, c=existing_id, reason=reason)
    elif relation == "narrows_scope":
        run("""MATCH (n:Assertion {id: $n}), (c:Assertion {id: $c})
               SET c.scope_firmware_below = coalesce($fw, c.scope_firmware_below)
               MERGE (n)-[r:NARROWS_SCOPE]->(c) SET r.firmware_below = $fw, r.reason = $reason""",
            n=new_id, c=existing_id, fw=firmware_below, reason=reason)
    elif relation == "supersedes":
        run("""MATCH (n:Assertion {id: $n}), (c:Assertion {id: $c})
               SET c.valid_to = n.valid_from, c.status = 'superseded'
               MERGE (n)-[r:SUPERSEDES]->(c) SET r.reason = $reason""", n=new_id, c=existing_id, reason=reason)
    elif relation == "conflicts":
        run("""MATCH (n:Assertion {id: $n}), (c:Assertion {id: $c})
               SET c.status = 'disputed', n.status = 'disputed'
               MERGE (n)-[r:CONFLICTS_WITH]->(c) SET r.reason = $reason""", n=new_id, c=existing_id, reason=reason)



def same_knowledge_cluster(assertion_id: str) -> list[str]:
    """All tips connected to this one through REINFORCES links (in either direction)."""
    rows = run(
        """
        MATCH (t:Assertion {id: $id})-[:REINFORCES*0..4]-(m:Assertion)
        WHERE m.valid_to IS NULL
        RETURN DISTINCT m.id AS id
        """,
        id=assertion_id,
    )
    return [r["id"] for r in rows]
