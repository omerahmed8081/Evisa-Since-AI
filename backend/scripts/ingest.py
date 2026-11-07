"""Captures conversations into the graph.

    python scripts/ingest.py data/threads              # all, oldest first (cached Gemini answers reused)
    python scripts/ingest.py data/threads --dry-run    # print extractions only, no Neo4j
    python scripts/ingest.py data/threads --force      # re-process already captured conversations
    python scripts/ingest.py data/threads --prefilter  # skip noise locally before Gemini"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.ingest import main

if __name__ == "__main__":
    main()
