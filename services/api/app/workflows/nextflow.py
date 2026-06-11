"""
Nextflow Tower workflow engine integration.

Provides workflow execution via Nextflow Tower API.
https://tower.nf/
"""
from __future__ import annotations
from datetime import datetime
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


class NextflowEngine(WorkflowEngine):
    """Nextflow Tower workflow engine.

    Submits and monitors workflows via Nextflow Tower API.

    Args:
        tower_url: Nextflow Tower API URL
        access_token: Tower API access token
        workspace_id: Tower workspace ID
        compute_env_id: Default compute environment ID
    """

    def __init__(
        self,
        tower_url: str = "https://api.tower.nf",
        access_token: Optional[str] = None,
        workspace_id: Optional[str] = None,
        compute_env_id: Optional[str] = None,
    ):
        self.tower_url = tower_url.rstrip("/")
        self.access_token = access_token
        self.workspace_id = workspace_id
        self.compute_env_id = compute_env_id

        self._client = httpx.AsyncClient(
            base_url=self.tower_url,
            headers={
                "Authorization": f"Bearer {access_token}" if access_token else "",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @property
    def name(self) -> str:
        return "nextflow"

    async def submit(
        self,
        workflow: WorkflowDefinition,
        inputs: dict[str, Any],
        options: Optional[dict[str, Any]] = None,
    ) -> WorkflowExecution:
        """Submit workflow to Nextflow Tower."""
        options = options or {}

        # Build launch request
        launch_request = {
            "launch": {
                "pipeline": workflow.source,
                "revision": workflow.version or "main",
                "computeEnvId": options.get("compute_env_id", self.compute_env_id),
                "workDir": options.get("work_dir"),
                "paramsText": self._format_params(inputs),
                "configProfiles": options.get("profiles", []),
                "resume": options.get("resume", False),
            }
        }

        if self.workspace_id:
            launch_request["launch"]["workspaceId"] = self.workspace_id

        logger.info(f"Submitting workflow {workflow.name} to Nextflow Tower")

        try:
            response = await self._client.post(
                "/workflow/launch",
                json=launch_request,
            )
            response.raise_for_status()
            data = response.json()

            execution_id = data.get("workflowId")
            logger.info(f"Workflow submitted: {execution_id}")

            return WorkflowExecution(
                execution_id=execution_id,
                workflow_name=workflow.name,
                status=WorkflowStatus.SUBMITTED,
                submitted_at=datetime.utcnow(),
                inputs=inputs,
                metadata={"tower_response": data},
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Tower API error: {e.response.text}")
            raise RuntimeError(f"Failed to submit workflow: {e.response.text}")

    async def status(self, execution_id: str) -> WorkflowExecution:
        """Get workflow status from Tower."""
        try:
            response = await self._client.get(f"/workflow/{execution_id}")
            response.raise_for_status()
            data = response.json()

            workflow_data = data.get("workflow", {})
            status = self._map_status(workflow_data.get("status"))

            return WorkflowExecution(
                execution_id=execution_id,
                workflow_name=workflow_data.get("manifest", {}).get("name", "unknown"),
                status=status,
                submitted_at=self._parse_datetime(workflow_data.get("submit")),
                started_at=self._parse_datetime(workflow_data.get("start")),
                completed_at=self._parse_datetime(workflow_data.get("complete")),
                outputs=workflow_data.get("outputs", {}),
                error_message=workflow_data.get("errorMessage"),
                metadata={
                    "run_name": workflow_data.get("runName"),
                    "project_name": workflow_data.get("projectName"),
                    "stats": workflow_data.get("stats", {}),
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
        """Cancel workflow execution."""
        try:
            response = await self._client.post(f"/workflow/{execution_id}/cancel")
            response.raise_for_status()
            logger.info(f"Workflow {execution_id} cancelled")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to cancel workflow: {e}")
            return False

    async def logs(self, execution_id: str, task: Optional[str] = None) -> str:
        """Get workflow logs."""
        try:
            url = f"/workflow/{execution_id}/log"
            if task:
                url = f"/workflow/{execution_id}/task/{task}/log"

            response = await self._client.get(url)
            response.raise_for_status()
            return response.text

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get logs: {e}")
            return f"Error fetching logs: {e}"

    async def list_executions(
        self,
        workflow_name: Optional[str] = None,
        status: Optional[WorkflowStatus] = None,
        limit: int = 50,
    ) -> list[WorkflowExecution]:
        """List workflow executions from Tower."""
        try:
            params = {"max": limit}
            if self.workspace_id:
                params["workspaceId"] = self.workspace_id

            response = await self._client.get("/workflow", params=params)
            response.raise_for_status()
            data = response.json()

            executions = []
            for wf in data.get("workflows", []):
                wf_status = self._map_status(wf.get("status"))

                # Apply filters
                if workflow_name and wf.get("manifest", {}).get("name") != workflow_name:
                    continue
                if status and wf_status != status:
                    continue

                executions.append(WorkflowExecution(
                    execution_id=wf.get("id"),
                    workflow_name=wf.get("manifest", {}).get("name", "unknown"),
                    status=wf_status,
                    submitted_at=self._parse_datetime(wf.get("submit")),
                    started_at=self._parse_datetime(wf.get("start")),
                    completed_at=self._parse_datetime(wf.get("complete")),
                ))

            return executions

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to list executions: {e}")
            return []

    @staticmethod
    def _map_status(tower_status: Optional[str]) -> WorkflowStatus:
        """Map Tower status to WorkflowStatus."""
        mapping = {
            "SUBMITTED": WorkflowStatus.SUBMITTED,
            "RUNNING": WorkflowStatus.RUNNING,
            "SUCCEEDED": WorkflowStatus.SUCCEEDED,
            "FAILED": WorkflowStatus.FAILED,
            "CANCELLED": WorkflowStatus.CANCELLED,
            "UNKNOWN": WorkflowStatus.UNKNOWN,
        }
        return mapping.get(tower_status, WorkflowStatus.UNKNOWN)

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Tower datetime string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _format_params(params: dict[str, Any]) -> str:
        """Format parameters as Nextflow params text."""
        import json
        return json.dumps(params, indent=2)

    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
