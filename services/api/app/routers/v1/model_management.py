"""
Model management API endpoints for MLflow model registry integration.

Provides endpoints for:
- Listing model versions
- Promoting models to staging/production
- Viewing model metadata and metrics
"""
from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ...ml.model_registry import ModelRegistry
from ...auth import verify_token

router = APIRouter(prefix="/models", tags=["models"])


class ModelVersionInfo(BaseModel):
    """Model version information."""
    name: str
    version: str
    run_id: str
    stage: str
    status: str
    creation_timestamp: datetime


class ModelVersionDetail(BaseModel):
    """Detailed model version information."""
    name: str
    version: str
    run_id: str
    source: str
    status: str
    stage: str
    creation_timestamp: datetime
    last_updated_timestamp: datetime


class PromoteModelRequest(BaseModel):
    """Request to promote a model version."""
    model_name: str
    version: str
    stage: str  # "Staging" or "Production"
    archive_existing: bool = True


class RunInfo(BaseModel):
    """MLflow run information."""
    run_id: str
    experiment_id: str
    status: str
    start_time: datetime
    end_time: Optional[datetime]
    params: dict
    metrics: dict
    tags: dict


@router.get("/production", response_model=Optional[ModelVersionDetail])
def get_production_model(
    model_name: str = "contrastive_encoder",
    _user: str = Depends(verify_token),
):
    """Get the current production model version.

    Returns the latest model version deployed to production stage.
    This is the model currently serving predictions in the API.
    """
    registry = ModelRegistry()
    model = registry.get_production_model(model_name)

    if not model:
        return None

    return ModelVersionDetail(**model)


@router.get("/staging", response_model=Optional[ModelVersionDetail])
def get_staging_model(
    model_name: str = "contrastive_encoder",
    _user: str = Depends(verify_token),
):
    """Get the current staging model version.

    Returns the latest model version in staging for testing
    before production promotion.
    """
    registry = ModelRegistry()
    model = registry.get_staging_model(model_name)

    if not model:
        return None

    return ModelVersionDetail(**model)


@router.get("/versions", response_model=List[ModelVersionInfo])
def list_model_versions(
    model_name: str = "contrastive_encoder",
    max_results: int = 10,
    _user: str = Depends(verify_token),
):
    """List all versions of a model.

    Returns up to `max_results` model versions ordered by creation time
    (most recent first).
    """
    registry = ModelRegistry()
    versions = registry.list_model_versions(model_name, max_results)

    return [ModelVersionInfo(**v) for v in versions]


@router.post("/promote")
def promote_model(
    request: PromoteModelRequest,
    _user: str = Depends(verify_token),
):
    """Promote a model version to staging or production.

    **Staging**: Use this stage for testing new models before production.
    **Production**: Deploy the model to production (serves live traffic).

    If `archive_existing` is True and promoting to Production, the previous
    production version will be moved to Archived stage.
    """
    registry = ModelRegistry()

    if request.stage not in ["Staging", "Production"]:
        raise HTTPException(
            status_code=400,
            detail="Stage must be 'Staging' or 'Production'"
        )

    if request.stage == "Production":
        success = registry.promote_to_production(
            model_name=request.model_name,
            version=request.version,
            archive_existing=request.archive_existing,
        )
    else:
        success = registry.promote_to_staging(
            model_name=request.model_name,
            version=request.version,
        )

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to promote model to {request.stage}"
        )

    return {
        "message": f"Successfully promoted {request.model_name} version {request.version} to {request.stage}",
        "model_name": request.model_name,
        "version": request.version,
        "stage": request.stage,
    }


@router.get("/runs/{run_id}", response_model=RunInfo)
def get_run_info(
    run_id: str,
    _user: str = Depends(verify_token),
):
    """Get information about a specific MLflow training run.

    Returns all parameters, metrics, and tags logged during the training run.
    Useful for comparing model performance and reproducibility.
    """
    registry = ModelRegistry()
    run = registry.get_model_by_run_id(run_id)

    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )

    return RunInfo(**run)
