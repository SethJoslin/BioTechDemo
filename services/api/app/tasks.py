"""
Celery task definitions for async processing.

Tasks run in separate worker processes and handle long-running
operations like feature extraction.
"""
from pathlib import Path

from celery import Celery

from .config import settings
from .db import SessionLocal, RunModel
from .logger import get_logger

logger = get_logger(__name__)

# Initialize Celery with config-driven URLs
celery_app = Celery(
    "openbioops_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)

# Testing/Dev configuration - run tasks synchronously
import os
if os.getenv("TESTING") or os.getenv("DEV_MODE"):
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )


@celery_app.task(name="extract_features", bind=True, max_retries=3)
def extract_features_task(self, run_id: str, raw_path: str, features_dir: str):
    """Extract features from raw data and update run status.

    Args:
        run_id: UUID of the run to process
        raw_path: Path to raw input data
        features_dir: Directory to write features parquet
    """
    from openbioops.processing.features import generate_features

    logger.info(f"Starting feature extraction for run {run_id}")

    output = Path(features_dir) / f"{run_id}.parquet"

    try:
        generate_features(raw_path, output)
        status = "features_ready"
        logger.info(f"Feature extraction complete for run {run_id}")
    except Exception as e:
        logger.error(f"Feature extraction failed for run {run_id}: {e}")
        status = "failed"
        # Re-raise for Celery retry mechanism
        raise self.retry(exc=e, countdown=60)

    # Update run status in database
    db = SessionLocal()
    try:
        run = db.query(RunModel).filter(RunModel.id == run_id).first()
        if run:
            run.qc_status = status
            db.commit()
            logger.info(f"Updated run {run_id} status to {status}")
    except Exception as e:
        logger.error(f"Failed to update run status: {e}")
        db.rollback()
        raise
    finally:
        db.close()
