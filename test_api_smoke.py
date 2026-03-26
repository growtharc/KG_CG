from fastapi.testclient import TestClient

from api_app import app


def main():
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200

    stats = client.get("/stats")
    assert stats.status_code == 200

    sample_load = client.post("/tickets/sample-load", json={"limit": 12})
    assert sample_load.status_code == 200

    analyze = client.post(
        "/tickets/analyze",
        json={"summary": "Delete duplicate opportunity for ACME account", "top_k": 2},
    )
    assert analyze.status_code == 200

    ingest = client.post(
        "/context/ingest/manual",
        json={
            "text": "Need Salesforce access to update account records",
            "page_number": 1,
            "chunk_index": 1,
            "source": "smoke_test",
        },
    )
    assert ingest.status_code == 200
    document_id = ingest.json()["document_id"]
    chunk_id = ingest.json()["chunk_id"]

    fetch_doc = client.get(f"/context/documents/{document_id}")
    assert fetch_doc.status_code == 200

    approve = client.post(
        "/context/approve",
        json={"chunk_ids": [chunk_id], "approved": True},
    )
    assert approve.status_code == 200

    promote = client.post(
        "/kg/promote",
        json={"chunk_ids": [chunk_id]},
    )
    assert promote.status_code == 200

    print("API smoke test passed.")


if __name__ == "__main__":
    main()
