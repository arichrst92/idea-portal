"""Smoke tests untuk skeleton — health & root endpoints."""

from fastapi.testclient import TestClient


def test_root(client: TestClient) -> None:
    """Root returns app metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "IDEA Portal API"
    assert "version" in data
    assert data["docs"] == "/docs"


def test_health(client: TestClient) -> None:
    """Health endpoint returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
