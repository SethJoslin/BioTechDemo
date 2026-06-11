"""
Batch prediction API endpoints for efficient processing of multiple runs.

Provides endpoints for:
- Submitting batch prediction jobs
- Tracking job status
- Retrieving batch results
- Canceling in-progress jobs
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db, RunModel
from ...auth import verify_token
from ...logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


class BatchStatus(str, Enum):
    """Batch job status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Output format for batch results."""
    PARQUET = "parquet"
    CSV = "csv"
    JSON = "json"


class BatchPredictionRequest(BaseModel):
    """Request for batch prediction."""
    run_ids: List[str] = Field(..., min_items=1, max_items=1000, description="List of run IDs to process")
    model_version: str = Field("production", description="Model version to use")
    output_format: OutputFormat = Field(OutputFormat.PARQUET, description="Output file format")
    callback_url: Optional[str] = Field(None, description="Webhook URL to call on completion")
    batch_size: int = Field(32, ge=1, le=128, description="Batch size for inference")


class BatchPredictionResponse(BaseModel):
    """Response for batch prediction."""
    batch_id: str
    status: BatchStatus
    n_total: int
    n_completed: int
    n_failed: int
    output_location: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    estimated_time_remaining_seconds: Optional[int]


class BatchJobSummary(BaseModel):
    """Summary of a batch job."""
    batch_id: str
    status: BatchStatus
    n_total: int
    n_completed: int
    n_failed: int
    created_at: datetime
    model_version: str


# In-memory storage for batch jobs (in production, use Redis or database)
batch_jobs: Dict[str, Dict] = {}


@router.post("", response_model=BatchPredictionResponse)
async def submit_batch_prediction(
    request: BatchPredictionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _user: str = Depends(verify_token),
):
    """Submit a batch prediction job for efficient processing.

    **Use Cases:**
    - Process 100+ runs at once for reporting
    - Batch inference for cost optimization (GPU utilization)
    - Overnight batch jobs for large datasets

    **Features:**
    - Asynchronous processing with status tracking
    - Configurable batch size for GPU optimization
    - Multiple output formats (Parquet, CSV, JSON)
    - Optional webhook notification on completion

    **Limits:**
    - Maximum 1000 runs per batch
    - Batch size 1-128 (adjust based on GPU memory)

    The job will be queued and processed in the background. Use the
    returned `batch_id` to check status via `GET /batch/{batch_id}`.
    """
    # Validate all run_ids exist
    existing_runs = db.query(RunModel).filter(RunModel.id.in_(request.run_ids)).all()
    existing_ids = {run.id for run in existing_runs}
    missing_ids = set(request.run_ids) - existing_ids

    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Runs not found: {', '.join(list(missing_ids)[:5])}{'...' if len(missing_ids) > 5 else ''}"
        )

    # Create batch job
    batch_id = str(uuid.uuid4())
    batch_job = {
        "batch_id": batch_id,
        "status": BatchStatus.QUEUED,
        "n_total": len(request.run_ids),
        "n_completed": 0,
        "n_failed": 0,
        "run_ids": request.run_ids,
        "model_version": request.model_version,
        "output_format": request.output_format.value,
        "callback_url": request.callback_url,
        "batch_size": request.batch_size,
        "output_location": None,
        "error_message": None,
        "created_at": datetime.utcnow(),
        "completed_at": None,
        "results": [],
    }

    batch_jobs[batch_id] = batch_job

    # Queue batch job using Celery
    logger.info(f"Queueing batch job {batch_id} with {len(request.run_ids)} runs")

    # In production, use Celery task
    # For now, use FastAPI background tasks
    background_tasks.add_task(
        process_batch_predictions,
        batch_id=batch_id,
        run_ids=request.run_ids,
        model_version=request.model_version,
        output_format=request.output_format.value,
        batch_size=request.batch_size,
        callback_url=request.callback_url,
    )

    return BatchPredictionResponse(
        batch_id=batch_id,
        status=BatchStatus.QUEUED,
        n_total=len(request.run_ids),
        n_completed=0,
        n_failed=0,
        output_location=None,
        error_message=None,
        created_at=batch_job["created_at"],
        completed_at=None,
        estimated_time_remaining_seconds=None,
    )


@router.get("/{batch_id}", response_model=BatchPredictionResponse)
def get_batch_status(
    batch_id: str,
    _user: str = Depends(verify_token),
):
    """Get status of a batch prediction job.

    Returns current status and progress:
    - `queued`: Job is waiting to start
    - `processing`: Job is currently running
    - `completed`: Job finished successfully
    - `failed`: Job encountered an error
    - `cancelled`: Job was cancelled by user

    **Progress Tracking:**
    - `n_completed`: Number of runs processed successfully
    - `n_failed`: Number of runs that failed
    - `estimated_time_remaining_seconds`: Estimated time to completion

    **Output:**
    - When status is `completed`, `output_location` will contain the results file path
    """
    if batch_id not in batch_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Batch job {batch_id} not found"
        )

    job = batch_jobs[batch_id]

    # Calculate estimated time remaining
    estimated_time = None
    if job["status"] == BatchStatus.PROCESSING and job["n_completed"] > 0:
        elapsed = (datetime.utcnow() - job["created_at"]).total_seconds()
        rate = job["n_completed"] / elapsed
        remaining = job["n_total"] - job["n_completed"]
        estimated_time = int(remaining / rate) if rate > 0 else None

    return BatchPredictionResponse(
        batch_id=job["batch_id"],
        status=job["status"],
        n_total=job["n_total"],
        n_completed=job["n_completed"],
        n_failed=job["n_failed"],
        output_location=job["output_location"],
        error_message=job["error_message"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
        estimated_time_remaining_seconds=estimated_time,
    )


@router.get("", response_model=List[BatchJobSummary])
def list_batch_jobs(
    limit: int = 10,
    _user: str = Depends(verify_token),
):
    """List recent batch jobs.

    Returns summary of recent batch jobs ordered by creation time (newest first).
    """
    jobs = sorted(
        batch_jobs.values(),
        key=lambda x: x["created_at"],
        reverse=True
    )[:limit]

    return [
        BatchJobSummary(
            batch_id=job["batch_id"],
            status=job["status"],
            n_total=job["n_total"],
            n_completed=job["n_completed"],
            n_failed=job["n_failed"],
            created_at=job["created_at"],
            model_version=job["model_version"],
        )
        for job in jobs
    ]


@router.delete("/{batch_id}")
def cancel_batch_job(
    batch_id: str,
    _user: str = Depends(verify_token),
):
    """Cancel a running batch job.

    **Note**: Already processed predictions will not be rolled back.
    Only stops further processing.
    """
    if batch_id not in batch_jobs:
        raise HTTPException(
            status_code=404,
            detail=f"Batch job {batch_id} not found"
        )

    job = batch_jobs[batch_id]

    if job["status"] in [BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job in status: {job['status']}"
        )

    job["status"] = BatchStatus.CANCELLED
    job["completed_at"] = datetime.utcnow()

    logger.info(f"Cancelled batch job {batch_id}")

    return {
        "message": f"Batch job {batch_id} cancelled",
        "n_completed": job["n_completed"],
        "n_total": job["n_total"],
    }


# Background task function
async def process_batch_predictions(
    batch_id: str,
    run_ids: List[str],
    model_version: str,
    output_format: str,
    batch_size: int,
    callback_url: Optional[str],
):
    """Process batch predictions in the background.

    Uses real model inference for embedding generation.
    """
    import json
    import pandas as pd
    from pathlib import Path
    from ...config import settings
    from ... import dependencies
    from ...ml import compute_run_vector
    from ...utils import load_or_compute_embeddings

    job = batch_jobs[batch_id]
    job["status"] = BatchStatus.PROCESSING

    logger.info(f"Starting batch job {batch_id} processing {len(run_ids)} runs")

    try:
        results = []
        model_server = dependencies.get_model_server()
        artifacts_dir = settings.absolute_artifacts_dir
        features_dir = settings.absolute_features_dir

        # Process runs in batches
        for i in range(0, len(run_ids), batch_size):
            if job["status"] == BatchStatus.CANCELLED:
                logger.info(f"Batch job {batch_id} cancelled, stopping processing")
                return

            batch = run_ids[i:i+batch_size]

            # Real inference on batch
            for run_id in batch:
                try:
                    # Load or compute embeddings using centralized utility
                    rows = load_or_compute_embeddings(run_id, model_server, artifacts_dir, features_dir)

                    # Compute run vector
                    vec = compute_run_vector(rows)

                    # Store result
                    result = {
                        "run_id": run_id,
                        "embedding": vec.tolist(),
                        "embedding_dim": int(vec.shape[0]),
                        "model_version": model_version,
                    }
                    results.append(result)
                    job["n_completed"] += 1

                except FileNotFoundError as e:
                    logger.warning(f"No features found for run {run_id}: {e}")
                    job["n_failed"] += 1
                except Exception as e:
                    logger.error(f"Failed to process run {run_id}: {e}")
                    job["n_failed"] += 1

        # Save results to file using configured path
        output_dir = settings.absolute_artifacts_dir / "batch_results"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{batch_id}.{output_format}"

        if output_format == "json":
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
        elif output_format == "csv":
            df = pd.DataFrame(results)
            df.to_csv(output_file, index=False)
        else:  # parquet
            df = pd.DataFrame(results)
            df.to_parquet(output_file, index=False)

        job["status"] = BatchStatus.COMPLETED
        job["output_location"] = str(output_file)
        job["completed_at"] = datetime.utcnow()

        logger.info(f"Batch job {batch_id} completed successfully")

        # Call webhook if provided
        if callback_url:
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(callback_url, json={
                        "batch_id": batch_id,
                        "status": "completed",
                        "output_location": str(output_file),
                    })
            except Exception as e:
                logger.error(f"Failed to call webhook {callback_url}: {e}")

    except Exception as e:
        logger.error(f"Batch job {batch_id} failed: {e}", exc_info=True)
        job["status"] = BatchStatus.FAILED
        job["error_message"] = str(e)
        job["completed_at"] = datetime.utcnow()
