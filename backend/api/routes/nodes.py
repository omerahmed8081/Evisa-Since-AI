"""Device endpoints: list for the selector, details for the side panel."""
from fastapi import APIRouter, HTTPException

from pipeline import graph
from api import knowledge
from api.models import Node, NodeDetail

router = APIRouter(prefix="/api", tags=["nodes"])

NODE_FIELDS = ("d {.node_id, .node_type, .firmware, .location, .status, "
               "install_date: toString(d.install_date)} AS node")


@router.get("/nodes", response_model=list[Node])
def list_nodes():
    return [dict(r["node"]) for r in graph.run(f"MATCH (d:Device) RETURN {NODE_FIELDS} ORDER BY d.node_id")]


@router.get("/nodes/{node_id}", response_model=NodeDetail)
def node_detail(node_id: str):
    node_id = node_id.upper()
    rows = graph.run(f"MATCH (d:Device {{node_id: $id}}) RETURN {NODE_FIELDS}", id=node_id)
    if not rows:
        raise HTTPException(404, f"Unknown device {node_id}")
    events = graph.run(
        """
        MATCH (e:Event)-[:ON]->(:Device {node_id: $id})
        RETURN e.id AS event_id, toString(e.timestamp) AS timestamp, e.event_type AS event_type,
               e.detail AS detail, e.from_firmware AS from_firmware, e.to_firmware AS to_firmware,
               e.related_thread AS related_thread
        ORDER BY e.timestamp DESC
        """, id=node_id)
    return {"node": dict(rows[0]["node"]), "knowledge": knowledge.device_cards(node_id),
            "events": [dict(e) for e in events]}
