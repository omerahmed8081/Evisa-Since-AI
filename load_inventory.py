"""
Load the inventory (and optionally the event stream) into Neo4j.

  python load_inventory.py data/inventory/nodes.csv
  python load_inventory.py data/inventory/nodes.csv data/events/events.json
  python load_inventory.py          (defaults to data/inventory/nodes.csv + data/events/events.json)
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

import graph

load_dotenv()
nodes_path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/inventory/nodes.csv")
graph.setup_constraints()
print(f"Loaded {graph.load_inventory(nodes_path)} devices from {nodes_path}")
events_path = Path(sys.argv[2] if len(sys.argv) > 2 else "data/events/events.json")
if events_path.exists():
    print(f"Loaded {graph.load_events(events_path)} events from {events_path}")
