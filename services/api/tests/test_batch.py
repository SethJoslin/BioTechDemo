"""Tests for batch prediction endpoints."""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.integration
def test_submit_batch_prediction(client, auth_headers, sample_run):
    """Test batch prediction submission."""
    run_id = sample_run["id"]

    payload = {
        "run_ids": [run_id],
        "model_version": "test",
        "output_format": "parquet",
        "batch_size": 32
    }

    response = client.post("/v1/batch", json=payload, headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert "batch_id" in data
    assert data["status"] == "queued"
    assert data["n_total"] == 1
    assert data["n_completed"] == 0


@pytest.mark.integration
def test_submit_batch_with_missing_runs(client, auth_headers):
    """Test batch submission with non-existent run IDs."""
    payload = {
        "run_ids": ["00000000-0000-0000-0000-000000000000"],
        "model_version": "test",
        "output_format": "json"
    }

    response = client.post("/v1/batch", json=payload, headers=auth_headers)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.integration
def test_get_batch_status(client, auth_headers, sample_run):
    """Test getting batch job status."""
    # Submit a batch job
    payload = {
        "run_ids": [sample_run["id"]],
        "model_version": "test",
        "output_format": "json"
    }

    response = client.post("/v1/batch", json=payload, headers=auth_headers)
    batch_id = response.json()["batch_id"]

    # Get status
    response = client.get(f"/v1/batch/{batch_id}", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["batch_id"] == batch_id
    assert data["status"] in ["queued", "processing", "completed"]


@pytest.mark.integration
def test_get_nonexistent_batch(client, auth_headers):
    """Test getting status of non-existent batch."""
    response = client.get("/v1/batch/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.integration
def test_list_batch_jobs(client, auth_headers, sample_run):
    """Test listing batch jobs."""
    # Submit a few jobs
    for _ in range(2):
        payload = {
            "run_ids": [sample_run["id"]],
            "model_version": "test",
            "output_format": "json"
        }
        client.post("/v1/batch", json=payload, headers=auth_headers)

    # List jobs
    response = client.get("/v1/batch", headers=auth_headers)
    assert response.status_code == 200

    jobs = response.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 2


@pytest.mark.integration
def test_cancel_batch_job(client, auth_headers, sample_run):
    """Test canceling a batch job."""
    # Submit a batch job
    payload = {
        "run_ids": [sample_run["id"]],
        "model_version": "test",
        "output_format": "json"
    }

    response = client.post("/v1/batch", json=payload, headers=auth_headers)
    batch_id = response.json()["batch_id"]

    # Cancel it - note that in test environment, background tasks may complete
    # before we can cancel, so both 200 (cancelled) and 400 (already terminal) are acceptable
    response = client.delete(f"/v1/batch/{batch_id}", headers=auth_headers)

    if response.status_code == 200:
        # Job was cancelled successfully
        assert "cancelled" in response.json()["message"].lower()

        # Verify status changed
        response = client.get(f"/v1/batch/{batch_id}", headers=auth_headers)
        assert response.json()["status"] == "cancelled"
    elif response.status_code == 400:
        # Job already completed/failed before we could cancel (acceptable in fast test environment)
        assert "cannot cancel" in response.json()["detail"].lower()

        # Verify job is in terminal state
        status_response = client.get(f"/v1/batch/{batch_id}", headers=auth_headers)
        assert status_response.json()["status"] in ["completed", "failed", "cancelled"]
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")


@pytest.mark.integration
def test_cancel_nonexistent_batch(client, auth_headers):
    """Test canceling non-existent batch."""
    response = client.delete("/v1/batch/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.integration
def test_cancel_completed_batch(client, auth_headers, sample_run):
    """Test that completed batches cannot be cancelled."""
    from app.routers.v1.batch import batch_jobs, BatchStatus

    # Submit a batch job
    payload = {
        "run_ids": [sample_run["id"]],
        "model_version": "test",
        "output_format": "json"
    }

    response = client.post("/v1/batch", json=payload, headers=auth_headers)
    batch_id = response.json()["batch_id"]

    # Mark it as completed
    batch_jobs[batch_id]["status"] = BatchStatus.COMPLETED

    # Try to cancel
    response = client.delete(f"/v1/batch/{batch_id}", headers=auth_headers)
    assert response.status_code == 400
    assert "cannot cancel" in response.json()["detail"].lower()


@pytest.mark.unit
def test_batch_validation():
    """Test batch request validation."""
    from app.routers.v1.batch import BatchPredictionRequest, OutputFormat
    from pydantic import ValidationError

    # Valid request
    req = BatchPredictionRequest(
        run_ids=["test-id"],
        model_version="v1",
        output_format=OutputFormat.PARQUET
    )
    assert req.batch_size == 32  # Default

    # Empty run_ids
    with pytest.raises(ValidationError):
        BatchPredictionRequest(run_ids=[])

    # Too many run_ids
    with pytest.raises(ValidationError):
        BatchPredictionRequest(run_ids=["id"] * 1001)

    # Invalid batch_size
    with pytest.raises(ValidationError):
        BatchPredictionRequest(run_ids=["id"], batch_size=0)

    with pytest.raises(ValidationError):
        BatchPredictionRequest(run_ids=["id"], batch_size=200)