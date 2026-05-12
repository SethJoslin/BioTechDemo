from celery import Celery
from pathlib import Path
from openbioops.processing.features import generate_features
from .db import SessionLocal, RunModel

celery_app = Celery('openbioops_tasks',
                    broker='redis://redis:6379/0',
                    backend='redis://redis:6379/0')

@celery_app.task(name="extract_features")
def extract_features_task(run_id: str, raw_path: str, features_dir: str):
    output = Path(features_dir) / f"{run_id}.parquet"
    generate_features(raw_path, output)
    # Update run status in DB
    db = SessionLocal()
    try:
        run = db.query(RunModel).filter(RunModel.id == run_id).first()
        if run:
            run.qc_status = "features_ready"
            db.commit()
    finally:
        db.close()
