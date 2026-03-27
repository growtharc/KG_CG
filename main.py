"""
NEO4J CONTEXT GRAPH - SIMPLE DEMO (10 Tickets Only)
"""

import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_OVERLAP = 40

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

    def ensure_context_graph_schema(self):
        """Create constraints for the context graph namespace."""
        statements = [
            "CREATE CONSTRAINT context_document_id IF NOT EXISTS FOR (d:ContextDocument) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT context_page_id IF NOT EXISTS FOR (p:ContextPage) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT context_chunk_id IF NOT EXISTS FOR (c:ContextChunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT context_action_name IF NOT EXISTS FOR (a:ContextAction) REQUIRE a.name IS UNIQUE",
            "CREATE CONSTRAINT context_object_name IF NOT EXISTS FOR (o:ContextObject) REQUIRE o.name IS UNIQUE",
            "CREATE CONSTRAINT context_problem_name IF NOT EXISTS FOR (p:ContextProblem) REQUIRE p.name IS UNIQUE",
        ]
        with self.driver.session() as session:
            for statement in statements:
                session.run(statement)

    def clear_context_graph(self):
        """Delete only context graph nodes/relationships."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (n)
                WHERE n:ContextDocument
                   OR n:ContextPage
                   OR n:ContextChunk
                   OR n:ContextAction
                   OR n:ContextObject
                   OR n:ContextProblem
                DETACH DELETE n
                """
            )

    def create_context_graph_from_summary(
        self,
        summary: str,
        document_id: str = "",
        page_number: int = 1,
        chunk_index: int = 1,
        source: str = "manual",
    ) -> Dict:
        """
        Create context graph nodes from one unstructured text chunk.
        This does not update Ticket/Action/Object/Problem KG labels.
        """
        self.ensure_context_graph_schema()
        extracted = self.extract_info(summary)

        final_document_id = document_id.strip() or f"CTXDOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        page_id = f"{final_document_id}-P{int(page_number):04d}"
        chunk_id = f"{page_id}-C{int(chunk_index):04d}"

        with self.driver.session() as session:
            session.run(
                """
                MERGE (d:ContextDocument {id: $document_id})
                ON CREATE SET d.source = $source, d.created_at = datetime()
                MERGE (p:ContextPage {id: $page_id})
                ON CREATE SET p.page_number = $page_number
                MERGE (d)-[:HAS_PAGE]->(p)
                MERGE (c:ContextChunk {id: $chunk_id})
                SET c.text = $summary,
                    c.source = $source,
                    c.page_number = $page_number,
                    c.chunk_index = $chunk_index,
                    c.updated_at = datetime()
                MERGE (p)-[:HAS_CHUNK]->(c)
                """,
                document_id=final_document_id,
                page_id=page_id,
                page_number=int(page_number),
                chunk_id=chunk_id,
                summary=summary,
                source=source,
                chunk_index=int(chunk_index),
            )

            if extracted["action"]:
                session.run(
                    """
                    MATCH (c:ContextChunk {id: $chunk_id})
                    MERGE (a:ContextAction {name: $action})
                    MERGE (c)-[:MENTIONS_ACTION]->(a)
                    """,
                    chunk_id=chunk_id,
                    action=extracted["action"],
                )

            if extracted["object"]:
                session.run(
                    """
                    MATCH (c:ContextChunk {id: $chunk_id})
                    MERGE (o:ContextObject {name: $object})
                    MERGE (c)-[:MENTIONS_OBJECT]->(o)
                    """,
                    chunk_id=chunk_id,
                    object=extracted["object"],
                )

            if extracted["problem"]:
                session.run(
                    """
                    MATCH (c:ContextChunk {id: $chunk_id})
                    MERGE (p:ContextProblem {name: $problem})
                    MERGE (c)-[:MENTIONS_PROBLEM]->(p)
                    """,
                    chunk_id=chunk_id,
                    problem=extracted["problem"],
                )

        return {
            "document_id": final_document_id,
            "page_id": page_id,
            "chunk_id": chunk_id,
            "summary": summary,
            "extracted": extracted,
        }

    def get_context_graph_stats(self) -> Dict:
        """Return context graph statistics."""
        with self.driver.session() as session:
            document_count = session.run(
                "MATCH (d:ContextDocument) RETURN count(d) AS c"
            ).single()["c"]
            page_count = session.run(
                "MATCH (p:ContextPage) RETURN count(p) AS c"
            ).single()["c"]
            chunk_count = session.run(
                "MATCH (c:ContextChunk) RETURN count(c) AS c"
            ).single()["c"]
            action_count = session.run(
                "MATCH (a:ContextAction) RETURN count(a) AS c"
            ).single()["c"]
            object_count = session.run(
                "MATCH (o:ContextObject) RETURN count(o) AS c"
            ).single()["c"]
            problem_count = session.run(
                "MATCH (p:ContextProblem) RETURN count(p) AS c"
            ).single()["c"]

        return {
            "document_count": document_count,
            "page_count": page_count,
            "chunk_count": chunk_count,
            "action_count": action_count,
            "object_count": object_count,
            "problem_count": problem_count,
        }

    def _normalize_pdf_text(self, text: str) -> str:
        """Normalize noisy PDF text while keeping sentence meaning."""
        cleaned = text.replace("\r", "\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"(?i)^page\s+\d+\s*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"(?i)^confidential.*$", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"(?i)^copyright.*$", "", cleaned, flags=re.MULTILINE)
        return cleaned.strip()

    def _split_unstructured_text_to_chunks(self, text: str) -> List[str]:
        """
        Split unstructured text into context chunks.
        Heuristics:
        - Use blank-line blocks first
        - Then split oversized blocks by sentence boundaries
        """
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        chunks: List[str] = []

        for block in blocks:
            block = re.sub(r"^(\d+[\).]|[-*]|\([a-zA-Z]\))\s*", "", block).strip()
            if len(block) < 20:
                continue

            if len(block) <= 350:
                chunks.append(block)
                continue

            # Split long blocks by sentence-like boundaries.
            sentences = re.split(r"(?<=[\.\?\!])\s+", block)
            current = []
            current_len = 0
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if current_len + len(sentence) + 1 > 320 and current:
                    merged = " ".join(current).strip()
                    if len(merged) >= 20:
                        chunks.append(merged)
                    current = [sentence]
                    current_len = len(sentence)
                else:
                    current.append(sentence)
                    current_len += len(sentence) + 1
            if current:
                merged = " ".join(current).strip()
                if len(merged) >= 20:
                    chunks.append(merged)

        # De-duplicate while preserving order
        unique_chunks: List[str] = []
        seen = set()
        for chunk in chunks:
            key = chunk.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_chunks.append(chunk)
        return unique_chunks

    def parse_unstructured_pdf_to_context_chunks(
        self,
        pdf_path: str,
        max_chunks_per_page: int = 30,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[Dict]:
        """
        Parse PDF into page-aware context chunks.
        Returns list of dicts with page_number, chunk_index, text.
        """
        try:
            # Keep imports local so API startup remains lightweight and explicit.
            from langchain_community.document_loaders import PyPDFLoader
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError as exc:
            raise ImportError(
                "PDF chunking requires langchain-community and langchain-text-splitters."
            ) from exc

        loader = PyPDFLoader(pdf_path)
        pages = loader.load_and_split()
        if not pages:
            return []

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(chunk_size),
            chunk_overlap=int(chunk_overlap),
        )
        docs = splitter.split_documents(pages)

        parsed_chunks: List[Dict] = []
        per_page_counts = defaultdict(int)
        seen = set()

        for doc in docs:
            page_number = int(doc.metadata.get("page", 0)) + 1
            if per_page_counts[page_number] >= int(max_chunks_per_page):
                continue

            text = (doc.page_content or "").replace("\n", " ").strip()
            if not text:
                continue

            dedup_key = (page_number, text.lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            per_page_counts[page_number] += 1
            parsed_chunks.append(
                {
                    "page_number": page_number,
                    "chunk_index": per_page_counts[page_number],
                    "text": text,
                }
            )

        return parsed_chunks

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
        """
        Build Context Graph from PDF only.
        This method intentionally does not update the KG schema.
        """
        self.ensure_context_graph_schema()
        if clear_existing_context:
            self.clear_context_graph()

        final_document_id = (
            document_id.strip() or f"CTXPDF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        parsed_chunks = self.parse_unstructured_pdf_to_context_chunks(
            pdf_path,
            max_chunks_per_page=max_chunks_per_page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        traces = []
        for item in parsed_chunks:
            trace = self.create_context_graph_from_summary(
                summary=item["text"],
                document_id=final_document_id,
                page_number=int(item["page_number"]),
                chunk_index=int(item["chunk_index"]),
                source=source,
            )
            traces.append(trace)

        stats = self.get_context_graph_stats()
        return {
            "document_id": final_document_id,
            "processed_chunks": len(traces),
            "parsed_chunks": parsed_chunks,
            "sample_traces": traces[:10],
            "chunking_config": {
                "chunk_size": int(chunk_size),
                "chunk_overlap": int(chunk_overlap),
                "max_chunks_per_page": int(max_chunks_per_page),
            },
            "context_stats": stats,
        }

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

    def add_ticket_with_trace(self, summary: str, ticket_id: str = "") -> Dict:
        """
        Add one ticket and return a context-to-KG trace.
        This is useful to inspect how extracted context became graph entities.
        """
        final_ticket_id = ticket_id.strip() or f"DEMO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        extracted = self.extract_info(summary)
        self.add_ticket(final_ticket_id, summary)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Ticket {id: $ticket_id})
                OPTIONAL MATCH (t)-[r]->(x)
                RETURN t.id AS ticket_id,
                       t.summary AS ticket_summary,
                       type(r) AS relationship,
                       labels(x) AS target_labels,
                       x.name AS target_name
                ORDER BY relationship
                """,
                ticket_id=final_ticket_id,
            )
            rows = [dict(record) for record in result]

        return {
            "ticket_id": final_ticket_id,
            "summary": summary,
            "extracted": extracted,
            "routing": self.get_routing(extracted),
            "write_cypher": [
                "CREATE (t:Ticket {id: $id, summary: $summary})",
                "MATCH (t:Ticket {id: $ticket_id}) MERGE (a:Action {name: $action}) CREATE (t)-[:HAS_ACTION]->(a)",
                "MATCH (t:Ticket {id: $ticket_id}) MERGE (o:Object {name: $object}) CREATE (t)-[:HAS_OBJECT]->(o)",
                "MATCH (t:Ticket {id: $ticket_id}) MERGE (p:Problem {name: $problem}) CREATE (t)-[:HAS_PROBLEM]->(p)",
            ],
            "created_links": rows,
        }

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
