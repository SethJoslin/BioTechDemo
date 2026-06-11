"""Tests for workflow engine abstractions."""
import pytest
from datetime import datetime, timedelta


@pytest.mark.unit
def test_workflow_status_enum():
    """Test WorkflowStatus enum values."""
    from app.workflows.engine import WorkflowStatus

    assert WorkflowStatus.PENDING == "pending"
    assert WorkflowStatus.RUNNING == "running"
    assert WorkflowStatus.SUCCEEDED == "succeeded"
    assert WorkflowStatus.FAILED == "failed"
    assert WorkflowStatus.CANCELLED == "cancelled"


@pytest.mark.unit
def test_workflow_execution_creation():
    """Test creating a WorkflowExecution."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="qc-pipeline",
        status=WorkflowStatus.PENDING,
        submitted_at=datetime.utcnow(),
        inputs={"sample_id": "test"},
        metadata={"user": "test"}
    )

    assert execution.execution_id == "exec-123"
    assert execution.status == WorkflowStatus.PENDING
    assert execution.inputs["sample_id"] == "test"
    assert execution.outputs == {}
    assert execution.error_message is None


@pytest.mark.unit
def test_workflow_execution_duration():
    """Test execution duration calculation."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    now = datetime.utcnow()
    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="test",
        status=WorkflowStatus.RUNNING,
        submitted_at=now,
        started_at=now,
        completed_at=now + timedelta(minutes=5)
    )

    assert execution.duration_seconds == pytest.approx(300.0, rel=1.0)


@pytest.mark.unit
def test_workflow_execution_duration_none():
    """Test duration is None when not completed."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="test",
        status=WorkflowStatus.RUNNING,
        submitted_at=datetime.utcnow(),
        started_at=datetime.utcnow()
    )

    assert execution.duration_seconds is None


@pytest.mark.unit
def test_workflow_execution_is_terminal():
    """Test terminal state detection."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    # Terminal states
    for status in [WorkflowStatus.SUCCEEDED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
        execution = WorkflowExecution(
            execution_id="exec-123",
            workflow_name="test",
            status=status,
            submitted_at=datetime.utcnow()
        )
        assert execution.is_terminal is True

    # Non-terminal states
    for status in [WorkflowStatus.PENDING, WorkflowStatus.RUNNING, WorkflowStatus.SUBMITTED]:
        execution = WorkflowExecution(
            execution_id="exec-123",
            workflow_name="test",
            status=status,
            submitted_at=datetime.utcnow()
        )
        assert execution.is_terminal is False


@pytest.mark.unit
def test_workflow_definition_creation():
    """Test creating a WorkflowDefinition."""
    from app.workflows.engine import WorkflowDefinition

    workflow = WorkflowDefinition(
        name="alignment-pipeline",
        version="1.0.0",
        description="RNA-seq alignment workflow",
        engine="nextflow",
        source="https://github.com/org/workflow.git",
        default_inputs={"threads": 4},
        required_inputs=["fastq_r1", "fastq_r2", "reference"]
    )

    assert workflow.name == "alignment-pipeline"
    assert workflow.engine == "nextflow"
    assert len(workflow.required_inputs) == 3
    assert workflow.default_inputs["threads"] == 4


@pytest.mark.unit
def test_workflow_definition_minimal():
    """Test WorkflowDefinition with minimal fields."""
    from app.workflows.engine import WorkflowDefinition

    workflow = WorkflowDefinition(
        name="test",
        version="1.0",
        description="test workflow",
        engine="nextflow",
        source="/path/to/workflow.nf"
    )

    assert workflow.default_inputs == {}
    assert workflow.required_inputs == []
    assert workflow.schema is None


@pytest.mark.unit
def test_workflow_engine_is_abstract():
    """Test that WorkflowEngine cannot be instantiated."""
    from app.workflows.engine import WorkflowEngine

    with pytest.raises(TypeError, match="abstract"):
        WorkflowEngine()


@pytest.mark.unit
def test_workflow_engine_subclass_must_implement_methods():
    """Test that WorkflowEngine subclass must implement abstract methods."""
    from app.workflows.engine import WorkflowEngine, WorkflowDefinition, WorkflowExecution
    from typing import Optional, Any

    # Incomplete implementation
    class IncompleteEngine(WorkflowEngine):
        @property
        def name(self) -> str:
            return "incomplete"

    # Should fail - missing submit, get_status, cancel
    with pytest.raises(TypeError):
        IncompleteEngine()


@pytest.mark.unit
def test_workflow_execution_with_error():
    """Test WorkflowExecution with error state."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="failing-workflow",
        status=WorkflowStatus.FAILED,
        submitted_at=datetime.utcnow(),
        error_message="Out of memory: Java heap space"
    )

    assert execution.status == WorkflowStatus.FAILED
    assert "heap space" in execution.error_message
    assert execution.is_terminal is True


@pytest.mark.unit
def test_workflow_execution_with_outputs():
    """Test WorkflowExecution with output artifacts."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="test",
        status=WorkflowStatus.SUCCEEDED,
        submitted_at=datetime.utcnow(),
        outputs={
            "bam_file": "s3://bucket/sample.bam",
            "metrics": {"reads": 1000000}
        }
    )

    assert execution.status == WorkflowStatus.SUCCEEDED
    assert "bam_file" in execution.outputs
    assert execution.outputs["metrics"]["reads"] == 1000000


@pytest.mark.unit
def test_workflow_definition_with_schema():
    """Test WorkflowDefinition with JSON schema."""
    from app.workflows.engine import WorkflowDefinition

    schema = {
        "type": "object",
        "properties": {
            "sample_id": {"type": "string"},
            "threads": {"type": "integer", "minimum": 1}
        },
        "required": ["sample_id"]
    }

    workflow = WorkflowDefinition(
        name="test",
        version="1.0",
        description="test",
        engine="nextflow",
        source="test.nf",
        schema=schema
    )

    assert workflow.schema is not None
    assert "sample_id" in workflow.schema["properties"]


@pytest.mark.unit
def test_workflow_execution_cost_estimate():
    """Test WorkflowExecution with cost estimate."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="expensive-workflow",
        status=WorkflowStatus.SUCCEEDED,
        submitted_at=datetime.utcnow(),
        cost_estimate=12.45
    )

    assert execution.cost_estimate == 12.45


@pytest.mark.unit
def test_workflow_execution_logs_url():
    """Test WorkflowExecution with logs URL."""
    from app.workflows.engine import WorkflowExecution, WorkflowStatus

    execution = WorkflowExecution(
        execution_id="exec-123",
        workflow_name="test",
        status=WorkflowStatus.RUNNING,
        submitted_at=datetime.utcnow(),
        logs_url="https://tower.example.com/logs/exec-123"
    )

    assert execution.logs_url is not None
    assert "exec-123" in execution.logs_url
