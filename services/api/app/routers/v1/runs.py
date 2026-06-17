"""
Run management endpoints for API v1.
"""
from __future__ import annotations
import json
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Body, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...config import settings, PaginationDefaults
from ...db import get_db, RunModel
from ...auth import verify_token
from ...tasks import extract_features_task
from ...ml import compute_run_vector
from ... import dependencies
from ...utils import validate_uuid, get_run_or_404, run_to_response, validate_path_safe
from ...serializers import JSONField, ArtifactLoader

router = APIRouter()


# ── Request/Response Models ───────────────────────────────────────────────────

class CreateRunRequest(BaseModel):
    """Request body for creating a new run."""
    name: Optional[str] = Field(None, description="Human-readable name for the run", max_length=255)
    metadata: Optional[dict] = Field(None, description="Arbitrary metadata for the run")
    raw_data_path: Optional[str] = Field(None, description="Path to raw data file for auto-processing")


class UpdateRunRequest(BaseModel):
    """Request body for updating a run."""
    name: Optional[str] = Field(None, description="Updated name for the run", max_length=255)
    metadata: Optional[dict] = Field(None, description="Updated metadata for the run")


class CreateRunResponse(BaseModel):
    """Response for run creation."""
    id: str = Field(..., description="Unique identifier for the created run")
    name: Optional[str] = Field(None, description="Name of the run")
    metadata: dict = Field(default_factory=dict, description="Metadata for the run")
    created_at: Optional[str] = Field(None, description="Creation timestamp", serialization_alias="created_at")


class RunResponse(BaseModel):
    """Response containing run details."""
    id: str
    name: Optional[str]
    metadata: dict
    qc: dict
    created_at: Optional[str]


class RunListResponse(BaseModel):
    """Response for listing runs."""
    total: int
    offset: int
    limit: int
    runs: list[RunResponse]


class RunStatusResponse(BaseModel):
    """Response for run processing status."""
    run_id: str
    status: str
    features_ready: bool


class QCPayload(BaseModel):
    """Request body for storing QC results."""
    qc_status: str = Field(..., description="QC status: passed, failed, unknown")
    metrics: Optional[dict] = Field(None, description="QC metrics")


class QCResponse(BaseModel):
    """Response for QC operations."""
    run_id: str
    qc_status: str
    metrics: Optional[dict] = None


class ComputeVectorResponse(BaseModel):
    """Response for compute_vector endpoint."""
    run_id: str
    vector_len: int
    indexed: bool
    cached: bool


class FeatureExtractionResponse(BaseModel):
    """Response for feature extraction endpoint."""
    task_id: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=CreateRunResponse, status_code=201, summary="Create a new run")
