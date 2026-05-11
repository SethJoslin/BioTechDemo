from __future__ import annotations
import json
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path as FPath, Body, Query, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import get_db, RunModel
from .ml.run_similarity import compute_run_vector, RunSimilarityIndex
from pathlib import Path

ARTIFACTS_DIR = Path(__file__).parents[3] / "artifacts" / "ml"

app = FastAPI(title="OpenBioOps API", version="0.1.0")
SIM_INDEX = RunSimilarityIndex()


# ── helpers ───────────────────────────────────────────────────────────────────

def require_valid_uuid(run_id: str) -> None:
    try:
        uuid.UUID(run_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid run_id format (expected UUID)")


def get_run_or_404(db: Session, run_id: str) -> RunModel:
    run = db.query(RunModel).filter(RunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="run_id not found")
    return run


def run_to_dict(run: RunModel) -> dict:
    return {
        "id": run.id,
        "name": run.name,
        "metadata": json.loads(run.metadata_ or "{}"),
        "qc": {"status": run.qc_status},
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


# ── models ────────────────────────────────────────────────────────────────────

class CreateRunRequest(BaseModel):
    name: Optional[str] = None
    metadata: Optional[dict] = None


class CreateRunResponse(BaseModel):
    run_id: str
    name: Optional[str] = None


# ── endpoints ─────────────────────────────────────────────────────────────────

@app.post("/runs", response_model=CreateRunResponse)
def create_run(payload: CreateRunRequest = Body(...), db: Session = Depends(get_db)):
    run = RunModel(
        id=str(uuid.uuid4()),
        name=payload.name,
        metadata_=json.dumps(payload.metadata or {}),
        qc_status="unknown",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"run_id": run.id, "name": run.name}


@app.get("/runs")
def list_runs(db: Session = Depends(get_db)) -> List[dict]:
    return [run_to_dict(r) for r in db.query(RunModel).all()]


@app.get("/runs/{run_id}")
def get_run(run_id: str = FPath(...), db: Session = Depends(get_db)):
    require_valid_uuid(run_id)
    return run_to_dict(get_run_or_404(db, run_id))


@app.post("/runs/{run_id}/compute_vector")
def compute_vector_for_run(
    run_id: str = FPath(...),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    require_valid_uuid(run_id)
    get_run_or_404(db, run_id)  # confirm run exists

    if not force and run_id in SIM_INDEX.vectors:
        vec = SIM_INDEX.vectors[run_id]
        return {"run_id": run_id, "vector_len": int(vec.shape[0]), "indexed": True, "cached": True}

    emb_json = ARTIFACTS_DIR / f"{run_id}.json"
    emb_parquet = ARTIFACTS_DIR / f"{run_id}.parquet"

    if emb_json.exists():
        rows = json.loads(emb_json.read_text())
    elif emb_parquet.exists():
        import pandas as pd
        rows = pd.read_parquet(emb_parquet).to_dict(orient="records")
    else:
        raise HTTPException(status_code=404, detail="embeddings not found for run")

    vec = compute_run_vector(rows)
    SIM_INDEX.upsert(run_id, vec)
    return {"run_id": run_id, "vector_len": int(vec.shape[0]), "indexed": True, "cached": False}


@app.get("/similarity/{run_id}")
def get_similarity(
    run_id: str = FPath(...),
    k: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
):
    require_valid_uuid(run_id)
    get_run_or_404(db, run_id)
    try:
        sims = SIM_INDEX.most_similar(run_id, k=k)
    except KeyError:
        raise HTTPException(status_code=404, detail="run vector not indexed — call /compute_vector first")
    return [{"run_id": r, "similarity": float(s)} for r, s in sims]