# services/api/app/main.py

from __future__ import annotations

from typing import List, Dict
from fastapi import FastAPI, HTTPException

from .ml.run_similarity import (
    RunSimilarityIndex,
    compute_run_vector,
)

app = FastAPI()

# --- Demo in-memory data (replace with your real storage) ---

RUNS = [
    {"id": "demo", "date": "2026-04-30"},
]

EMBEDDINGS: Dict[str, List[dict]] = {
    "demo": [
        {"0": 0.08015053707816414, "1": -0.5403210025445111, "2": 0.051267366920527226, "3": 0.28601559668860654, "4": -0.04177062241908575},
        {"0": 0.515632680090998, "1": 0.02494750863921818, "2": 0.5387146380226487, "3": -0.22664045741867464, "4": -0.10058400292438738},
        {"0": 0.103157489306816, "1": 0.35304155288766303, "2": -0.3511269954196515, "3": 0.14139030128311328, "4": -0.2154341182619997},
        {"0": -0.37553345170927754, "1": 0.14008218799568953, "2": 0.005683546972283652, "3": 0.16186360622002607, "4": 0.06331298915797916},
        {"0": 0.5593084716548833, "1": 0.12558423293421034, "2": -0.23308623765095443, "3": -0.10849893688950228, "4": 0.13292421558264994},
        {"0": 0.047364186538655935, "1": 0.475212682595236, "2": 0.04791657142861722, "3": -0.0050701316035661435, "4": 0.08592571693857483},
        {"0": -0.5656719289179584, "1": -0.04543381607115537, "2": 0.06352069583125837, "3": -0.07866692239863779, "4": 0.0802966293895127},
        {"0": -0.4141922894918505, "1": -0.29332644561151533, "2": -0.2679707659232915, "3": -0.4101403491792679, "4": -0.0621862871600789},
        {"0": -0.4359699220542252, "1": 0.08336023100996222, "2": 0.28313027001327407, "3": 0.14079237374486922, "4": -0.015756085546294225},
        {"0": 0.4857542275037937, "1": -0.32314713183479843, "2": -0.13804909019471173, "3": 0.09895491955303352, "4": 0.07327156524312972},
    ],
}

FEATURES: Dict[str, dict] = {
    "demo": {"n_cells": 100, "n_genes": 2000, "n_hvgs": 300},
}

# --- Similarity index setup ---

similarity_index = RunSimilarityIndex()


def rebuild_similarity_index() -> None:
    """
    Recompute run-level vectors from EMBEDDINGS and rebuild the similarity index.
    """
    global similarity_index
    vectors = {}
    for run in RUNS:
        run_id = run["id"]
        rows = EMBEDDINGS.get(run_id)
        if not rows:
            continue
        vec = compute_run_vector(rows)
        vectors[run_id] = vec
    similarity_index = RunSimilarityIndex(vectors=vectors)


@app.on_event("startup")
def on_startup() -> None:
    rebuild_similarity_index()


# --- Existing endpoints ---

@app.get("/runs")
def list_runs():
    return RUNS


@app.get("/embeddings/{run_id}")
def get_embeddings(run_id: str):
    rows = EMBEDDINGS.get(run_id)
    if rows is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id!r}")
    return rows


@app.get("/features/{run_id}")
def get_features(run_id: str):
    stats = FEATURES.get(run_id)
    if stats is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id!r}")
    return stats


# --- New similarity endpoint ---

@app.get("/similarity/{run_id}")
def get_similarity(run_id: str, k: int = 5):
    """
    Return the top-k most similar runs to the given run_id based on run-level embeddings.
    """
    if run_id not in EMBEDDINGS:
        raise HTTPException(status_code=404, detail=f"Unknown run_id {run_id!r}")

    try:
        results = similarity_index.most_similar(run_id, k=k)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"No vector for run_id {run_id!r}")

    return [
        {"run_id": other_id, "similarity": sim}
        for (other_id, sim) in results
    ]
