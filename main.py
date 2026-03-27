"""
NEO4J CONTEXT GRAPH - SIMPLE DEMO (10 Tickets Only)
"""

from typing import Dict

from backend.common import extract_info, get_routing
from backend.connection import create_driver
from backend.context_service import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    ContextGraphService,
)
from backend.kg_service import KnowledgeGraphService


class SimpleNeo4jDemo:
    """Compatibility facade over decoupled backend services."""

    def __init__(self):
        self.driver = create_driver()
        self.kg = KnowledgeGraphService(self.driver, extract_info, get_routing)
        self.context = ContextGraphService(self.driver, extract_info)
        print("Connected to Neo4j")

    def close(self):
        self.driver.close()

    # Shared helpers
    def extract_info(self, summary: str) -> Dict:
        return extract_info(summary)

    def get_routing(self, info: Dict) -> str:
        return get_routing(info)

    # KG methods
    def clear_all(self):
        self.kg.clear_all()
        print("Database cleared")

    def add_ticket(self, ticket_id: str, summary: str):
        self.kg.add_ticket(ticket_id, summary)
        print(f"Added: {ticket_id}")

    def add_ticket_with_trace(self, summary: str, ticket_id: str = "") -> Dict:
        return self.kg.add_ticket_with_trace(summary, ticket_id)

    def create_similarity_links(self):
        self.kg.create_similarity_links()
        print("Created similarity links")

    def load_sample_tickets(
        self,
        csv_path: str = "data/Jira last 6 months.csv",
        limit: int = 10,
        clear_existing: bool = True,
    ) -> int:
        return self.kg.load_sample_tickets(csv_path, limit, clear_existing)

    def query_similar_tickets(self, new_ticket_summary: str, top_k: int = 3) -> Dict:
        return self.kg.query_similar_tickets(new_ticket_summary, top_k=top_k)

    def get_graph_stats(self) -> Dict:
        return self.kg.get_graph_stats()

    def show_graph_stats(self):
        stats = self.get_graph_stats()
        print("\nGRAPH STATISTICS:")
        print(f"  Tickets: {stats['ticket_count']}")
        print(f"  Actions: {stats['action_count']}")
        print(f"  Objects: {stats['object_count']}")
        print(f"  Similarity Links: {stats['similarity_count']}")

    def find_similar_tickets(self, new_ticket_summary: str, top_k: int = 3):
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

    # Context methods
    def ensure_context_graph_schema(self):
        self.context.ensure_context_graph_schema()

    def clear_context_graph(self):
        self.context.clear_context_graph()

    def create_context_graph_from_summary(
        self,
        summary: str,
        document_id: str = "",
        page_number: int = 1,
        chunk_index: int = 1,
        source: str = "manual",
    ) -> Dict:
        return self.context.create_context_graph_from_summary(
            summary=summary,
            document_id=document_id,
            page_number=page_number,
            chunk_index=chunk_index,
            source=source,
        )

    def get_context_graph_stats(self) -> Dict:
        return self.context.get_context_graph_stats()

    def parse_unstructured_pdf_to_context_chunks(
        self,
        pdf_path: str,
        max_chunks_per_page: int = 30,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        return self.context.parse_unstructured_pdf_to_context_chunks(
            pdf_path=pdf_path,
            max_chunks_per_page=max_chunks_per_page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def build_context_graph_from_pdf(
        self,
        pdf_path: str,
        document_id: str = "",
        source: str = "pdf_upload",
        max_chunks_per_page: int = 30,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        clear_existing_context: bool = False,
    ) -> Dict:
        return self.context.build_context_graph_from_pdf(
            pdf_path=pdf_path,
            document_id=document_id,
            source=source,
            max_chunks_per_page=max_chunks_per_page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            clear_existing_context=clear_existing_context,
        )


def interactive_mode(graph: SimpleNeo4jDemo):
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
