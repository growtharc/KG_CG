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

    clear_ctx = client.post("/context/clear")
    assert clear_ctx.status_code == 200

    print("API smoke test passed.")


if __name__ == "__main__":
    main()
