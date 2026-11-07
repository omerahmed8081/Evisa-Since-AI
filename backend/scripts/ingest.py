"""
Capture knowledge from conversation files into the graph.

  python scripts/ingest.py data/threads              # all conversations, oldest first (cached Gemini answers reused)
  python scripts/ingest.py data/threads --dry-run    # only print Gemini's output (no Neo4j needed)
  python scripts/ingest.py data/threads --force      # re-process threads already in Neo4j
  python scripts/ingest.py data/threads --refresh    # ignore the Gemini cache (costs API calls)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # make "pipeline" importable

from pipeline.ingest import main

if __name__ == "__main__":
    main()
