"""Integration tests for /v1/runs endpoints."""
import pytest
from unittest import mock


@pytest.mark.integration
def test_create_run(client, auth_headers):
    """Test creating a new run."""
    response = client.post(
        "/v1/runs",
        json={"name": "test_run", "metadata": {"tissue": "PBMC"}},
        headers=auth_headers
    )

    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["name"] == "test_run"
    assert data["metadata"]["tissue"] == "PBMC"
    assert "created_at" in data


@pytest.mark.integration
def test_create_run_no_auth(client):
    """Test creating run without authentication fails."""
    response = client.post(
        "/v1/runs",
        json={"name": "test_run"}
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_list_runs(client, auth_headers):
    """Test listing runs."""
    # Create a few runs first
    for i in range(3):
        client.post(
            "/v1/runs",
            json={"name": f"run_{i}"},
            headers=auth_headers
        )

    # List runs
    response = client.get("/v1/runs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert "runs" in data
    assert len(data["runs"]) == 3


@pytest.mark.integration
def test_get_run(client, auth_headers):
    """Test getting a specific run."""
    # Create run
    create_response = client.post(
        "/v1/runs",
        json={"name": "specific_run"},
        headers=auth_headers
    )
    run_id = create_response.json()["id"]

    # Get run
    response = client.get(f"/v1/runs/{run_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == run_id
    assert data["name"] == "specific_run"


@pytest.mark.integration
def test_get_nonexistent_run(client, auth_headers):
    """Test getting a run that doesn't exist."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"

    response = client.get(f"/v1/runs/{fake_uuid}", headers=auth_headers)

    assert response.status_code == 404


@pytest.mark.integration
def test_update_run(client, auth_headers):
    """Test updating run metadata."""
    # Create run
    create_response = client.post(
        "/v1/runs",
        json={"name": "original_name"},
        headers=auth_headers
    )
    run_id = create_response.json()["id"]

    # Update run
    response = client.put(
        f"/v1/runs/{run_id}",
        json={"name": "updated_name", "metadata": {"status": "completed"}},
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "updated_name"
    assert data["metadata"]["status"] == "completed"


@pytest.mark.integration
def test_delete_run(client, auth_headers):
    """Test deleting a run."""
    # Create run
    create_response = client.post(
        "/v1/runs",
        json={"name": "to_delete"},
        headers=auth_headers
    )
    run_id = create_response.json()["id"]

    # Delete run
    response = client.delete(f"/v1/runs/{run_id}", headers=auth_headers)

    assert response.status_code == 204

    # Verify deletion
    get_response = client.get(f"/v1/runs/{run_id}", headers=auth_headers)
    assert get_response.status_code == 404


@pytest.mark.integration
@mock.patch('app.tasks.SessionLocal')
@mock.patch('openbioops.processing.features.generate_features')
@mock.patch('app.routers.v1.runs.extract_features_task')
def test_extract_features(mock_task, mock_generate, mock_session, client, auth_headers, sample_run):
    """Test triggering feature extraction."""
    # Mock the task's database session
    mock_db = mock.Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = sample_run
    mock_session.return_value = mock_db

    mock_task.delay.return_value = mock.Mock(id="task_123")
    mock_generate.return_value = None  # Mock actual file processing

    response = client.post(
        f"/v1/runs/{sample_run.id}/features",
        json={"raw_path": "/data/sample.h5ad"},
        headers=auth_headers
    )

    assert response.status_code == 202
    data = response.json()

    assert "task_id" in data
    assert data["message"] == "Feature extraction started"

    # Verify task was called
    mock_task.delay.assert_called_once()


@pytest.mark.integration
def test_list_runs_with_pagination(client, auth_headers):
    """Test run listing with pagination."""
    # Create many runs
    for i in range(15):
        client.post(
            "/v1/runs",
            json={"name": f"run_{i}"},
            headers=auth_headers
        )

    # Get first page
    response = client.get("/v1/runs?limit=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 10

    # Get second page
    response = client.get("/v1/runs?limit=10&offset=10", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 5


@pytest.mark.integration
def test_compute_vector_no_features(client, auth_headers, sample_run):
    """Test computing vector when features don't exist."""
    response = client.post(
        f"/v1/runs/{sample_run.id}/compute_vector",
        headers=auth_headers
    )

    # Should fail because features don't exist
    assert response.status_code in [404, 500]
