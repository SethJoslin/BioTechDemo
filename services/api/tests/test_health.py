"""
Tests for health check endpoints.
"""
import pytest


class TestHealthEndpoints:
    """Tests for /health endpoints."""

    def test_health_check_returns_status(self, client):
        """GET /health should return service status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "model_loaded" in data
        assert "index_size" in data

    def test_liveness_probe(self, client):
        """GET /health/live should return alive for liveness check."""
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_probe_checks_database(self, client):
        """GET /health/ready should check database connectivity."""
        response = client.get("/health/ready")
        # Should return 200 or 503 depending on model status
        assert response.status_code in [200, 503]
        data = response.json()
        assert "ready" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert "model" in data["checks"]

    def test_health_endpoints_no_auth_required(self, client):
        """Health endpoints should not require authentication."""
        # These should all succeed without auth headers
        assert client.get("/health").status_code == 200
        assert client.get("/health/live").status_code == 200
        # Readiness might be 503 if model not loaded, but shouldn't be 401
        response = client.get("/health/ready")
        assert response.status_code != 401