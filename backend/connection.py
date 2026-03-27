import os

from dotenv import load_dotenv
from neo4j import GraphDatabase


def create_driver():
    """Create Neo4j driver from environment variables."""
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise ValueError("NEO4J_PASSWORD not found in .env file.")

    return GraphDatabase.driver(uri, auth=(user, password))
