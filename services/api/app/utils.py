"""
Shared utility functions for OpenBioOps API.

This module contains common helper functions used across multiple routers
to avoid code duplication and ensure consistent behavior.
"""
from __future__ import annotations
import json
import uuid
from typing import TYPE_CHECKING

from fastapi import HTTPException, Depends, Path as PathParam
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from .db import RunModel

# Import for dependency
from .db import get_db


def validate_uuid(value: str) -> None:
    """Validate that a string is a valid UUID.

    Args:
        value: String to validate

    Raises:
        HTTPException: 400 error if not a valid UUID
    """
    try:
        uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid UUID format")


def get_run_or_404(db: Session, run_id: str) -> "RunModel":
    """Fetch a run by ID or raise 404.

    Args:
        db: Database session
        run_id: Run UUID to fetch

    Returns:
        RunModel instance

    Raises:
        HTTPException: 404 if run not found
    """
    from .db import RunModel

    run = db.query(RunModel).filter(RunModel.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def get_validated_run(
    run_id: str = PathParam(..., description="Run UUID"),
    db: Session = Depends(get_db)
) -> "RunModel":
    """FastAPI dependency that validates UUID and fetches run in one step.

    This consolidates the repeated pattern of:
        validate_uuid(run_id)
        run = get_run_or_404(db, run_id)

    Usage:
        @router.get("/{run_id}")
        def get_run(run: RunModel = Depends(get_validated_run)):
            return run_to_response(run)

    Args:
        run_id: Run UUID from path
        db: Database session

    Returns:
        RunModel instance

    Raises:
        HTTPException: 400 for invalid UUID, 404 if run not found
    """
    validate_uuid(run_id)
    return get_run_or_404(db, run_id)


def run_to_response(run: "RunModel") -> dict:
    """Convert a RunModel to API response format.

    Args:
        run: RunModel instance

    Returns:
        Dictionary suitable for API response
    """
    return {
        "id": run.id,
        "name": run.name,
        "metadata": json.loads(run.metadata_ or "{}"),
        "qc": {
            "status": run.qc_status,
            "metrics": json.loads(run.qc_metrics_ or "{}"),
        },
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def load_or_compute_embeddings(
    run_id: str,
    model_server,
    artifacts_dir,
    features_dir
) -> list[dict]:
    """Load existing embeddings or compute from features.

    This function centralizes the embedding loading logic used across
    multiple endpoints (compute_vector, batch processing).

    Args:
        run_id: Run identifier
        model_server: Optional ModelServer instance
        artifacts_dir: Path to artifacts directory
        features_dir: Path to features directory

    Returns:
        List of embedding dictionaries

    Raises:
        FileNotFoundError: If neither embeddings nor features exist
    """
    from pathlib import Path
    from .serializers import ArtifactLoader, EmbeddingSerializer
    from .config import settings
    import pandas as pd

    loader = ArtifactLoader(artifacts_dir, run_id)

    # Try to load existing embeddings
    try:
        rows = loader.load_embeddings()
        if not isinstance(rows, list):
            raise ValueError(f"Invalid embeddings format: expected list, got {type(rows).__name__}")
        return rows
    except (FileNotFoundError, ValueError):
        # Compute embeddings from features
        feature_path = settings.get_feature_path(run_id)
        if not feature_path.exists():
            raise FileNotFoundError(f"No features found for run {run_id}")

        if model_server is None:
            # Fallback: use PCA features directly as embeddings
            emb_df = pd.read_parquet(feature_path)
            rows = emb_df.to_dict(orient="records")
        else:
            # Run real inference
            emb_df = model_server.embed(feature_path)
            rows = emb_df.to_dict(orient="records")

        # Cache the embeddings
        emb_json = settings.get_artifact_path(run_id, "json")
        EmbeddingSerializer.save(emb_json, rows)
        emb_df.to_parquet(settings.get_artifact_path(run_id, "parquet"))

        return rows


def validate_path_safe(path: str, allowed_prefixes: list[str] | None = None) -> str:
    """Validate a file path for security.

    Prevents directory traversal attacks by canonicalizing the path and
    ensuring it stays within allowed directories.

    Args:
        path: File path to validate
        allowed_prefixes: Optional list of allowed path prefixes (absolute paths)

    Returns:
        Validated path string

    Raises:
        HTTPException: 400 if path is unsafe or outside allowed directories
    """
    from pathlib import Path

    try:
        # Convert to Path and resolve to canonical absolute path
        # This handles .., ~, symlinks, and other traversal attempts
        resolved_path = Path(path).resolve(strict=False)

        # Check for directory traversal attempts in the original input
        # Reject paths containing .. to prevent traversal attacks
        if ".." in path:
            raise HTTPException(
                status_code=400,
                detail="Invalid path: directory traversal not allowed"
            )

        # Check for dangerous patterns in the original input (before resolution)
        # These patterns could indicate shell injection attempts
        dangerous_patterns = ["${", "$(", "`", ";", "|", "&"]
        for pattern in dangerous_patterns:
            if pattern in path:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid path: contains forbidden sequence '{pattern}'"
                )

        # Check allowed prefixes if specified
        if allowed_prefixes:
            # Convert allowed prefixes to absolute paths
            allowed_paths = [Path(prefix).resolve() for prefix in allowed_prefixes]

            # Check if resolved path is within any allowed directory
            is_allowed = any(
                str(resolved_path).startswith(str(allowed))
                for allowed in allowed_paths
            )

            if not is_allowed:
                raise HTTPException(
                    status_code=400,
                    detail="Path not in allowed directories"
                )

        return str(resolved_path)

    except (ValueError, OSError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid path: {str(e)}"
        )
