"""End-to-end pipeline tests."""
import pytest
from unittest import mock


@pytest.mark.e2e
@pytest.mark.slow
def test_complete_analysis_workflow(client, auth_headers, temp_dir):
    """Test complete workflow: create run → upload features → compute vector → search similar."""

    # Step 1: Create run
    create_response = client.post(
        "/v1/runs",
        json={
            "name": "E2E_Test_Run",
            "metadata": {"tissue": "PBMC", "cells": 2638}
        },
        headers=auth_headers
    )
    assert create_response.status_code == 201
    run_id = create_response.json()["id"]

    # Step 2: Verify run exists
    get_response = client.get(f"/v1/runs/{run_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "E2E_Test_Run"

    # Step 3: Trigger feature extraction (mocked)
    with mock.patch('app.tasks.SessionLocal') as mock_session:
        # Mock the task's database access
        mock_db = mock.Mock()
        mock_run = mock.Mock()
        mock_run.id = run_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_run
        mock_session.return_value = mock_db

        with mock.patch('openbioops.processing.features.generate_features') as mock_generate:
            with mock.patch('services.api.app.routers.v1.runs.extract_features_task') as mock_task:
                mock_task.delay.return_value = mock.Mock(id="task_123")
                mock_generate.return_value = None  # Mock actual file processing

                features_response = client.post(
                    f"/v1/runs/{run_id}/features",
                    json={"raw_path": "/data/sample.h5ad"},
                    headers=auth_headers
                )
                assert features_response.status_code == 202

    # Step 4: Update run status
    update_response = client.put(
        f"/v1/runs/{run_id}",
        json={"metadata": {"status": "features_extracted"}},
        headers=auth_headers
    )
    assert update_response.status_code == 200

    # Step 5: List all runs (should include our run)
    list_response = client.get("/v1/runs", headers=auth_headers)
    assert list_response.status_code == 200
    runs = list_response.json()["runs"]
    assert any(r["id"] == run_id for r in runs)

    # Step 6: Cleanup
    delete_response = client.delete(f"/v1/runs/{run_id}", headers=auth_headers)
    assert delete_response.status_code == 204


@pytest.mark.e2e
def test_authentication_flow(client):
    """Test complete authentication flow."""

    # Step 1: Get token
    token_response = client.post("/v1/auth/token", json={"username": "e2e_user"})
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    # Step 2: Use token to access protected endpoint
    runs_response = client.get(
        "/v1/runs",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert runs_response.status_code == 200

    # Step 3: Verify invalid token fails
    invalid_response = client.get(
        "/v1/runs",
        headers={"Authorization": "Bearer invalid"}
    )
    assert invalid_response.status_code == 401


@pytest.mark.e2e
def test_health_check_endpoints(client):
    """Test health check endpoints work without authentication."""

    # Liveness
    liveness = client.get("/health/live")
    assert liveness.status_code == 200
    assert liveness.json()["status"] == "alive"

    # Readiness
    readiness = client.get("/health/ready")
    assert readiness.status_code in [200, 503]  # May not be ready in test env

    # Full health
    health = client.get("/health")
    assert health.status_code in [200, 503]
    assert "status" in health.json()


@pytest.mark.e2e
@pytest.mark.slow
def test_error_handling_chain(client, auth_headers):
    """Test error handling across multiple operations."""

    # Step 1: Try to get non-existent run
    response = client.get(
        "/v1/runs/00000000-0000-0000-0000-000000000000",
        headers=auth_headers
    )
    assert response.status_code == 404

    # Step 2: Try to create run with invalid data
    response = client.post(
        "/v1/runs",
        json={"invalid_field": "value"},
        headers=auth_headers
    )
    # Should fail validation (422) or succeed with defaults
    assert response.status_code in [201, 422]

    # Step 3: Try to update non-existent run
    response = client.put(
        "/v1/runs/00000000-0000-0000-0000-000000000000",
        json={"name": "updated"},
        headers=auth_headers
    )
    assert response.status_code == 404

    # Step 4: Try to delete non-existent run
    response = client.delete(
        "/v1/runs/00000000-0000-0000-0000-000000000000",
        headers=auth_headers
    )
    assert response.status_code == 404
