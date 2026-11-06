"""
Delete everything in the Neo4j database (e.g. to remove the sample data before loading the full dataset).

  python reset_graph.py
"""
from dotenv import load_dotenv

import graph

load_dotenv()
answer = input("This deletes ALL nodes and relationships in the database. Type 'yes' to continue: ")
if answer.strip().lower() == "yes":
    graph.run("MATCH (n) DETACH DELETE n")
    print("Database is empty.")
else:
    print("Nothing deleted.")
