"""
NEO4J CONTEXT GRAPH - SIMPLE DEMO (10 Tickets Only)
"""

import os
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables from .env file
load_dotenv()


class SimpleNeo4jDemo:
    """Simple Neo4j context graph with sample tickets."""

    def __init__(self):
        """Connect to Neo4j using .env variables."""
        uri = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")

        if not password:
            raise ValueError("NEO4J_PASSWORD not found in .env file.")

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        print("Connected to Neo4j")

    def close(self):
        """Close connection."""
        self.driver.close()

    def clear_all(self):
        """Clear everything from Neo4j."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        print("Database cleared")

    def extract_info(self, summary: str) -> Dict:
        """Extract simple action/object/problem tags from ticket summary."""
        summary_lower = summary.lower()

        action = None
        if "delete" in summary_lower or "remove" in summary_lower:
            action = "DELETE"
        elif "access" in summary_lower or "permission" in summary_lower:
            action = "ACCESS"
        elif "create" in summary_lower:
            action = "CREATE"
        elif "update" in summary_lower or "move" in summary_lower:
            action = "UPDATE"

        obj = None
        if "opportunity" in summary_lower or "opp" in summary_lower:
            obj = "Opportunity"
        elif "account" in summary_lower:
            obj = "Account"
        elif "onboarding" in summary_lower:
            obj = "Onboarding"

        problem = None
        if "duplicate" in summary_lower:
            problem = "Duplicate"
        elif "access" in summary_lower:
            problem = "Access Issue"

        return {"action": action, "object": obj, "problem": problem}

    def add_ticket(self, ticket_id: str, summary: str):
        """Add one ticket to Neo4j graph."""
        info = self.extract_info(summary)

        with self.driver.session() as session:
            session.run(
                """
                CREATE (t:Ticket {
                    id: $id,
                    summary: $summary
                })
                """,
                id=ticket_id,
                summary=summary,
            )

            if info["action"]:
                session.run(
                    """
                    MATCH (t:Ticket {id: $ticket_id})
                    MERGE (a:Action {name: $action})
                    CREATE (t)-[:HAS_ACTION]->(a)
                    """,
                    ticket_id=ticket_id,
                    action=info["action"],
                )

            if info["object"]:
                session.run(
                    """
                    MATCH (t:Ticket {id: $ticket_id})
                    MERGE (o:Object {name: $object})
                    CREATE (t)-[:HAS_OBJECT]->(o)
                    """,
                    ticket_id=ticket_id,
                    object=info["object"],
                )

            if info["problem"]:
                session.run(
                    """
                    MATCH (t:Ticket {id: $ticket_id})
                    MERGE (p:Problem {name: $problem})
                    CREATE (t)-[:HAS_PROBLEM]->(p)
                    """,
                    ticket_id=ticket_id,
                    problem=info["problem"],
                )

        print(f"Added: {ticket_id}")

    def create_similarity_links(self):
        """Create SIMILAR_TO relationships between tickets with same action + object."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (t1:Ticket)-[:HAS_ACTION]->(a:Action)<-[:HAS_ACTION]-(t2:Ticket)
                MATCH (t1)-[:HAS_OBJECT]->(o:Object)<-[:HAS_OBJECT]-(t2)
                WHERE t1.id < t2.id
                CREATE (t1)-[:SIMILAR_TO {reason: 'Same Action + Object'}]->(t2)
                """
            )

        print("Created similarity links")

    def load_sample_tickets(
        self,
        csv_path: str = "Jira last 6 months.csv",
        limit: int = 10,
        clear_existing: bool = True,
    ) -> int:
        """Load sample tickets from CSV and build graph relationships."""
        if clear_existing:
            self.clear_all()

        df = pd.read_csv(csv_path)
        sample_tickets = df.head(limit)

        for _, row in sample_tickets.iterrows():
            self.add_ticket(str(row["Issue key"]), str(row["Summary"]))

        self.create_similarity_links()
        return len(sample_tickets)

    def _query_exact_matches(self, action: str, obj: str, limit: int) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket)-[:HAS_ACTION]->(a:Action {name: $action})
                MATCH (t)-[:HAS_OBJECT]->(o:Object {name: $object})
                RETURN t.id AS id, t.summary AS summary
                LIMIT $limit
                """,
                action=action,
                object=obj,
                limit=limit,
            )
            return [dict(record) for record in result]

    def _query_action_matches(self, action: str, limit: int) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket)-[:HAS_ACTION]->(a:Action {name: $action})
                RETURN t.id AS id, t.summary AS summary, count(*) AS relevance
                ORDER BY relevance DESC
                LIMIT $limit
                """,
                action=action,
                limit=limit,
            )
            return [dict(record) for record in result]

    def query_similar_tickets(self, new_ticket_summary: str, top_k: int = 3) -> Dict:
        """Return structured similarity results for a new ticket summary."""
        new_info = self.extract_info(new_ticket_summary)
        exact_matches = []
        action_matches = []

        if new_info["action"] and new_info["object"]:
            exact_matches = self._query_exact_matches(
                new_info["action"], new_info["object"], top_k
            )

        if new_info["action"]:
            action_matches = self._query_action_matches(new_info["action"], top_k)

        routing = self.get_routing(new_info)
        return {
            "ticket_summary": new_ticket_summary,
            "extracted": new_info,
            "exact_matches": exact_matches,
            "action_matches": action_matches,
            "routing": routing,
        }

    def find_similar_tickets(self, new_ticket_summary: str, top_k: int = 3):
        """CLI-friendly wrapper that prints structured query results."""
        results = self.query_similar_tickets(new_ticket_summary, top_k=top_k)
        new_info = results["extracted"]

        print("\n" + "=" * 80)
        print(f"NEW TICKET: {new_ticket_summary}")
        print("=" * 80)
        print("\nExtracted:")
        print(f"  Action: {new_info['action']}")
        print(f"  Object: {new_info['object']}")
        print(f"  Problem: {new_info['problem']}")

        exact_matches = results["exact_matches"]
        if new_info["action"] and new_info["object"]:
            if exact_matches:
                print(
                    f"\nFound {len(exact_matches)} similar tickets (Same Action + Object):"
                )
                for i, record in enumerate(exact_matches, 1):
                    print(f"  {i}. {record['id']}")
                    print(f"     {record['summary'][:70]}...")
            else:
                print("\nNo exact matches found")

        if new_info["action"]:
            print(f"\nTickets with same ACTION ({new_info['action']}):")
            for i, record in enumerate(results["action_matches"], 1):
                print(f"  {i}. {record['id']}: {record['summary'][:60]}...")

        print(f"\nROUTING SUGGESTION: {results['routing']}")
        print("=" * 80 + "\n")

    def get_routing(self, info: Dict) -> str:
        """Suggest routing based on extracted info."""
        if info["action"] == "DELETE" and info["problem"] == "Duplicate":
            return "Data Quality Team"
        if info["action"] == "ACCESS":
            return "Salesforce Admin Team"
        if info["action"] == "DELETE":
            return "Data Operations Team"
        if info["action"] == "CREATE":
            return "Data Operations Team"
        return "General Support Queue"

    def get_graph_stats(self) -> Dict:
        """Return graph statistics in a dictionary."""
        with self.driver.session() as session:
            ticket_count = session.run(
                "MATCH (t:Ticket) RETURN count(t) AS ticket_count"
            ).single()["ticket_count"]
            action_count = session.run(
                "MATCH (a:Action) RETURN count(a) AS action_count"
            ).single()["action_count"]
            object_count = session.run(
                "MATCH (o:Object) RETURN count(o) AS object_count"
            ).single()["object_count"]
            similarity_count = session.run(
                "MATCH ()-[r:SIMILAR_TO]->() RETURN count(r) AS similarity_count"
            ).single()["similarity_count"]

        return {
            "ticket_count": ticket_count,
            "action_count": action_count,
            "object_count": object_count,
            "similarity_count": similarity_count,
        }

    def show_graph_stats(self):
        """Print graph statistics."""
        stats = self.get_graph_stats()
        print("\nGRAPH STATISTICS:")
        print(f"  Tickets: {stats['ticket_count']}")
        print(f"  Actions: {stats['action_count']}")
        print(f"  Objects: {stats['object_count']}")
        print(f"  Similarity Links: {stats['similarity_count']}")


def interactive_mode(graph: SimpleNeo4jDemo):
    """Interactive mode to test with custom ticket summaries."""
    print("\n" + "=" * 80)
    print("INTERACTIVE MODE - Test New Tickets")
    print("=" * 80)
    print("\nType a new ticket summary and press enter.")
    print("Type 'quit' to exit.")
    print("=" * 80)

    while True:
        new_ticket = input("\nEnter NEW ticket summary (or 'quit'): ").strip()
        if new_ticket.lower() in ["quit", "exit", "q"]:
            print("\nExiting interactive mode...")
            break
        if not new_ticket:
            print("Please enter a ticket summary.")
            continue
        graph.find_similar_tickets(new_ticket)


def main():
    """Main demo function."""
    print("=" * 80)
    print("NEO4J CONTEXT GRAPH - SIMPLE DEMO (10 Tickets)")
    print("=" * 80)

    graph = SimpleNeo4jDemo()
    graph.load_sample_tickets(limit=10, clear_existing=True)
    graph.show_graph_stats()

    print("\n" + "=" * 80)
    print("DEMO: QUERY THE GRAPH WITH NEW TICKETS")
    print("=" * 80)

    graph.find_similar_tickets("Delete duplicate payment opportunity for XYZ Corp")
    graph.find_similar_tickets("Need Salesforce access to update records")
    graph.find_similar_tickets("Create new onboarding record for ABC Company")

    interactive_mode(graph)
    graph.close()


if __name__ == "__main__":
    main()
