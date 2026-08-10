"""Tests — API Health endpoint (Sprint 1).

Covers:
    - GET /health returns pipeline health JSON
    - GET / returns API info
    - Health response structure includes components
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestHealthAPI:
    """Pipeline Health — component-level status."""

    def test_health_returns_200(self) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status_field(self) -> None:
        response = client.get("/health")
        body = response.json()
        assert "status" in body
        assert body["status"] in ("healthy", "degraded", "unhealthy")

    def test_health_has_components(self) -> None:
        response = client.get("/health")
        body = response.json()
        assert "components" in body
        assert "api" in body["components"]
        assert "database" in body["components"]
        assert "collector" in body["components"]
        assert "last_ingested" in body["components"]

    def test_api_component_healthy(self) -> None:
        response = client.get("/health")
        body = response.json()
        assert body["components"]["api"]["status"] == "healthy"

    def test_database_component_present(self) -> None:
        response = client.get("/health")
        body = response.json()
        assert body["components"]["database"]["status"] in ("healthy", "unhealthy")

    def test_health_has_timestamp(self) -> None:
        response = client.get("/health")
        body = response.json()
        assert "timestamp" in body

    def test_root_endpoint(self) -> None:
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Macro Research Agent API"
        assert body["version"] == "0.1.0"
