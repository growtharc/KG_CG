# Project Study Guide

This guide explains the codebase in a practical way so you can understand, maintain, and extend it confidently.

## 1) What This Project Is

This project has two graph layers in Neo4j:

- Knowledge Graph (KG): `Ticket`, `Action`, `Object`, `Problem`
- Context Graph (CG): `ContextDocument`, `ContextPage`, `ContextChunk`, `ContextAction`, `ContextObject`, `ContextProblem`

Current intended flow:

1. Ingest text/PDF into **Context Graph**
2. Review/approve context data
3. Later promote approved context into **Knowledge Graph**

At the moment, APIs are wired to existing backend methods and mainly cover ingestion + analysis + stats.

## 2) High-Level Architecture

Main layers:

1. API layer: [api_app.py](/c:/Users/RadhikaAgarwal/Downloads/KG_CG/KG_CG/api_app.py)
2. Service layer: [graph_api_service.py](/c:/Users/RadhikaAgarwal/Downloads/KG_CG/KG_CG/services/graph_api_service.py)
3. Domain/backend graph logic: [main.py](/c:/Users/RadhikaAgarwal/Downloads/KG_CG/KG_CG/main.py)
4. UI layer: [streamlit_app.py](/c:/Users/RadhikaAgarwal/Downloads/KG_CG/KG_CG/streamlit_app.py)

Why this is good:

- Routes are thin (API does request/response and validation)
- Service layer isolates orchestration
- Graph logic lives in one place (`SimpleNeo4jDemo`)

## 3) Core Files and Responsibilities

### `main.py`

Main class: `SimpleNeo4jDemo`

Key responsibilities:

- Neo4j connection and sessions
- KG operations:
  - Add ticket
  - Create similarity links
  - Query similar tickets
  - KG stats
- CG operations:
  - Ensure context constraints
  - Add context from text chunk
  - Parse PDF to chunks
  - Build context graph from PDF
  - Clear context graph
  - CG stats

### `services/graph_api_service.py`

Wraps `SimpleNeo4jDemo` for API use:

- `get_stats`
- `load_sample_tickets`
- `analyze_ticket`
- `ingest_context_manual`
- `ingest_context_pdf`
- `clear_context_graph`

It also handles temporary PDF file handling for API upload ingestion.

### `api_app.py`

FastAPI app exposing endpoints:

- `GET /health`
- `GET /stats`
- `POST /tickets/sample-load`
- `POST /tickets/analyze`
- `POST /context/ingest/manual`
- `POST /context/ingest/pdf`
- `POST /context/clear`

This file should stay thin.

### `api_schemas.py`

Pydantic request models for validation:

- sample load request
- analyze request
- manual context ingest request

### `streamlit_app.py`

UI for:

- Loading sample ticket KG data
- Context graph manual builder
- PDF -> context graph build
- Similar-ticket analysis
- Cypher results panel

## 4) PDF Chunking Strategy (Current)

Current backend uses reference-style chunking:

1. `PyPDFLoader` to load PDF pages
2. `RecursiveCharacterTextSplitter`
3. Chunk cleanup (`replace("\n", " ").strip()`)
4. Per-page chunk indexing and dedupe
5. Context graph writes per chunk

Configurable knobs:

- `chunk_size` (default 200)
- `chunk_overlap` (default 40)
- `max_chunks_per_page`

## 5) Context Graph Schema

Nodes:

- `ContextDocument(id, source, created_at)`
- `ContextPage(id, page_number)`
- `ContextChunk(id, text, source, page_number, chunk_index, updated_at)`
- `ContextAction(name)`
- `ContextObject(name)`
- `ContextProblem(name)`

Relationships:

- `(:ContextDocument)-[:HAS_PAGE]->(:ContextPage)`
- `(:ContextPage)-[:HAS_CHUNK]->(:ContextChunk)`
- `(:ContextChunk)-[:MENTIONS_ACTION]->(:ContextAction)`
- `(:ContextChunk)-[:MENTIONS_OBJECT]->(:ContextObject)`
- `(:ContextChunk)-[:MENTIONS_PROBLEM]->(:ContextProblem)`

## 6) Knowledge Graph Schema

Nodes:

- `Ticket(id, summary, ...)`
- `Action(name)`
- `Object(name)`
- `Problem(name)`

Relationships:

- `(:Ticket)-[:HAS_ACTION]->(:Action)`
- `(:Ticket)-[:HAS_OBJECT]->(:Object)`
- `(:Ticket)-[:HAS_PROBLEM]->(:Problem)`
- `(:Ticket)-[:SIMILAR_TO]->(:Ticket)`

## 7) End-to-End Flow Examples

### Manual context ingestion

1. Call `POST /context/ingest/manual`
2. API validates request
3. Service calls `create_context_graph_from_summary`
4. Backend writes context nodes/edges
5. Returns chunk trace data

### PDF ingestion

1. Call `POST /context/ingest/pdf` with file
2. Service writes upload bytes to temp file
3. Backend parses + chunks + extracts + writes context graph
4. Returns processing summary + chunking config + stats
5. Service removes temp file

## 8) Important Environment + Run Commands

Activate Python 3.12 env:

```powershell
.\.venv312\Scripts\Activate.ps1
```

Run API:

```powershell
uvicorn api_app:app --host 127.0.0.1 --port 8000 --reload
```

Swagger:

`http://127.0.0.1:8000/docs`

Run Streamlit:

```powershell
streamlit run .\streamlit_app.py
```

## 9) Common Failure Points

1. Neo4j not running -> API endpoints fail except `/health`
2. Wrong Neo4j URI/password in `.env`
3. PDF endpoint called with JSON instead of multipart file upload
4. Missing dependencies in active virtual environment

## 10) Study Path (Recommended)

1. Read `api_app.py` first (public contract)
2. Read `graph_api_service.py` (orchestration)
3. Read CG methods in `main.py`
4. Read KG methods in `main.py`
5. Trace one request in Swagger from endpoint -> service -> backend writes

## 11) Next Improvements (When You’re Ready)

1. Add approval workflow endpoints backed by existing graph model
2. Add structured logs + request IDs
3. Add unit tests for service methods
4. Add integration test against a local Neo4j test instance
