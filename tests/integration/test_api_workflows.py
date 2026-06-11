"""
Integration tests for workflow orchestration API endpoints.

Tests /v1/workflows/* endpoints for workflow submission, status, and management.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest import mock

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_list_templates(client: TestClient, auth_headers: dict):
    """Test listing available workflow templates."""
    response = client.get("/v1/workflows/templates", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert "templates" in data
    assert len(data["templates"]) > 0

    # Verify template structure
    template = data["templates"][0]
    assert "name" in template
    assert "version" in template
    assert "description" in template
    assert "engine" in template
    assert "required_inputs" in template
    assert "default_inputs" in template

    # Verify expected templates exist
    template_names = [t["name"] for t in data["templates"]]
    assert "scrna-qc" in template_names
    assert "feature-extraction" in template_names
    assert "batch-embedding" in template_names


@pytest.mark.integration
def test_list_templates_requires_auth(client: TestClient):
    """Test that template listing requires authentication."""
    response = client.get("/v1/workflows/templates")
    assert response.status_code == 401


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_submit_workflow_with_template(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test submitting a workflow using a predefined template."""
    from app.workflows import WorkflowExecution, WorkflowStatus

    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock successful submission
    mock_execution = WorkflowExecution(
        execution_id="test_exec_123",
        workflow_name="scrna-qc",
        status=WorkflowStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=None,
        outputs={},
        error_message=None,
        metadata={},
    )
    mock_engine.validate_inputs = mock.Mock(return_value=[])  # Sync method - use Mock not AsyncMock
    mock_engine.submit.return_value = mock_execution
    mock_engine.close.return_value = None

    # Submit workflow
    response = client.post(
        "/v1/workflows",
        json={
            "workflow_name": "scrna-qc",
            "workflow_source": "",  # Will use template default
            "engine": "nextflow",
            "inputs": {
                "input_path": "/data/sample.h5ad",
                "output_dir": "/data/output",
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["execution_id"] == "test_exec_123"
    assert data["workflow_name"] == "scrna-qc"
    assert data["status"] == "submitted"
    assert "submitted_at" in data
    assert "status_url" in data

    # Verify engine was called
    mock_engine.validate_inputs.assert_called_once()
    mock_engine.submit.assert_called_once()
    mock_engine.close.assert_called_once()


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_submit_workflow_missing_required_input(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test workflow submission with missing required input."""
    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock validation errors
    mock_engine.validate_inputs = mock.Mock(return_value=["Missing required input: input_path"])  # Sync method
    mock_engine.close.return_value = None

    # Submit workflow without required input
    response = client.post(
        "/v1/workflows",
        json={
            "workflow_name": "scrna-qc",
            "workflow_source": "",
            "engine": "nextflow",
            "inputs": {
                # Missing "input_path" and "output_dir"
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "validation_errors" in response.json()["detail"]


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.CromwellEngine")
def test_submit_workflow_with_cromwell(mock_cromwell_class, client: TestClient, auth_headers: dict):
    """Test submitting a workflow with Cromwell engine."""
    from app.workflows import WorkflowExecution, WorkflowStatus

    # Mock the Cromwell engine
    mock_engine = mock.AsyncMock()
    mock_cromwell_class.return_value = mock_engine

    # Mock successful submission
    mock_execution = WorkflowExecution(
        execution_id="cromwell_exec_456",
        workflow_name="batch-embedding",
        status=WorkflowStatus.SUBMITTED,
        submitted_at=datetime.now(timezone.utc),
        started_at=None,
        completed_at=None,
        outputs={},
        error_message=None,
        metadata={},
    )
    mock_engine.validate_inputs = mock.Mock(return_value=[])  # Sync method
    mock_engine.submit.return_value = mock_execution
    mock_engine.close.return_value = None

    # Submit workflow
    response = client.post(
        "/v1/workflows",
        json={
            "workflow_name": "batch-embedding",
            "workflow_source": "",
            "engine": "cromwell",
            "inputs": {
                "sample_manifest": "/data/manifest.csv",
                "output_bucket": "gs://my-bucket/outputs",
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["execution_id"] == "cromwell_exec_456"
    assert data["workflow_name"] == "batch-embedding"


@pytest.mark.integration
def test_submit_workflow_invalid_engine(client: TestClient, auth_headers: dict):
    """Test workflow submission with invalid engine."""
    response = client.post(
        "/v1/workflows",
        json={
            "workflow_name": "test-workflow",
            "workflow_source": "/path/to/workflow.nf",
            "engine": "invalid_engine",
            "inputs": {},
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Unknown workflow engine" in response.json()["detail"]


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_get_workflow_status(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test getting workflow execution status."""
    from app.workflows import WorkflowExecution, WorkflowStatus

    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock workflow status
    submitted_at = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    started_at = datetime(2026, 5, 12, 10, 1, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 5, 12, 10, 15, 0, tzinfo=timezone.utc)

    mock_execution = WorkflowExecution(
        execution_id="test_exec_789",
        workflow_name="scrna-qc",
        status=WorkflowStatus.SUCCEEDED,
        submitted_at=submitted_at,
        started_at=started_at,
        completed_at=completed_at,
        outputs={"results": "/data/output/results.h5ad"},
        error_message=None,
        metadata={"n_cells": 5000, "n_genes": 20000},
    )
    mock_engine.status.return_value = mock_execution
    mock_engine.close.return_value = None

    # Get status
    response = client.get(
        "/v1/workflows/test_exec_789?engine=nextflow",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["execution_id"] == "test_exec_789"
    assert data["workflow_name"] == "scrna-qc"
    assert data["status"] == "succeeded"
    assert data["duration_seconds"] == 840.0
    assert data["outputs"] == {"results": "/data/output/results.h5ad"}
    assert data["error_message"] is None
    assert data["metadata"]["n_cells"] == 5000


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_get_workflow_status_failed(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test getting status of a failed workflow."""
    from app.workflows import WorkflowExecution, WorkflowStatus

    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock failed workflow
    mock_execution = WorkflowExecution(
        execution_id="failed_exec_999",
        workflow_name="scrna-qc",
        status=WorkflowStatus.FAILED,
        submitted_at=datetime.now(timezone.utc),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        outputs={},
        error_message="Input file not found: /data/sample.h5ad",
        metadata={},
    )
    mock_engine.status.return_value = mock_execution
    mock_engine.close.return_value = None

    # Get status
    response = client.get(
        "/v1/workflows/failed_exec_999?engine=nextflow",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "Input file not found: /data/sample.h5ad"


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_cancel_workflow(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test cancelling a running workflow."""
    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock successful cancellation
    mock_engine.cancel.return_value = True
    mock_engine.close.return_value = None

    # Cancel workflow
    response = client.post(
        "/v1/workflows/test_exec_abc/cancel?engine=nextflow",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["execution_id"] == "test_exec_abc"
    assert data["status"] == "cancelled"

    # Verify engine was called
    mock_engine.cancel.assert_called_once_with("test_exec_abc")


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_cancel_workflow_failure(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test failed workflow cancellation."""
    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock failed cancellation
    mock_engine.cancel.return_value = False
    mock_engine.close.return_value = None

    # Try to cancel workflow
    response = client.post(
        "/v1/workflows/test_exec_xyz/cancel?engine=nextflow",
        headers=auth_headers,
    )
    assert response.status_code == 500
    assert "Failed to cancel workflow" in response.json()["detail"]


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_get_workflow_logs(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test retrieving workflow logs."""
    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock logs
    mock_logs = """
    [2026-05-12 10:00:00] Workflow started
    [2026-05-12 10:01:00] Processing sample.h5ad
    [2026-05-12 10:15:00] QC metrics computed: 5000 cells, 20000 genes
    [2026-05-12 10:15:01] Workflow completed successfully
    """
    mock_engine.logs.return_value = mock_logs
    mock_engine.close.return_value = None

    # Get logs
    response = client.get(
        "/v1/workflows/test_exec_logs/logs?engine=nextflow",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["execution_id"] == "test_exec_logs"
    assert "Workflow started" in data["logs"]
    assert "5000 cells" in data["logs"]


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_get_workflow_logs_specific_task(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test retrieving logs for a specific task."""
    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock task-specific logs
    mock_logs = "[2026-05-12 10:05:00] QC task: Filtering low-quality cells"
    mock_engine.logs.return_value = mock_logs
    mock_engine.close.return_value = None

    # Get logs for specific task
    response = client.get(
        "/v1/workflows/test_exec_task/logs?task=qc_filter&engine=nextflow",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert "QC task" in data["logs"]

    # Verify engine was called with task name
    mock_engine.logs.assert_called_once_with("test_exec_task", "qc_filter")


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_list_workflows(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test listing workflow executions."""
    from app.workflows import WorkflowExecution, WorkflowStatus

    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock multiple executions
    mock_executions = [
        WorkflowExecution(
            execution_id=f"exec_{i}",
            workflow_name="scrna-qc",
            status=WorkflowStatus.SUCCEEDED if i % 2 == 0 else WorkflowStatus.RUNNING,
            submitted_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) if i % 2 == 0 else None,
            outputs={},
            error_message=None,
            metadata={},
        )
        for i in range(5)
    ]
    mock_engine.list_executions.return_value = mock_executions
    mock_engine.close.return_value = None

    # List workflows
    response = client.get("/v1/workflows?engine=nextflow", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 5
    assert len(data["executions"]) == 5

    # Verify execution structure
    first_exec = data["executions"][0]
    assert "execution_id" in first_exec
    assert "workflow_name" in first_exec
    assert "status" in first_exec


@pytest.mark.integration
@mock.patch("app.routers.v1.workflows.NextflowEngine")
def test_list_workflows_with_filters(mock_nextflow_class, client: TestClient, auth_headers: dict):
    """Test listing workflows with filters."""
    from app.workflows import WorkflowExecution, WorkflowStatus

    # Mock the Nextflow engine
    mock_engine = mock.AsyncMock()
    mock_nextflow_class.return_value = mock_engine

    # Mock filtered executions
    mock_executions = [
        WorkflowExecution(
            execution_id="running_exec_1",
            workflow_name="scrna-qc",
            status=WorkflowStatus.RUNNING,
            submitted_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            outputs={},
            error_message=None,
            metadata={},
        ),
    ]
    mock_engine.list_executions.return_value = mock_executions
    mock_engine.close.return_value = None

    # List workflows with status filter
    response = client.get(
        "/v1/workflows?engine=nextflow&status=running&workflow_name=scrna-qc&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["executions"][0]["status"] == "running"
    assert data["executions"][0]["workflow_name"] == "scrna-qc"

    # Verify engine was called with filters
    mock_engine.list_executions.assert_called_once()
    call_kwargs = mock_engine.list_executions.call_args.kwargs
    assert call_kwargs["workflow_name"] == "scrna-qc"
    assert call_kwargs["status"].value == "running"
    assert call_kwargs["limit"] == 10


@pytest.mark.integration
def test_list_workflows_invalid_status_filter(client: TestClient, auth_headers: dict):
    """Test listing workflows with invalid status filter."""
    response = client.get(
        "/v1/workflows?engine=nextflow&status=invalid_status",
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Invalid status" in response.json()["detail"]


@pytest.mark.integration
def test_workflow_endpoints_require_auth(client: TestClient):
    """Test that workflow endpoints require authentication."""
    endpoints = [
        ("/v1/workflows", "POST", {"workflow_name": "test", "workflow_source": "", "inputs": {}}),
        ("/v1/workflows/exec_123", "GET", None),
        ("/v1/workflows/exec_123/cancel", "POST", None),
        ("/v1/workflows/exec_123/logs", "GET", None),
        ("/v1/workflows", "GET", None),
    ]

    for endpoint, method, json_data in endpoints:
        if method == "POST":
            response = client.post(endpoint, json=json_data or {})
        else:
            response = client.get(endpoint)

        assert response.status_code == 401, f"Endpoint {method} {endpoint} should require auth"
