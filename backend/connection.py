import os
import time

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable


def create_driver(max_retries: int = 3, retry_delay: float = 2.0):
    """Create and verify a Neo4j driver from environment variables.

    Retries on transient errors (rate limit, service unavailable).
    Raises a clear error on auth failure.
    """
    # Always reload so changes to .env are picked up without restart
    load_dotenv(override=True)

    uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    if not password:
        raise ValueError(
            "NEO4J_PASSWORD not set. Add it to your .env file:\n"
            "  NEO4J_PASSWORD=your_password_here"
        )

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            driver = GraphDatabase.driver(
                uri,
                auth=(user, password),
                connection_timeout=10,
                max_connection_lifetime=3600,
            )
            # Verify connectivity immediately so we fail fast with a clear message
            driver.verify_connectivity()
            return driver

        except AuthError as e:
            # Wrong password — no point retrying
            raise ConnectionError(
                f"Neo4j authentication failed for user '{user}' at {uri}.\n"
                f"Check NEO4J_PASSWORD in your .env file.\n"
                f"Original error: {e}"
            ) from e

        except ServiceUnavailable as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(retry_delay)
            continue

        except Exception as e:
            msg = str(e)
            # Rate limit — wait longer and retry
            if "RateLimit" in msg or "rate" in msg.lower():
                last_error = e
                if attempt < max_retries:
                    time.sleep(retry_delay * attempt)
                continue
            # Auth failure surfaced as generic exception
            if "Unauthorized" in msg or "authentication" in msg.lower():
                raise ConnectionError(
                    f"Neo4j authentication failed for user '{user}' at {uri}.\n"
                    f"Check NEO4J_PASSWORD in your .env file.\n"
                    f"Original error: {e}"
                ) from e
            raise

    raise ConnectionError(
        f"Could not connect to Neo4j at {uri} after {max_retries} attempts.\n"
        f"Make sure Neo4j Desktop is running and the database is started.\n"
        f"Last error: {last_error}"
    )
