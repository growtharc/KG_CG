from typing import Optional

from pydantic import BaseModel, Field


class TicketAnalyzeRequest(BaseModel):
    summary: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=20)


class SampleLoadRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=5000)
    csv_path: str = Field(default="data/Jira last 6 months.csv")


class ContextManualIngestRequest(BaseModel):
    text: str = Field(min_length=3, max_length=10000)
    document_id: Optional[str] = None
    page_number: int = Field(default=1, ge=1)
    chunk_index: int = Field(default=1, ge=1)
    source: str = Field(default="manual")
