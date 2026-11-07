"""Deletes everything in the Neo4j database.

    python scripts/reset_graph.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import graph

answer = input("This deletes ALL nodes and relationships in the database. Type 'yes' to continue: ")
if answer.strip().lower() == "yes":
    graph.run("MATCH (n) DETACH DELETE n")
    print("Database is empty.")
else:
    print("Nothing deleted.")
