"""
Tests for the runs API endpoints.
"""
import uuid

import pytest


class TestAuthentication:
    """Tests for authentication endpoints and protection."""

    def test_token_endpoint_returns_jwt(self, client):
        """POST /v1/auth/token should return a valid JWT."""
        response = client.post("/v1/auth/token", json={"username": "testuser"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_protected_route_requires_token(self, client):
        """Protected routes should return 401 without token."""
        response = client.get("/v1/runs")
        assert response.status_code == 401
        assert "Missing bearer token" in response.json()["detail"]

    def test_protected_route_rejects_invalid_token(self, client):
        """Protected routes should reject invalid tokens."""
        response = client.get(
            "/v1/runs",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]


class TestRunsCRUD:
    """Tests for runs CRUD operations."""

    def test_create_run_with_name(self, client, auth_headers):
        """POST /v1/runs should create a run and return its ID."""
        response = client.post(
            "/v1/runs",
            json={"name": "my-analysis-run"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "my-analysis-run"
        # Verify it's a valid UUID
        uuid.UUID(data["id"])

    def test_create_run_with_metadata(self, client, auth_headers):
        """POST /v1/runs should accept metadata."""
        metadata = {"tissue": "lung", "species": "human", "cell_count": 5000}
        response = client.post(
            "/v1/runs",
            json={"name": "metadata-run", "metadata": metadata},
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Verify metadata is stored
        run_id = response.json()["id"]
        get_response = client.get(f"/v1/runs/{run_id}", headers=auth_headers)
        assert get_response.json()["metadata"] == metadata

    def test_create_run_minimal(self, client, auth_headers):
        """POST /v1/runs should work with minimal payload."""
        response = client.post("/v1/runs", json={}, headers=auth_headers)
        assert response.status_code == 201
        assert "id" in response.json()

    def test_list_runs_empty(self, client, auth_headers):
        """GET /v1/runs should return empty list initially."""
        response = client.get("/v1/runs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["runs"] == []

    def test_list_runs_pagination(self, client, auth_headers):
        """GET /v1/runs should support pagination."""
        # Create multiple runs
        for i in range(5):
            client.post("/v1/runs", json={"name": f"run-{i}"}, headers=auth_headers)

        # Test pagination
        response = client.get("/v1/runs?offset=0&limit=2", headers=auth_headers)
        data = response.json()
        assert data["total"] == 5
        assert len(data["runs"]) == 2
        assert data["offset"] == 0
        assert data["limit"] == 2

        # Get next page
        response = client.get("/v1/runs?offset=2&limit=2", headers=auth_headers)
        data = response.json()
        assert len(data["runs"]) == 2

    def test_get_run_by_id(self, client, auth_headers, sample_run):
        """GET /v1/runs/{run_id} should return run details."""
        run_id = sample_run["id"]
        response = client.get(f"/v1/runs/{run_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run_id
        assert data["name"] == "test-run"

    def test_get_run_not_found(self, client, auth_headers):
        """GET /v1/runs/{run_id} should return 404 for non-existent run."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/runs/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    def test_get_run_invalid_uuid(self, client, auth_headers):
        """GET /v1/runs/{run_id} should return 400 for invalid UUID."""
        response = client.get("/v1/runs/not-a-valid-uuid", headers=auth_headers)
        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "invalid" in detail and "uuid" in detail


class TestRunQC:
    """Tests for QC endpoints."""

    def test_store_qc_results(self, client, auth_headers, sample_run):
        """POST /v1/runs/{run_id}/qc should store QC results."""
        run_id = sample_run["id"]
        qc_data = {
            "qc_status": "passed",
            "metrics": {"n_cells": 5000, "median_genes": 2500},
        }
        response = client.post(
            f"/v1/runs/{run_id}/qc",
            json=qc_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["qc_status"] == "passed"

    def test_get_qc_results(self, client, auth_headers, sample_run):
        """GET /v1/runs/{run_id}/qc should retrieve QC results."""
        run_id = sample_run["id"]

        # Store QC first
        client.post(
            f"/v1/runs/{run_id}/qc",
            json={"qc_status": "passed", "metrics": {"score": 0.95}},
            headers=auth_headers,
        )

        # Retrieve
        response = client.get(f"/v1/runs/{run_id}/qc", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["qc_status"] == "passed"
        assert data["metrics"]["score"] == 0.95


class TestRunStatus:
    """Tests for run status endpoint."""

    def test_get_run_status(self, client, auth_headers, sample_run):
        """GET /v1/runs/{run_id}/status should return status info."""
        run_id = sample_run["id"]
        response = client.get(f"/v1/runs/{run_id}/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "status" in data
        assert "features_ready" in data


class TestSimilarity:
    """Tests for similarity search endpoints."""

    def test_similarity_requires_indexed_vector(self, client, auth_headers, sample_run):
        """GET /v1/similarity/{run_id} should return 404 if vector not indexed."""
        run_id = sample_run["id"]
        response = client.get(f"/v1/similarity/{run_id}", headers=auth_headers)
        assert response.status_code == 404
        assert "not indexed" in response.json()["detail"].lower()


class TestSimilarityIndex:
    """Tests for the FAISS similarity index."""

    def test_index_persistence(self, tmp_path):
        """Vectors should survive index restart."""
        import numpy as np

        from app.ml.run_similarity import RunSimilarityIndex, compute_run_vector

        # Create test embedding data
        np.random.seed(42)
        rows_a = [{f"d_{i}": float(1 + np.random.normal(0, 0.05)) for i in range(16)}
                  for _ in range(10)]
        rows_b = [{f"d_{i}": float(np.random.normal(0, 0.05)) for i in range(16)}
                  for _ in range(10)]

        # Create index and add vectors
        idx1 = RunSimilarityIndex(index_dir=tmp_path)
        idx1.upsert("run-A", compute_run_vector(rows_a))
        idx1.upsert("run-B", compute_run_vector(rows_b))

        # Simulate restart with new instance
        idx2 = RunSimilarityIndex(index_dir=tmp_path)
        assert "run-A" in idx2.vectors, "run-A missing after reload"
        assert "run-B" in idx2.vectors, "run-B missing after reload"

        # Verify similarity search works
        sims = idx2.most_similar("run-A", k=1)
        assert len(sims) == 1
        assert sims[0][0] == "run-B"

    def test_compute_run_vector_normalization(self):
        """Run vectors should be L2-normalized."""
        import numpy as np

        from app.ml.run_similarity import compute_run_vector

        rows = [{f"d_{i}": float(i + 1) for i in range(8)} for _ in range(5)]
        vec = compute_run_vector(rows)

        # Check L2 norm is approximately 1
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 1e-5, f"Vector norm {norm} is not 1.0"

    def test_empty_rows_raises_error(self):
        """compute_run_vector should raise on empty input."""
        from app.ml.run_similarity import compute_run_vector

        with pytest.raises(ValueError, match="No rows provided"):
            compute_run_vector([])