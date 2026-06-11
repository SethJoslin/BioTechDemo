"""
Analysis pipeline API endpoints for Prefect-orchestrated workflows.

Provides endpoints to start full pipelines, re-run individual stages,
and track progress of multi-stage single-cell analysis.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db, WorkflowRun, RunModel
from ...auth import verify_token
from ...config import settings
from ...workflows import run_single_cell_analysis, rerun_umap_flow, rerun_clustering_flow

router = APIRouter()


# Request/Response Models
class AnalysisParameters(BaseModel):
    """Parameters for staged analysis pipeline."""
    min_genes: int = Field(200, description="Minimum genes per cell")
    max_genes: int = Field(5000, description="Maximum genes per cell")
    max_pct_mt: float = Field(20.0, description="Maximum mitochondrial percentage")
    n_hvg: int = Field(2000, description="Number of highly variable genes")
    n_pcs: int = Field(50, description="Number of principal components")
    n_neighbors: int = Field(15, ge=2, le=100, description="UMAP n_neighbors")
    min_dist: float = Field(0.1, ge=0.0, le=1.0, description="UMAP min_dist")
    resolution: float = Field(1.0, ge=0.1, le=5.0, description="Leiden clustering resolution")


class StartAnalysisRequest(BaseModel):
    """Request to start full analysis pipeline."""
    raw_path: str = Field(..., description="Path to raw count matrix")
    params: Optional[AnalysisParameters] = None


class StartAnalysisResponse(BaseModel):
    """Response after starting analysis."""
    workflow_run_id: str
    run_id: str
    status: str
    created_at: str
    status_url: str


class StageInfo(BaseModel):
    """Information about a single pipeline stage."""
    stage: int
    name: str
    status: str
    duration_sec: Optional[float] = None


class AnalysisStatusResponse(BaseModel):
    """Status of analysis workflow."""
    workflow_run_id: str
    run_id: str
    status: str
    current_stage: Optional[str] = None
    stages: list[StageInfo]
    parameters: Dict[str, Any]
    created_at: str
    error_message: Optional[str] = None


class RerunStageRequest(BaseModel):
    """Request to re-run specific stage(s)."""
    stage: int = Field(..., ge=3, le=4, description="Stage to re-run (3=UMAP, 4=Clustering)")
    params: Optional[AnalysisParameters] = None


# Endpoints
@router.post("/runs/{run_id}/analysis/start", response_model=StartAnalysisResponse)
async def start_analysis(
    run_id: str,
    request: StartAnalysisRequest,
    db: Session = Depends(get_db),
    user: str = Depends(verify_token)
):
    """Start full 4-stage analysis pipeline: QC → PCA → UMAP → Clustering."""
    run = db.query(RunModel).filter(RunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    existing = db.query(WorkflowRun).filter(
        WorkflowRun.run_id == run_id,
        WorkflowRun.status.in_(["pending", "running"])
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Workflow already running for run {run_id}")

    params_dict = request.params.dict() if request.params else {}
    workflow_run = WorkflowRun(
        run_id=run_id,
        status="pending",
        parameters=json.dumps(params_dict),
        started_at=datetime.utcnow()
    )
    db.add(workflow_run)
    db.commit()
    db.refresh(workflow_run)

    try:
        flow_result = run_single_cell_analysis(
            run_id=run_id,
            raw_path=request.raw_path,
            output_dir=str(settings.absolute_artifacts_dir),
            features_dir=str(settings.absolute_features_dir),
            params=params_dict
        )

        workflow_run.status = "running"
        db.commit()

        return StartAnalysisResponse(
            workflow_run_id=workflow_run.id,
            run_id=run_id,
            status=workflow_run.status,
            created_at=workflow_run.created_at.isoformat(),
            status_url=f"/v1/analysis/runs/{run_id}/analysis/status"
        )

    except Exception as e:
        workflow_run.status = "failed"
        workflow_run.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/analysis/status", response_model=AnalysisStatusResponse)
def get_analysis_status(
    run_id: str,
    db: Session = Depends(get_db),
    user: str = Depends(verify_token)
):
    """Get current status of analysis workflow with progress through all 4 stages."""
    workflow_run = db.query(WorkflowRun).filter(
        WorkflowRun.run_id == run_id
    ).order_by(WorkflowRun.created_at.desc()).first()

    if not workflow_run:
        raise HTTPException(status_code=404, detail=f"No workflow found for run {run_id}")

    stage_results = json.loads(workflow_run.stage_results) if workflow_run.stage_results else {}
    stage_names = ["Load & QC", "PCA", "UMAP", "Clustering"]
    stages = []

    for i in range(1, 5):
        stage_status = getattr(workflow_run, f"stage_{i}_status")
        stage_data = stage_results.get(f"stage_{i}", {})
        stages.append(StageInfo(
            stage=i,
            name=stage_names[i-1],
            status=stage_status,
            duration_sec=stage_data.get("duration_sec")
        ))

    params = json.loads(workflow_run.parameters) if workflow_run.parameters else {}

    return AnalysisStatusResponse(
        workflow_run_id=workflow_run.id,
        run_id=workflow_run.run_id,
        status=workflow_run.status,
        current_stage=workflow_run.current_stage,
        stages=stages,
        parameters=params,
        created_at=workflow_run.created_at.isoformat(),
        error_message=workflow_run.error_message
    )


@router.post("/runs/{run_id}/analysis/rerun-stage")
def rerun_stage(
    run_id: str,
    request: RerunStageRequest,
    db: Session = Depends(get_db),
    user: str = Depends(verify_token)
):
    """Re-run specific stage(s) with new parameters. Stage 3=UMAP+Clustering, Stage 4=Clustering only."""
    run = db.query(RunModel).filter(RunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    workflow_run = db.query(WorkflowRun).filter(
        WorkflowRun.run_id == run_id
    ).order_by(WorkflowRun.created_at.desc()).first()

    if not workflow_run:
        raise HTTPException(status_code=404, detail=f"No workflow found for run {run_id}")

    params_dict = request.params.dict() if request.params else {}
    output_dir = str(settings.absolute_artifacts_dir)

    try:
        if request.stage == 3:
            result = rerun_umap_flow(run_id=run_id, output_dir=output_dir, params=params_dict)
            rerun_stages = ["stage_3_umap", "stage_4_clustering"]
        elif request.stage == 4:
            result = rerun_clustering_flow(run_id=run_id, output_dir=output_dir, params=params_dict)
            rerun_stages = ["stage_4_clustering"]
        else:
            raise HTTPException(status_code=400, detail="Can only re-run stages 3 or 4")

        stage_results = json.loads(workflow_run.stage_results) if workflow_run.stage_results else {}
        stage_results.update(result.get("stages", {}))
        workflow_run.stage_results = json.dumps(stage_results)
        db.commit()

        return {
            "workflow_run_id": workflow_run.id,
            "run_id": run_id,
            "status": "completed",
            "rerun_stages": rerun_stages,
            "message": f"Successfully re-ran stage {request.stage}"
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))