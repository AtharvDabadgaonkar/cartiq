"""Service-level endpoint behaviour."""

from cartiq_api.schemas import EventType


def test_health_reports_version_and_provider(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    # The database may legitimately be down in CI; the endpoint must still answer.
    assert body["status"] in {"ok", "degraded"}
    assert body["database"] in {"up", "down"}
    assert body["llm_provider"] == "mock"
    assert body["phase"] == 1


def test_schema_endpoint_serves_the_event_contract(client):
    response = client.get("/schema")
    assert response.status_code == 200
    body = response.json()
    assert body["event_types"] == [e.value for e in EventType]
    assert body["funnel"][0]["key"] == "visit"
    assert body["funnel"][-1]["event_type"] == "purchase"


def test_openapi_document_builds(client):
    assert client.get("/openapi.json").status_code == 200
