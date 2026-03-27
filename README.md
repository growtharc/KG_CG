# KG_CG

Context Graph + Knowledge Graph demo using Neo4j and Streamlit.

## What this project does

- Builds a **Knowledge Graph** for tickets (`Ticket`, `Action`, `Object`, `Problem`)
- Builds a separate **Context Graph** namespace (`ContextDocument`, `ContextPage`, `ContextChunk`, etc.)
- Supports manual context chunk creation from unstructured text
- Supports PDF-to-Context-Graph ingestion (no direct KG update from PDF)

## Prerequisites

- Python 3.12+
- Neo4j running locally (or reachable URI)
- A `.env` file with:
  - `NEO4J_URI`
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`

## Setup

```powershell
python -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Streamlit app

```powershell
.\.venv312\Scripts\Activate.ps1
streamlit run .\ui\streamlit_app.py
```

## Run FastAPI (hardcoded backend mode)

```powershell
.\.venv312\Scripts\Activate.ps1
uvicorn api.api_app:app --host 127.0.0.1 --port 8000 --reload
```

## Test API endpoints

```powershell
.\.venv312\Scripts\Activate.ps1
python .\tests\test_api_smoke.py
```

## Notes

- CSV and `.env` are ignored by Git.
- Context Graph is intentionally separated from KG updates.
- Promotion from Context Graph to KG should happen only after user approval.

## Study Guide

For detailed architecture and code walkthrough notes, see:

- [STUDY_GUIDE.md](/c:/Users/RadhikaAgarwal/Downloads/KG_CG/KG_CG/STUDY_GUIDE.md)