def create_run(
    payload: CreateRunRequest = Body(...),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Create a new bioinformatics run.

    If raw_data_path is provided, automatically triggers feature extraction.
    """
    # Validate path if provided
    if payload.raw_data_path:
        validate_path_safe(payload.raw_data_path)

    run = RunModel(
        id=str(uuid.uuid4()),
        name=payload.name,
        metadata_=JSONField.dumps(payload.metadata),
        qc_status="unknown",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Auto-generate features if raw data provided
    if payload.raw_data_path:
        model_server = dependencies.get_model_server()
        if model_server is None:
            raise HTTPException(status_code=503, detail="Model server not loaded")
        extract_features_task.apply_async(
            args=(run.id, payload.raw_data_path, str(settings.absolute_features_dir))
        )
        run.qc_status = "processing"
        db.commit()

    return CreateRunResponse(
        id=run.id,
        name=run.name,
        metadata=JSONField.loads(run.metadata_) if run.metadata_ else {},
        created_at=run.created_at.isoformat() if run.created_at else None,
    )


@router.get("", response_model=RunListResponse, summary="List all runs")
def list_runs(
    db: Session = Depends(get_db),
    offset: int = Query(0, ge=0, description="Number of runs to skip"),
    limit: int = Query(
        PaginationDefaults.DEFAULT_PAGE_SIZE,
        ge=1,
        le=PaginationDefaults.MAX_PAGE_SIZE,
        description="Maximum runs to return"
    ),
    user: str = Depends(verify_token),
):
    """List all runs with pagination.

    Returns runs sorted by creation time (newest first).
    """
    total = db.query(RunModel).count()
    runs = (
        db.query(RunModel)
        .order_by(RunModel.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return RunListResponse(
        total=total,
        offset=offset,
        limit=limit,
        runs=[run_to_response(r) for r in runs],
    )


@router.get("/{run_id}", response_model=RunResponse, summary="Get run details")
def get_run(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Get details for a specific run."""
    validate_uuid(run_id)
    return run_to_response(get_run_or_404(db, run_id))


@router.put("/{run_id}", response_model=RunResponse, summary="Update run details")
def update_run(
    run_id: str = Path(..., description="Run UUID"),
    payload: "UpdateRunRequest" = Body(...),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Update run name and/or metadata."""
    validate_uuid(run_id)
    run = get_run_or_404(db, run_id)

    if payload.name is not None:
        run.name = payload.name

    if payload.metadata is not None:
        run.metadata_ = JSONField.dumps(payload.metadata)

    db.commit()
    db.refresh(run)

    return run_to_response(run)


@router.delete("/{run_id}", status_code=204, summary="Delete a run")
def delete_run(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Delete a run and all associated data."""
    validate_uuid(run_id)
    run = get_run_or_404(db, run_id)

    db.delete(run)
    db.commit()

    return None


@router.get("/{run_id}/status", response_model=RunStatusResponse, summary="Get run processing status")
def get_run_status(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
):
    """Get the processing status of a run.

    Does not require authentication for polling convenience.
    """
    validate_uuid(run_id)
    run = get_run_or_404(db, run_id)
    feature_path = settings.get_feature_path(run_id)
    return RunStatusResponse(
        run_id=run_id,
        status=run.qc_status,
        features_ready=feature_path.exists(),
    )


@router.post("/{run_id}/compute_vector", response_model=ComputeVectorResponse, summary="Compute embedding vector")
def compute_vector_for_run(
    run_id: str = Path(..., description="Run UUID"),
    force: bool = Query(False, description="Force recomputation even if cached"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Compute or retrieve the embedding vector for a run.

    This runs ML inference on the run's features and indexes the result
    for similarity search.
    """
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    sim_index = dependencies.get_sim_index()
    model_server = dependencies.get_model_server()

    # Return cached vector if available
    if not force and run_id in sim_index.vectors:
        vec = sim_index.vectors[run_id]
        return ComputeVectorResponse(
            run_id=run_id,
            vector_len=int(vec.shape[0]),
            indexed=True,
            cached=True,
        )

    # Load or compute embeddings using centralized utility
    artifacts_dir = settings.absolute_artifacts_dir
    features_dir = settings.absolute_features_dir

    try:
        from ...utils import load_or_compute_embeddings
        rows = load_or_compute_embeddings(run_id, model_server, artifacts_dir, features_dir)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"No embedding or feature file found. {str(e)}",
        )

    vec = compute_run_vector(rows)
    sim_index.upsert(run_id, vec)

    return ComputeVectorResponse(
        run_id=run_id,
        vector_len=int(vec.shape[0]),
        indexed=True,
        cached=False,
    )


class FeatureExtractionRequest(BaseModel):
    """Request body for feature extraction."""
    raw_path: str = Field(..., description="Path to raw data file")


@router.post("/{run_id}/features", response_model=FeatureExtractionResponse, status_code=202, summary="Trigger feature extraction")
def trigger_feature_extraction(
    run_id: str = Path(..., description="Run UUID"),
    payload: FeatureExtractionRequest = Body(...),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Trigger asynchronous feature extraction for a run.

    This endpoint queues a background task to extract features from raw data.
    Returns immediately with a task ID for tracking.
    """
    validate_uuid(run_id)
    validate_path_safe(payload.raw_path)
    get_run_or_404(db, run_id)

    # Resolve paths starting with 'data/' relative to project root
    from pathlib import Path
    if payload.raw_path.startswith("data/"):
        resolved_path = str(settings.project_root / payload.raw_path)
    else:
        resolved_path = payload.raw_path

    # Queue the feature extraction task
    task = extract_features_task.delay(
        run_id,
        resolved_path,
        str(settings.absolute_features_dir)
    )

    return FeatureExtractionResponse(
        task_id=task.id,
        message="Feature extraction started",
    )


@router.post("/{run_id}/qc", response_model=QCResponse, summary="Store QC results")
def store_qc(
    run_id: str = Path(..., description="Run UUID"),
    payload: QCPayload = Body(...),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Store QC results for a run."""
    validate_uuid(run_id)
    run = get_run_or_404(db, run_id)
    run.qc_status = payload.qc_status
    run.qc_metrics_ = json.dumps(payload.metrics or {})
    db.commit()
    return QCResponse(run_id=run_id, qc_status=run.qc_status)


@router.get("/{run_id}/qc", response_model=QCResponse, summary="Get QC results")
def get_qc(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Get QC results for a run."""
    validate_uuid(run_id)
    run = get_run_or_404(db, run_id)
    return QCResponse(
        run_id=run_id,
        qc_status=run.qc_status,
        metrics=json.loads(run.qc_metrics_ or "{}"),
    )