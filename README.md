# KG_CG

Context Graph + Knowledge Graph demo using Neo4j and Streamlit.

## What this project does

- Builds a **Knowledge Graph** for tickets (`Ticket`, `Action`, `Object`, `Problem`)
- Builds a separate **Context Graph** namespace (`ContextDocument`, `ContextPage`, `ContextChunk`, etc.)
- Supports manual context chunk creation from unstructured text
- Supports PDF-to-Context-Graph ingestion (no direct KG update from PDF)

## Prerequisites

- python version 3.12+
- Neo4j running locally (or reachable URI)
- A `.env` file with:
  - `NEO4J_URI`
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`

## Setup

```powershell
python -m venv fresh_env
.\fresh_env\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Streamlit app

```powershell
.\fresh_env\Scripts\Activate.ps1
streamlit run .\streamlit_app.py
```

## Run FastAPI (hardcoded backend mode)

```powershell
.\fresh_env\Scripts\Activate.ps1
uvicorn api_app:app --host 127.0.0.1 --port 8000 --reload
```

## Test API endpoints

```powershell
.\fresh_env\Scripts\Activate.ps1
python .\test_api_smoke.py
```

## Notes

- CSV and `.env` are ignored by Git.
- Context Graph is intentionally separated from KG updates.
- Promotion from Context Graph to KG should happen only after user approval.


