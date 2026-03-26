from datetime import datetime
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field


app = FastAPI(
    title="KG_CG API",
    version="0.1.0",
    description="Hardcoded API scaffold for Context Graph and KG flow.",
)


# In-memory store for initial API testing.
FAKE_DB: Dict = {
    "kg_stats": {
        "ticket_count": 10,
        "action_count": 4,
        "object_count": 3,
        "similarity_count": 6,
    },
    "context_stats": {
        "document_count": 0,
        "page_count": 0,
        "chunk_count": 0,
        "action_count": 0,
        "object_count": 0,
        "problem_count": 0,
    },
    "context_documents": {},
    "approved_chunk_ids": set(),
}


def _extract_stub(text: str) -> Dict[str, Optional[str]]:
    lower = text.lower()
    action = None
    if "delete" in lower or "remove" in lower:
        action = "DELETE"
    elif "access" in lower or "permission" in lower:
        action = "ACCESS"
    elif "create" in lower:
        action = "CREATE"
    elif "update" in lower or "move" in lower:
        action = "UPDATE"

    obj = None
    if "opportunity" in lower or "opp" in lower:
        obj = "Opportunity"
    elif "account" in lower:
        obj = "Account"
    elif "onboarding" in lower:
        obj = "Onboarding"

    problem = None
    if "duplicate" in lower:
        problem = "Duplicate"
    elif "access" in lower:
        problem = "Access Issue"

    return {"action": action, "object": obj, "problem": problem}


class TicketAnalyzeRequest(BaseModel):
    summary: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=20)


class SampleLoadRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=5000)


class ContextManualIngestRequest(BaseModel):
    text: str = Field(min_length=3, max_length=10000)
    document_id: Optional[str] = None
    page_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(default=1, ge=1)
    source: str = Field(default="manual")


class ContextApproveRequest(BaseModel):
    chunk_ids: List[str] = Field(min_length=1)
    approved: Literal[True, False] = True


class KgPromoteRequest(BaseModel):
    document_id: Optional[str] = None
    chunk_ids: List[str] = Field(default_factory=list)


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/stats")
def get_stats():
    return {
        "kg": FAKE_DB["kg_stats"],
        "context": FAKE_DB["context_stats"],
        "approved_chunk_count": len(FAKE_DB["approved_chunk_ids"]),
    }


@app.post("/tickets/sample-load")
def load_sample_tickets(payload: SampleLoadRequest):
    FAKE_DB["kg_stats"]["ticket_count"] = payload.limit
    return {
        "message": "Sample load simulated.",
        "loaded": payload.limit,
        "kg_stats": FAKE_DB["kg_stats"],
    }


@app.post("/tickets/analyze")
def analyze_ticket(payload: TicketAnalyzeRequest):
    extracted = _extract_stub(payload.summary)
    return {
        "summary": payload.summary,
        "top_k": payload.top_k,
        "extracted": extracted,
        "routing": "General Support Queue",
        "matches": [
            {"id": "SIM-001", "summary": "Stub similar ticket 1"},
            {"id": "SIM-002", "summary": "Stub similar ticket 2"},
        ][: payload.top_k],
    }


@app.post("/context/ingest/manual")
def ingest_context_manual(payload: ContextManualIngestRequest):
    document_id = payload.document_id or f"CTXDOC-{uuid4().hex[:8].upper()}"
    chunk_id = f"{document_id}-P{payload.page_number:04d}-C{payload.chunk_index:04d}"
    extracted = _extract_stub(payload.text)

    doc = FAKE_DB["context_documents"].setdefault(
        document_id, {"document_id": document_id, "chunks": []}
    )
    doc["chunks"].append(
        {
            "chunk_id": chunk_id,
            "text": payload.text,
            "page_number": payload.page_number,
            "chunk_index": payload.chunk_index,
            "source": payload.source,
            "extracted": extracted,
            "approved": False,
        }
    )

    FAKE_DB["context_stats"]["document_count"] = len(FAKE_DB["context_documents"])
    FAKE_DB["context_stats"]["chunk_count"] += 1
    FAKE_DB["context_stats"]["page_count"] = max(
        FAKE_DB["context_stats"]["page_count"], payload.page_number
    )
    if extracted["action"]:
        FAKE_DB["context_stats"]["action_count"] += 1
    if extracted["object"]:
        FAKE_DB["context_stats"]["object_count"] += 1
    if extracted["problem"]:
        FAKE_DB["context_stats"]["problem_count"] += 1

    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "extracted": extracted,
        "message": "Context chunk ingested (hardcoded mode).",
    }


@app.post("/context/ingest/pdf")
async def ingest_context_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    document_id = f"CTXPDF-{uuid4().hex[:8].upper()}"
    sample_text = (
        "Delete duplicate opportunity record for uploaded PDF ticket context."
    )
    chunk_id = f"{document_id}-P0001-C0001"
    extracted = _extract_stub(sample_text)

    FAKE_DB["context_documents"][document_id] = {
        "document_id": document_id,
        "chunks": [
            {
                "chunk_id": chunk_id,
                "text": sample_text,
                "page_number": 1,
                "chunk_index": 1,
                "source": "pdf_upload",
                "extracted": extracted,
                "approved": False,
            }
        ],
    }
    FAKE_DB["context_stats"]["document_count"] = len(FAKE_DB["context_documents"])
    FAKE_DB["context_stats"]["chunk_count"] += 1
    FAKE_DB["context_stats"]["page_count"] = max(
        FAKE_DB["context_stats"]["page_count"], 1
    )
    if extracted["action"]:
        FAKE_DB["context_stats"]["action_count"] += 1
    if extracted["object"]:
        FAKE_DB["context_stats"]["object_count"] += 1
    if extracted["problem"]:
        FAKE_DB["context_stats"]["problem_count"] += 1

    return {
        "document_id": document_id,
        "processed_chunks": 1,
        "message": "PDF ingest simulated (hardcoded mode).",
    }


@app.get("/context/documents/{document_id}")
def get_context_document(document_id: str):
    document = FAKE_DB["context_documents"].get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@app.post("/context/approve")
def approve_context(payload: ContextApproveRequest):
    found = 0
    for document in FAKE_DB["context_documents"].values():
        for chunk in document["chunks"]:
            if chunk["chunk_id"] in payload.chunk_ids:
                chunk["approved"] = payload.approved
                found += 1
                if payload.approved:
                    FAKE_DB["approved_chunk_ids"].add(chunk["chunk_id"])
                else:
                    FAKE_DB["approved_chunk_ids"].discard(chunk["chunk_id"])

    return {
        "updated_chunks": found,
        "approved": payload.approved,
        "approved_chunk_count": len(FAKE_DB["approved_chunk_ids"]),
    }


@app.post("/kg/promote")
def promote_to_kg(payload: KgPromoteRequest):
    target_chunks = set(payload.chunk_ids)

    if payload.document_id and payload.document_id in FAKE_DB["context_documents"]:
        for chunk in FAKE_DB["context_documents"][payload.document_id]["chunks"]:
            target_chunks.add(chunk["chunk_id"])

    approved_targets = [
        chunk_id for chunk_id in target_chunks if chunk_id in FAKE_DB["approved_chunk_ids"]
    ]

    # Hardcoded KG promotion simulation.
    FAKE_DB["kg_stats"]["ticket_count"] += len(approved_targets)

    return {
        "message": "KG promotion simulated (hardcoded mode).",
        "promoted_count": len(approved_targets),
        "kg_stats": FAKE_DB["kg_stats"],
    }
