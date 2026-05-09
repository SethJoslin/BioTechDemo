# services/api/app/main.py
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, Path as FPath, Body
from pydantic import BaseModel

from .ml.run_similarity import compute_run_vector, RunSimilarityIndex

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RUNS_FILE = DATA_DIR / "runs.json"
ARTIFACTS_DIR = Path(__file__).parents[2] / "artifacts" / "ml"

app = FastAPI(title="OpenBioOps API")

SIM_INDEX = RunSimilarityIndex()

# Helpers
def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def load_runs() -> Dict[str, dict]:
    ensure_data_dir()
    if not RUNS_FILE.exists():
        RUNS_FILE.write_text(json.dumps({}))
        return {}
    return json.loads(RUNS_FILE.read_text())

def save_runs(runs: Dict[str, dict]) -> None:
    ensure_data_dir()
    RUNS_FILE.write_text(json.dumps(runs, indent=2))

def validate_run_id_format(run_id: str) -> bool:
    try:
        uuid.UUID(run_id)
        return True
    except Exception:
        return False

def ensure_run_exists(run_id: str) -> dict:
    runs = load_runs()
    if run_id not in runs:
        raise HTTPException(status_code=404, detail="run_id not found")
    return runs[run_id]

# Models
class CreateRunRequest(BaseModel):
    name: str | None = None
    metadata: dict | None = None

class CreateRunResponse(BaseModel):
    run_id: str
    name: str | None = None

# Endpoints
@app.post("/runs", response_model=CreateRunResponse)
def create_run(payload: CreateRunRequest = Body(...)):
    runs = load_runs()
    run_id = str(uuid.uuid4())
    runs[run_id] = {
        "id": run_id,
        "name": payload.name or run_id,
        "metadata": payload.metadata or {},
        "qc": {"status": "unknown"},
    }
    save_runs(runs)
    return {"run_id": run_id, "name": runs[run_id]["name"]}

@app.get("/runs")
def list_runs():
    runs = load_runs()
    return list(runs.values())

@app.post("/runs/{run_id}/compute_vector")
def compute_vector_for_run(run_id: str = FPath(...), force: bool = False):
    if not validate_run_id_format(run_id):
        raise HTTPException(status_code=400, detail="invalid run_id format")
    ensure_run_exists(run_id)

    # Expect artifact at artifacts/ml/{run_id}.json for demo
    emb_json = ARTIFACTS_DIR / f"{run_id}.json"
    emb_parquet = ARTIFACTS_DIR / f"{run_id}.parquet"

    if emb_json.exists():
        rows = json.loads(emb_json.read_text())
    elif emb_parquet.exists():
        # lazy import to avoid heavy deps at import time
        import pandas as pd
        df = pd.read_parquet(emb_parquet)
        rows = df.to_dict(orient="records")
    else:
        raise HTTPException(status_code=404, detail="embeddings not found for run")

    vec = compute_run_vector(rows)
    SIM_INDEX.upsert(run_id, vec)

    # Optionally persist run vector registry here (left minimal)
    return {"run_id": run_id, "vector_len": int(vec.shape[0]), "indexed": True}

@app.get("/similarity/{run_id}")
def get_similarity(run_id: str = FPath(...), k: int = 5):
    if not validate_run_id_format(run_id):
        raise HTTPException(status_code=400, detail="invalid run_id format")
    ensure_run_exists(run_id)
    try:
        sims = SIM_INDEX.most_similar(run_id, k=k)
    except KeyError:
        raise HTTPException(status_code=404, detail="run vector not indexed")
    return [{"run_id": r, "similarity": float(s)} for r, s in sims]
