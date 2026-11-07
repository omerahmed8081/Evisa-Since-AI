"""
Load the inventory and the event stream into Neo4j.

  python scripts/load_inventory.py                       # data/inventory/nodes.csv + data/events/events.json
  python scripts/load_inventory.py path/to/nodes.csv path/to/events.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make "pipeline" importable

from pipeline import DATA_DIR, graph

nodes_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "inventory" / "nodes.csv"
events_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DATA_DIR / "events" / "events.json"

graph.setup_constraints()
print(f"Loaded {graph.load_inventory(nodes_path)} devices from {nodes_path}")
if events_path.exists():
    print(f"Loaded {graph.load_events(events_path)} events from {events_path}")
