from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List

DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_OVERLAP = 40


class ContextGraphService:
    def __init__(self, driver, extract_info_fn: Callable[[str], Dict]):
        self.driver = driver
        self.extract_info = extract_info_fn

    def ensure_context_graph_schema(self):
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

    def parse_unstructured_pdf_to_context_chunks(
        self,
        pdf_path: str,
        max_chunks_per_page: int = 30,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[Dict]:
        from langchain_community.document_loaders import PyPDFLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter

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
            "context_stats": self.get_context_graph_stats(),
        }
