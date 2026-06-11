"""
Workflow orchestration API endpoints.

Provides REST API for submitting and managing bioinformatics workflows.
"""
from __future__ import annotations
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from ...auth import verify_token
from ...logger import get_logger
from ...workflows import (
    WorkflowEngine,
    WorkflowStatus,
    WorkflowExecution,
    WorkflowDefinition,
    NextflowEngine,
    CromwellEngine,
)
from ...config import settings

logger = get_logger(__name__)
router = APIRouter()


# ── Request/Response Models ───────────────────────────────────────────────────

class WorkflowSubmitRequest(BaseModel):
    """Request to submit a workflow."""
    workflow_name: str = Field(..., description="Name of the workflow to run")
    workflow_source: str = Field(..., description="Path or URL to workflow file")
    workflow_version: str = Field("main", description="Workflow version/revision")
    engine: str = Field("nextflow", description="Execution engine: nextflow or cromwell")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Workflow input parameters")
    options: Optional[dict[str, Any]] = Field(None, description="Engine-specific options")


class WorkflowSubmitResponse(BaseModel):
    """Response after workflow submission."""
    execution_id: str
    workflow_name: str
    status: str
    submitted_at: str
    status_url: str


class WorkflowStatusResponse(BaseModel):
    """Workflow execution status."""
    execution_id: str
    workflow_name: str
    status: str
    submitted_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[float]
    outputs: dict[str, Any]
    error_message: Optional[str]
    metadata: dict[str, Any]


class WorkflowListResponse(BaseModel):
    """List of workflow executions."""
    executions: list[WorkflowStatusResponse]
    total: int


class WorkflowLogsResponse(BaseModel):
    """Workflow logs."""
    execution_id: str
    logs: str


# ── Workflow Templates ────────────────────────────────────────────────────────

WORKFLOW_TEMPLATES: dict[str, WorkflowDefinition] = {
    "scrna-qc": WorkflowDefinition(
        name="scrna-qc",
        version="1.0.0",
        description="Single-cell RNA-seq quality control pipeline",
        engine="nextflow",
        source="pipelines/main.nf",
        required_inputs=["input_path", "output_dir"],
        default_inputs={"min_genes": 200, "max_genes": 5000, "max_mito": 20},
    ),
    "feature-extraction": WorkflowDefinition(
        name="feature-extraction",
        version="1.0.0",
        description="Extract features from count matrix for ML embedding",
        engine="nextflow",
        source="pipelines/main.nf",
        required_inputs=["input_path", "output_dir"],
        default_inputs={"n_pcs": 50, "n_hvgs": 2000},
    ),
    "batch-embedding": WorkflowDefinition(
        name="batch-embedding",
        version="1.0.0",
        description="Compute embeddings for multiple samples",
        engine="cromwell",
        source="pipelines/workflow.wdl",
        required_inputs=["sample_manifest", "output_bucket"],
        default_inputs={},
    ),
}


# ── Engine Factory ────────────────────────────────────────────────────────────

