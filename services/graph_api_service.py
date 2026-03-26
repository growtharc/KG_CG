from __future__ import annotations

from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from typing import Dict

from main import SimpleNeo4jDemo


@dataclass
class GraphApiService:
    graph: SimpleNeo4jDemo

    def get_stats(self) -> Dict:
        return {
            "kg": self.graph.get_graph_stats(),
            "context": self.graph.get_context_graph_stats(),
        }

    def load_sample_tickets(self, limit: int, csv_path: str = "Jira last 6 months.csv") -> Dict:
        loaded = self.graph.load_sample_tickets(
            csv_path=csv_path,
            limit=limit,
            clear_existing=True,
        )
        return {
            "message": "Sample tickets loaded.",
            "loaded": loaded,
            "kg_stats": self.graph.get_graph_stats(),
        }

    def analyze_ticket(self, summary: str, top_k: int) -> Dict:
        result = self.graph.query_similar_tickets(summary, top_k=top_k)
        return {
            "summary": summary,
            "top_k": top_k,
            "extracted": result["extracted"],
            "routing": result["routing"],
            "exact_matches": result["exact_matches"],
            "action_matches": result["action_matches"],
        }

    def ingest_context_manual(
        self,
        text: str,
        document_id: str,
        page_number: int,
        chunk_index: int,
        source: str,
    ) -> Dict:
        return self.graph.create_context_graph_from_summary(
            summary=text,
            document_id=document_id,
            page_number=page_number,
            chunk_index=chunk_index,
            source=source,
        )

    def ingest_context_pdf(
        self,
        file_bytes: bytes,
        document_id: str,
        source: str,
        max_chunks_per_page: int,
        clear_existing_context: bool,
    ) -> Dict:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(file_bytes)
            temp_path = temp_file.name

        try:
            return self.graph.build_context_graph_from_pdf(
                pdf_path=temp_path,
                document_id=document_id,
                source=source,
                max_chunks_per_page=max_chunks_per_page,
                clear_existing_context=clear_existing_context,
            )
        finally:
            try:
                import os

                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass

    def clear_context_graph(self) -> Dict:
        self.graph.clear_context_graph()
        return {
            "message": "Context graph cleared.",
            "context_stats": self.graph.get_context_graph_stats(),
        }
