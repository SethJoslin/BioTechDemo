"""
Abstract workflow engine interface.

Defines the contract for workflow execution backends.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class WorkflowExecution:
    """Workflow execution details."""
    execution_id: str
    workflow_name: str
    status: WorkflowStatus
    submitted_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    logs_url: Optional[str] = None
    cost_estimate: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        """Check if execution is in a terminal state."""
        return self.status in {
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }


@dataclass
class WorkflowDefinition:
    """Workflow definition/template."""
    name: str
    version: str
    description: str
    engine: str  # "nextflow" or "cromwell"
    source: str  # Path or URL to workflow file
    default_inputs: dict[str, Any] = field(default_factory=dict)
    required_inputs: list[str] = field(default_factory=list)
    schema: Optional[dict] = None  # JSON schema for inputs


class WorkflowEngine(ABC):
    """Abstract base class for workflow execution engines.

    Implementations provide integration with specific execution
    platforms (Nextflow Tower, Cromwell, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name identifier."""
        ...

    @abstractmethod
    async def submit(
        self,
        workflow: WorkflowDefinition,
        inputs: dict[str, Any],
        options: Optional[dict[str, Any]] = None,
    ) -> WorkflowExecution:
        """Submit a workflow for execution.

        Args:
            workflow: Workflow definition
            inputs: Input parameters
            options: Engine-specific options (compute, labels, etc.)

        Returns:
            WorkflowExecution with execution_id
        """
        ...

    @abstractmethod
    async def status(self, execution_id: str) -> WorkflowExecution:
        """Get workflow execution status.

        Args:
            execution_id: Execution identifier

        Returns:
            Updated WorkflowExecution
        """
        ...

    @abstractmethod
    async def cancel(self, execution_id: str) -> bool:
        """Cancel a running workflow.

        Args:
            execution_id: Execution identifier

        Returns:
            True if cancellation was successful
        """
        ...

    @abstractmethod
    async def logs(self, execution_id: str, task: Optional[str] = None) -> str:
        """Get execution logs.

        Args:
            execution_id: Execution identifier
            task: Optional specific task name

        Returns:
            Log content as string
        """
        ...

    async def wait(
        self,
        execution_id: str,
        poll_interval: float = 30.0,
        timeout: Optional[float] = None,
    ) -> WorkflowExecution:
        """Wait for workflow completion.

        Args:
            execution_id: Execution identifier
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait (None = infinite)

        Returns:
            Final WorkflowExecution state

        Raises:
            TimeoutError: If timeout exceeded
        """
        import asyncio
        elapsed = 0.0

        while True:
            execution = await self.status(execution_id)
            if execution.is_terminal:
                return execution

            if timeout and elapsed >= timeout:
                raise TimeoutError(f"Workflow {execution_id} did not complete within {timeout}s")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    async def list_executions(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
    ) -> list[WorkflowExecution]:
        """List workflow executions.

        Default implementation returns empty list.
        Override in subclasses that support listing.

        Args:
            workflow_name: Filter by workflow name
            status: Filter by status
            limit: Maximum results

        Returns:
            List of WorkflowExecution
        """
        return []

    def validate_inputs(
        self,
        workflow: WorkflowDefinition,
        inputs: dict[str, Any],
    ) -> list[str]:
        """Validate inputs against workflow requirements.

        Args:
            workflow: Workflow definition
            inputs: Proposed inputs

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check required inputs
        for required in workflow.required_inputs:
            if required not in inputs:
                errors.append(f"Missing required input: {required}")

        # Validate against JSON schema if provided
        if workflow.schema:
            try:
                import jsonschema
                jsonschema.validate(inputs, workflow.schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation error: {e.message}")
            except ImportError:
                pass  # jsonschema not installed, skip validation

        return errors