def get_workflow_engine(engine_name: str) -> WorkflowEngine:
    """Get workflow engine instance by name."""
    if engine_name == "nextflow":
        return NextflowEngine(
            tower_url=getattr(settings, "nextflow_tower_url", "https://api.tower.nf"),
            access_token=getattr(settings, "nextflow_tower_token", None),
            workspace_id=getattr(settings, "nextflow_workspace_id", None),
            compute_env_id=getattr(settings, "nextflow_compute_env_id", None),
        )
    elif engine_name == "cromwell":
        return CromwellEngine(
            cromwell_url=getattr(settings, "cromwell_url", "http://localhost:8000"),
            auth_token=getattr(settings, "cromwell_token", None),
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown workflow engine: {engine_name}. Use 'nextflow' or 'cromwell'.",
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/templates", summary="List available workflow templates")
def list_templates(user: str = Depends(verify_token)):
    """List pre-configured workflow templates."""
    return {
        "templates": [
            {
                "name": wf.name,
                "version": wf.version,
                "description": wf.description,
                "engine": wf.engine,
                "required_inputs": wf.required_inputs,
                "default_inputs": wf.default_inputs,
            }
            for wf in WORKFLOW_TEMPLATES.values()
        ]
    }


@router.post("", response_model=WorkflowSubmitResponse, summary="Submit a workflow")
async def submit_workflow(
    request: WorkflowSubmitRequest,
    user: str = Depends(verify_token),
):
    """Submit a workflow for execution.

    Can use a pre-defined template by name or provide custom workflow source.
    """
    # Check if using a template
    if request.workflow_name in WORKFLOW_TEMPLATES:
        template = WORKFLOW_TEMPLATES[request.workflow_name]
        workflow = WorkflowDefinition(
            name=template.name,
            version=request.workflow_version or template.version,
            description=template.description,
            engine=request.engine or template.engine,
            source=request.workflow_source or template.source,
            required_inputs=template.required_inputs,
            default_inputs=template.default_inputs,
        )
        # Merge default inputs with provided inputs
        inputs = {**template.default_inputs, **request.inputs}
    else:
        workflow = WorkflowDefinition(
            name=request.workflow_name,
            version=request.workflow_version,
            description="Custom workflow",
            engine=request.engine,
            source=request.workflow_source,
            required_inputs=[],
            default_inputs={},
        )
        inputs = request.inputs

    # Get engine and validate
    engine = get_workflow_engine(workflow.engine)
    errors = engine.validate_inputs(workflow, inputs)
    if errors:
        raise HTTPException(status_code=400, detail={"validation_errors": errors})

    # Submit workflow
    try:
        execution = await engine.submit(workflow, inputs, request.options)
        logger.info(f"User {user} submitted workflow {workflow.name}: {execution.execution_id}")

        return WorkflowSubmitResponse(
            execution_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            status=execution.status.value,
            submitted_at=execution.submitted_at.isoformat(),
            status_url=f"/v1/workflows/{execution.execution_id}",
        )

    except Exception as e:
        logger.error(f"Workflow submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        await engine.close()


@router.get("/{execution_id}", response_model=WorkflowStatusResponse, summary="Get workflow status")
async def get_workflow_status(
    execution_id: str = Path(..., description="Workflow execution ID"),
    engine: str = Query("nextflow", description="Workflow engine"),
    user: str = Depends(verify_token),
):
    """Get the status of a workflow execution."""
    workflow_engine = get_workflow_engine(engine)

    try:
        execution = await workflow_engine.status(execution_id)

        return WorkflowStatusResponse(
            execution_id=execution.execution_id,
            workflow_name=execution.workflow_name,
            status=execution.status.value,
            submitted_at=execution.submitted_at.isoformat() if execution.submitted_at else None,
            started_at=execution.started_at.isoformat() if execution.started_at else None,
            completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
            duration_seconds=execution.duration_seconds,
            outputs=execution.outputs,
            error_message=execution.error_message,
            metadata=execution.metadata,
        )

    finally:
        await workflow_engine.close()


@router.post("/{execution_id}/cancel", summary="Cancel a workflow")
async def cancel_workflow(
    execution_id: str = Path(..., description="Workflow execution ID"),
    engine: str = Query("nextflow", description="Workflow engine"),
    user: str = Depends(verify_token),
):
    """Cancel a running workflow."""
    workflow_engine = get_workflow_engine(engine)

    try:
        success = await workflow_engine.cancel(execution_id)

        if success:
            logger.info(f"User {user} cancelled workflow {execution_id}")
            return {"execution_id": execution_id, "status": "cancelled"}
        else:
            raise HTTPException(status_code=500, detail="Failed to cancel workflow")

    finally:
        await workflow_engine.close()


@router.get("/{execution_id}/logs", response_model=WorkflowLogsResponse, summary="Get workflow logs")
async def get_workflow_logs(
    execution_id: str = Path(..., description="Workflow execution ID"),
    task: Optional[str] = Query(None, description="Specific task name"),
    engine: str = Query("nextflow", description="Workflow engine"),
    user: str = Depends(verify_token),
):
    """Get logs for a workflow execution."""
    workflow_engine = get_workflow_engine(engine)

    try:
        logs = await workflow_engine.logs(execution_id, task)

        return WorkflowLogsResponse(
            execution_id=execution_id,
            logs=logs,
        )

    finally:
        await workflow_engine.close()


@router.get("", response_model=WorkflowListResponse, summary="List workflow executions")
async def list_workflows(
    workflow_name: Optional[str] = Query(None, description="Filter by workflow name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    engine: str = Query("nextflow", description="Workflow engine"),
    user: str = Depends(verify_token),
):
    """List workflow executions."""
    workflow_engine = get_workflow_engine(engine)

    try:
        # Parse status filter
        status_filter = None
        if status:
            try:
                status_filter = WorkflowStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        executions = await workflow_engine.list_executions(
            workflow_name=workflow_name,
            status=status_filter,
            limit=limit,
        )

        return WorkflowListResponse(
            executions=[
                WorkflowStatusResponse(
                    execution_id=ex.execution_id,
                    workflow_name=ex.workflow_name,
                    status=ex.status.value,
                    submitted_at=ex.submitted_at.isoformat() if ex.submitted_at else None,
                    started_at=ex.started_at.isoformat() if ex.started_at else None,
                    completed_at=ex.completed_at.isoformat() if ex.completed_at else None,
                    duration_seconds=ex.duration_seconds,
                    outputs=ex.outputs,
                    error_message=ex.error_message,
                    metadata=ex.metadata,
                )
                for ex in executions
            ],
            total=len(executions),
        )

    finally:
        await workflow_engine.close()
