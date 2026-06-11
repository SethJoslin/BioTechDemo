"""
Cromwell/WDL workflow engine integration.

Provides workflow execution via Cromwell REST API.
https://cromwell.readthedocs.io/
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import httpx

from .engine import (
    WorkflowEngine,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
)
from ..logger import get_logger

logger = get_logger(__name__)


class CromwellEngine(WorkflowEngine):
    """Cromwell workflow engine for WDL workflows.

    Submits and monitors workflows via Cromwell REST API.

    Args:
        cromwell_url: Cromwell server URL
        auth_token: Optional bearer token for authentication
    """

    def __init__(
        self,
        cromwell_url: str = "http://localhost:8000",
        auth_token: Optional[str] = None,
    ):
        self.cromwell_url = cromwell_url.rstrip("/")

        headers = {"Accept": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        self._client = httpx.AsyncClient(
            base_url=f"{self.cromwell_url}/api/workflows/v1",
            headers=headers,
            timeout=60.0,
        )

    @property
    def name(self) -> str:
        return "cromwell"

    async def submit(
        self,
        workflow: WorkflowDefinition,
        inputs: dict[str, Any],
        options: Optional[dict[str, Any]] = None,
    ) -> WorkflowExecution:
        """Submit WDL workflow to Cromwell."""
        import json
        options = options or {}

        # Prepare multipart form data
        files = {}
        data = {}

        # Workflow source (file or URL)
        source_path = Path(workflow.source)
        if source_path.exists():
            files["workflowSource"] = (
                source_path.name,
                source_path.read_text(),
                "application/wdl",
            )
        else:
            data["workflowUrl"] = workflow.source

        # Inputs JSON
        files["workflowInputs"] = (
            "inputs.json",
            json.dumps(inputs),
            "application/json",
        )

        # Workflow options
        if options:
            workflow_options = {
                "backend": options.get("backend", "Local"),
                "write_to_cache": options.get("cache", True),
                "read_from_cache": options.get("cache", True),
            }
            if "output_dir" in options:
                workflow_options["final_workflow_outputs_dir"] = options["output_dir"]

            files["workflowOptions"] = (
                "options.json",
                json.dumps(workflow_options),
                "application/json",
            )

        # Labels for tracking
        labels = {
            "workflow_name": workflow.name,
            "workflow_version": workflow.version,
            **options.get("labels", {}),
        }
        files["labels"] = (
            "labels.json",
            json.dumps(labels),
            "application/json",
        )

        logger.info(f"Submitting WDL workflow {workflow.name} to Cromwell")

        try:
            response = await self._client.post(
                "/",
                files=files,
                data=data,
            )
            response.raise_for_status()
            result = response.json()

            execution_id = result.get("id")
            logger.info(f"Workflow submitted: {execution_id}")

            return WorkflowExecution(
                execution_id=execution_id,
                workflow_name=workflow.name,
                status=WorkflowStatus.SUBMITTED,
                submitted_at=datetime.utcnow(),
                inputs=inputs,
                metadata={"cromwell_response": result},
            )

        except httpx.HTTPStatusError as e:
            error_msg = e.response.text if e.response else str(e)
            logger.error(f"Cromwell submission error: {error_msg}")
            raise RuntimeError(f"Failed to submit workflow: {error_msg}")

    async def status(self, execution_id: str) -> WorkflowExecution:
        """Get workflow status from Cromwell."""
        try:
            # Get basic status
            response = await self._client.get(f"/{execution_id}/status")
            response.raise_for_status()
            status_data = response.json()

            # Get metadata for more details
            metadata_response = await self._client.get(f"/{execution_id}/metadata")
            metadata = {}
            if metadata_response.status_code == 200:
                metadata = metadata_response.json()

            status = self._map_status(status_data.get("status"))

            return WorkflowExecution(
                execution_id=execution_id,
                workflow_name=metadata.get("workflowName", "unknown"),
                status=status,
                submitted_at=self._parse_datetime(metadata.get("submission")),
                started_at=self._parse_datetime(metadata.get("start")),
                completed_at=self._parse_datetime(metadata.get("end")),
                outputs=metadata.get("outputs", {}),
                error_message=self._extract_error(metadata),
                metadata={
                    "calls": self._summarize_calls(metadata.get("calls", {})),
                    "labels": metadata.get("labels", {}),
                },
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get workflow status: {e}")
            return WorkflowExecution(
                execution_id=execution_id,
                workflow_name="unknown",
                status=WorkflowStatus.UNKNOWN,
                submitted_at=datetime.utcnow(),
                error_message=str(e),
            )

    async def cancel(self, execution_id: str) -> bool:
        """Abort workflow execution."""
        try:
            response = await self._client.post(f"/{execution_id}/abort")
            response.raise_for_status()
            logger.info(f"Workflow {execution_id} aborted")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to abort workflow: {e}")
            return False

    async def logs(self, execution_id: str, task: Optional[str] = None) -> str:
        """Get workflow logs."""
        try:
            response = await self._client.get(f"/{execution_id}/logs")
            response.raise_for_status()
            logs_data = response.json()

            if task:
                # Get specific task logs
                calls = logs_data.get("calls", {})
                if task in calls and calls[task]:
                    task_logs = calls[task][0]  # First attempt
                    stdout = task_logs.get("stdout", "")
                    stderr = task_logs.get("stderr", "")
                    return f"=== STDOUT ===/n{stdout}/n/n=== STDERR ===/n{stderr}"
                return f"Task {task} not found"

            # Aggregate all logs
            all_logs = []
            for task_name, attempts in logs_data.get("calls", {}).items():
                for i, attempt in enumerate(attempts):
                    all_logs.append(f"=== {task_name} (attempt {i + 1}) ===")
                    if attempt.get("stdout"):
                        all_logs.append(f"STDOUT: {attempt['stdout']}")
                    if attempt.get("stderr"):
                        all_logs.append(f"STDERR: {attempt['stderr']}")
                    all_logs.append("")

            return "/n".join(all_logs)

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get logs: {e}")
            return f"Error fetching logs: {e}"

    async def list_executions(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
    ) -> list[WorkflowExecution]:
        """Query workflow executions."""
        try:
            params = {"pageSize": limit}
            if workflow_name:
                params["name"] = workflow_name
            if status:
                params["status"] = self._reverse_map_status(status)

            response = await self._client.get("/query", params=params)
            response.raise_for_status()
            data = response.json()

            executions = []
            for wf in data.get("results", []):
                executions.append(WorkflowExecution(
                    execution_id=wf.get("id"),
                    workflow_name=wf.get("name", "unknown"),
                    status=self._map_status(wf.get("status")),
                    submitted_at=self._parse_datetime(wf.get("submission")),
                    started_at=self._parse_datetime(wf.get("start")),
                    completed_at=self._parse_datetime(wf.get("end")),
                ))

            return executions

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to query executions: {e}")
            return []

    @staticmethod
    def _map_status(cromwell_status: Optional[str]) -> WorkflowStatus:
        """Map Cromwell status to WorkflowStatus."""
        mapping = {
            "Submitted": WorkflowStatus.SUBMITTED,
            "Running": WorkflowStatus.RUNNING,
            "Succeeded": WorkflowStatus.SUCCEEDED,
            "Failed": WorkflowStatus.FAILED,
            "Aborted": WorkflowStatus.CANCELLED,
            "Aborting": WorkflowStatus.CANCELLED,
        }
        return mapping.get(cromwell_status, WorkflowStatus.UNKNOWN)

    @staticmethod
    def _reverse_map_status(status: WorkflowStatus) -> str:
        """Map WorkflowStatus to Cromwell status string."""
        mapping = {
            WorkflowStatus.SUBMITTED: "Submitted",
            WorkflowStatus.RUNNING: "Running",
            WorkflowStatus.SUCCEEDED: "Succeeded",
            WorkflowStatus.FAILED: "Failed",
            WorkflowStatus.CANCELLED: "Aborted",
        }
        return mapping.get(status, "")

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Cromwell datetime string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _extract_error(metadata: dict) -> Optional[str]:
        """Extract error message from metadata."""
        failures = metadata.get("failures", [])
        if failures:
            messages = []
            for failure in failures:
                msg = failure.get("message", "")
                caused_by = failure.get("causedBy", [])
                if caused_by:
                    msg += f" Caused by: {caused_by[0].get('message', '')}"
                messages.append(msg)
            return "; ".join(messages)
        return None

    @staticmethod
    def _summarize_calls(calls: dict) -> dict:
        """Summarize call execution statistics."""
        summary = {}
        for task_name, attempts in calls.items():
            if attempts:
                last_attempt = attempts[-1]
                summary[task_name] = {
                    "status": last_attempt.get("executionStatus"),
                    "attempts": len(attempts),
                    "backend": last_attempt.get("backend"),
                }
        return summary

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
