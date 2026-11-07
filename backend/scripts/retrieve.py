"""
What does the graph know that applies to a device? (no Gemini calls)

  python scripts/retrieve.py TRN-077
  python scripts/retrieve.py TRN-042 --symptoms TRAFFIC_COUNTERS_ZERO INTERFACE_UP --events SFP_REPLACEMENT
  python scripts/retrieve.py TRN-077 --json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make "pipeline" importable

from pipeline.retrieve import find_knowledge, print_readable

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("node_id")
    parser.add_argument("--symptoms", nargs="*")
    parser.add_argument("--events", nargs="*")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    out = find_knowledge(args.node_id, args.symptoms, args.events)
    print(json.dumps(out, indent=2, ensure_ascii=False, default=list) if args.json else "")
    if not args.json:
        print_readable(out)
