from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from api.api_schemas import (
    ContextManualIngestRequest,
    SampleLoadRequest,
    TicketAnalyzeRequest,
)
from main import SimpleNeo4jDemo
from services.graph_api_service import GraphApiService


app = FastAPI(
    title="KG_CG API",
    version="0.2.0",
    description="Decoupled API routes with real backend service integration.",
)

_service: GraphApiService | None = None


def get_service() -> GraphApiService:
    global _service
    if _service is None:
        _service = GraphApiService(graph=SimpleNeo4jDemo())
    return _service


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/stats")
def get_stats():
    try:
        service = get_service()
        return service.get_stats()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Stats fetch failed: {exc}") from exc


@app.post("/tickets/sample-load")
def load_sample_tickets(payload: SampleLoadRequest):
    try:
        service = get_service()
        return service.load_sample_tickets(limit=payload.limit, csv_path=payload.csv_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Sample load failed: {exc}") from exc


@app.post("/tickets/analyze")
def analyze_ticket(payload: TicketAnalyzeRequest):
    try:
        service = get_service()
        return service.analyze_ticket(summary=payload.summary, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Analyze failed: {exc}") from exc


@app.post("/context/ingest/manual")
def ingest_context_manual(payload: ContextManualIngestRequest):
    try:
        service = get_service()
        return service.ingest_context_manual(
            text=payload.text,
            document_id=payload.document_id or "",
            page_number=payload.page_number,
            chunk_index=payload.chunk_index,
            source=payload.source,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Manual context ingest failed: {exc}") from exc


@app.post("/context/ingest/pdf")
async def ingest_context_pdf(
    file: UploadFile = File(...),
    document_id: str = Query(default=""),
    source: str = Query(default="pdf_upload"),
    max_chunks_per_page: int = Query(default=30, ge=1, le=200),
    chunk_size: int = Query(default=200, ge=50, le=2000),
    chunk_overlap: int = Query(default=40, ge=0, le=500),
    clear_existing_context: bool = Query(default=False),
):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    try:
        service = get_service()
        return service.ingest_context_pdf(
            file_bytes=data,
            document_id=document_id,
            source=source,
            max_chunks_per_page=max_chunks_per_page,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            clear_existing_context=clear_existing_context,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"PDF context ingest failed: {exc}") from exc


@app.post("/context/clear")
def clear_context_graph():
    try:
        service = get_service()
        return service.clear_context_graph()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Context clear failed: {exc}") from exc
