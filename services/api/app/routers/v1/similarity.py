"""
Similarity search endpoints for API v1.
"""
from __future__ import annotations
from typing import List

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from ...auth import verify_token
from ... import dependencies
from ...utils import validate_uuid, get_run_or_404

router = APIRouter()


class SimilarRunResponse(BaseModel):
    """A similar run with its similarity score."""
    run_id: str = Field(..., description="ID of the similar run")
    similarity: float = Field(..., ge=0, le=1, description="Cosine similarity score (0-1)")


@router.get(
    "/{run_id}",
    response_model=List[SimilarRunResponse],
    summary="Find similar runs",
)
def get_similarity(
    run_id: str = Path(..., description="Run UUID to find similar runs for"),
    k: int = Query(5, ge=1, le=50, description="Number of similar runs to return"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Find the k most similar runs to the given run.

    The run must have been indexed via /runs/{run_id}/compute_vector first.

    Returns:
        List of similar runs sorted by similarity (highest first)
    """
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    sim_index = dependencies.get_sim_index()

    try:
        sims = sim_index.most_similar(run_id, k=k)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Run vector not indexed. Call /v1/runs/{run_id}/compute_vector first.",
        )

    return [SimilarRunResponse(run_id=r, similarity=float(s)) for r, s in sims]
