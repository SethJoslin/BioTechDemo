"""
Visualization data API endpoints.

Provides data endpoints for interactive visualizations:
- UMAP/t-SNE coordinates
- Gene expression data
- Cluster information
- Differential expression results
"""
from __future__ import annotations
from typing import Optional
import json

from fastapi import APIRouter, HTTPException, Path, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import numpy as np

from ...db import get_db
from ...auth import verify_token
from ...config import settings
from ...logger import get_logger
from ...utils import validate_uuid, get_run_or_404

logger = get_logger(__name__)
router = APIRouter()


# ── Response Models ───────────────────────────────────────────────────────────

class Point2D(BaseModel):
    """2D coordinate point."""
    x: float
    y: float


class CellData(BaseModel):
    """Single cell data for visualization."""
    cell_id: str
    x: float
    y: float
    cluster: Optional[int] = None
    cell_type: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class UMAPResponse(BaseModel):
    """UMAP coordinates response."""
    run_id: str
    n_cells: int
    coordinates: list[CellData]
    clusters: list[int]
    bounds: dict  # {x_min, x_max, y_min, y_max}


class GeneExpressionResponse(BaseModel):
    """Gene expression data for a specific gene."""
    run_id: str
    gene: str
    n_cells: int
    expression: list[float]  # Expression values per cell (same order as UMAP)
    min_value: float
    max_value: float
    mean_value: float


class ClusterSummary(BaseModel):
    """Summary statistics for a cluster."""
    cluster_id: int
    n_cells: int
    percentage: float
    top_markers: list[str]
    cell_type: Optional[str] = None


class ClusterResponse(BaseModel):
    """Cluster information response."""
    run_id: str
    n_clusters: int
    clusters: list[ClusterSummary]


class DifferentialGene(BaseModel):
    """Differentially expressed gene."""
    gene: str
    log_fold_change: float
    p_value: float
    adjusted_p_value: float
    mean_expression_group1: float
    mean_expression_group2: float


class DifferentialExpressionResponse(BaseModel):
    """Differential expression results."""
    run_id: str
    group1: str
    group2: str
    n_genes: int
    genes: list[DifferentialGene]


# ── Data Loading Helpers ──────────────────────────────────────────────────────

def load_umap_data(run_id: str) -> dict:
    """Load UMAP coordinates from artifacts."""
    import pandas as pd

    umap_path = settings.absolute_artifacts_dir / f"{run_id}_umap.parquet"
    if not umap_path.exists():
        # Try CSV fallback
        umap_csv = settings.absolute_artifacts_dir / f"{run_id}_umap.csv"
        if umap_csv.exists():
            return pd.read_csv(umap_csv).to_dict(orient="list")
        raise HTTPException(
            status_code=404,
            detail="UMAP coordinates not found. Run dimensionality reduction first.",
        )

    df = pd.read_parquet(umap_path)
    return df.to_dict(orient="list")


def load_expression_data(run_id: str) -> "pd.DataFrame":
    """Load expression matrix."""
    import pandas as pd

    expr_path = settings.absolute_features_dir / f"{run_id}.parquet"
    if not expr_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Expression data not found.",
        )

    return pd.read_parquet(expr_path)


def load_cluster_data(run_id: str) -> dict:
    """Load cluster assignments."""
    cluster_path = settings.absolute_artifacts_dir / f"{run_id}_clusters.json"
    if not cluster_path.exists():
        return {}

    return json.loads(cluster_path.read_text())


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{run_id}/umap", response_model=UMAPResponse, summary="Get UMAP coordinates")
def get_umap_coordinates(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Get UMAP coordinates for visualization.

    Returns 2D coordinates for each cell, along with cluster assignments.
    Suitable for rendering in a scatter plot.
    """
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    try:
        data = load_umap_data(run_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load UMAP data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load UMAP data")

    # Extract coordinates
    x_coords = data.get("UMAP1", data.get("x", data.get("umap_1", [])))
    y_coords = data.get("UMAP2", data.get("y", data.get("umap_2", [])))
    clusters = data.get("cluster", data.get("leiden", [0] * len(x_coords)))
    cell_ids = data.get("cell_id", data.get("index", [f"cell_{i}" for i in range(len(x_coords))]))
    cell_types = data.get("cell_type", [None] * len(x_coords))

    if not x_coords or not y_coords:
        raise HTTPException(status_code=404, detail="UMAP coordinates not found in data")

    coordinates = [
        CellData(
            cell_id=str(cell_ids[i]) if i < len(cell_ids) else f"cell_{i}",
            x=float(x_coords[i]),
            y=float(y_coords[i]),
            cluster=int(clusters[i]) if i < len(clusters) else 0,
            cell_type=cell_types[i] if i < len(cell_types) else None,
        )
        for i in range(len(x_coords))
    ]

    # Calculate bounds for viewport
    x_arr = np.array(x_coords)
    y_arr = np.array(y_coords)

    return UMAPResponse(
        run_id=run_id,
        n_cells=len(coordinates),
        coordinates=coordinates,
        clusters=sorted(set(clusters)),
        bounds={
            "x_min": float(x_arr.min()),
            "x_max": float(x_arr.max()),
            "y_min": float(y_arr.min()),
            "y_max": float(y_arr.max()),
        },
    )


@router.get("/{run_id}/umap/stream", summary="Stream UMAP coordinates")
async def stream_umap_coordinates(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Stream UMAP coordinates as newline-delimited JSON.

    More efficient for large datasets (>100k cells).
    """
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    def generate():
        try:
            data = load_umap_data(run_id)
            x_coords = data.get("UMAP1", data.get("x", []))
            y_coords = data.get("UMAP2", data.get("y", []))
            clusters = data.get("cluster", [0] * len(x_coords))

            for i in range(len(x_coords)):
                point = {
                    "i": i,
                    "x": float(x_coords[i]),
                    "y": float(y_coords[i]),
                    "c": int(clusters[i]) if i < len(clusters) else 0,
                }
                yield json.dumps(point) + " \n"

        except Exception as e:
            logger.error(f"Error streaming UMAP: {e}")
            yield json.dumps({"error": str(e)}) + " \n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/{run_id}/expression/{gene}", response_model=GeneExpressionResponse, summary="Get gene expression")
def get_gene_expression(
    run_id: str = Path(..., description="Run UUID"),
    gene: str = Path(..., description="Gene symbol"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Get expression values for a specific gene.

    Returns expression values in the same order as UMAP coordinates,
    suitable for coloring a scatter plot.
    """
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    try:
        expr_df = load_expression_data(run_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load expression data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load expression data")

    if gene not in expr_df.columns:
        raise HTTPException(
            status_code=404,
            detail=f"Gene '{gene}' not found in expression data",
        )

    expression = expr_df[gene].values

    return GeneExpressionResponse(
        run_id=run_id,
        gene=gene,
        n_cells=len(expression),
        expression=[float(v) for v in expression],
        min_value=float(expression.min()),
        max_value=float(expression.max()),
        mean_value=float(expression.mean()),
    )


@router.get("/{run_id}/genes", summary="List available genes")
def list_genes(
    run_id: str = Path(..., description="Run UUID"),
    search: Optional[str] = Query(None, description="Search term"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """List available genes in the expression matrix."""
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    try:
        expr_df = load_expression_data(run_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load expression data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load expression data")

    genes = list(expr_df.columns)

    if search:
        search_lower = search.lower()
        genes = [g for g in genes if search_lower in g.lower()]

    return {
        "run_id": run_id,
        "total_genes": len(expr_df.columns),
        "genes": genes[:limit],
    }


@router.get("/{run_id}/clusters", response_model=ClusterResponse, summary="Get cluster summary")
def get_cluster_summary(
    run_id: str = Path(..., description="Run UUID"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Get summary statistics for each cluster."""
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    try:
        data = load_umap_data(run_id)
        cluster_data = load_cluster_data(run_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load cluster data: {e}")
        raise HTTPException(status_code=500, detail="Failed to load cluster data")

    clusters = data.get("cluster", data.get("leiden", []))
    if not clusters:
        raise HTTPException(status_code=404, detail="Cluster data not found")

    # Count cells per cluster
    from collections import Counter
    cluster_counts = Counter(clusters)
    total_cells = len(clusters)

    cluster_summaries = []
    for cluster_id in sorted(cluster_counts.keys()):
        n_cells = cluster_counts[cluster_id]
        summary = ClusterSummary(
            cluster_id=int(cluster_id),
            n_cells=n_cells,
            percentage=round(100 * n_cells / total_cells, 2),
            top_markers=cluster_data.get(str(cluster_id), {}).get("markers", [])[:5],
            cell_type=cluster_data.get(str(cluster_id), {}).get("cell_type"),
        )
        cluster_summaries.append(summary)

    return ClusterResponse(
        run_id=run_id,
        n_clusters=len(cluster_summaries),
        clusters=cluster_summaries,
    )


@router.post("/{run_id}/differential", response_model=DifferentialExpressionResponse, summary="Compute differential expression")
def compute_differential_expression(
    run_id: str = Path(..., description="Run UUID"),
    group1: str = Query(..., description="First group (cluster ID or cell type)"),
    group2: str = Query(..., description="Second group (cluster ID or cell type)"),
    top_n: int = Query(50, ge=1, le=500, description="Number of top genes to return"),
    db: Session = Depends(get_db),
    user: str = Depends(verify_token),
):
    """Compute differential expression between two groups.

    Groups can be specified as cluster IDs or cell type labels.
    Returns top differentially expressed genes ranked by adjusted p-value.
    """
    validate_uuid(run_id)
    get_run_or_404(db, run_id)

    try:
        import pandas as pd
        from scipy import stats

        expr_df = load_expression_data(run_id)
        umap_data = load_umap_data(run_id)

        clusters = umap_data.get("cluster", umap_data.get("leiden", []))
        cell_types = umap_data.get("cell_type", [])

        # Determine group membership
        group1_mask = np.zeros(len(clusters), dtype=bool)
        group2_mask = np.zeros(len(clusters), dtype=bool)

        # Try cluster IDs first, then cell types
        try:
            g1_id = int(group1)
            g2_id = int(group2)
            group1_mask = np.array(clusters) == g1_id
            group2_mask = np.array(clusters) == g2_id
        except ValueError:
            if cell_types:
                group1_mask = np.array(cell_types) == group1
                group2_mask = np.array(cell_types) == group2

        if not group1_mask.any():
            raise HTTPException(status_code=400, detail=f"Group '{group1}' not found")
        if not group2_mask.any():
            raise HTTPException(status_code=400, detail=f"Group '{group2}' not found")

        # Compute differential expression
        results = []
        for gene in expr_df.columns:
            g1_expr = expr_df.loc[group1_mask, gene].values
            g2_expr = expr_df.loc[group2_mask, gene].values

            # Skip genes with no variance
            if g1_expr.std() == 0 and g2_expr.std() == 0:
                continue

            # Welch's t-test
            t_stat, p_value = stats.ttest_ind(g1_expr, g2_expr, equal_var=False)

            # Log fold change (add pseudocount to avoid log(0))
            mean1 = g1_expr.mean() + 1e-9
            mean2 = g2_expr.mean() + 1e-9
            log_fc = np.log2(mean1 / mean2)

            results.append({
                "gene": gene,
                "log_fold_change": float(log_fc),
                "p_value": float(p_value) if not np.isnan(p_value) else 1.0,
                "mean_expression_group1": float(g1_expr.mean()),
                "mean_expression_group2": float(g2_expr.mean()),
            })

        # Multiple testing correction (Benjamini-Hochberg)
        results = sorted(results, key=lambda x: x["p_value"])
        n_tests = len(results)
        for i, r in enumerate(results):
            r["adjusted_p_value"] = min(r["p_value"] * n_tests / (i + 1), 1.0)

        # Sort by adjusted p-value and take top N
        results = sorted(results, key=lambda x: x["adjusted_p_value"])[:top_n]

        return DifferentialExpressionResponse(
            run_id=run_id,
            group1=group1,
            group2=group2,
            n_genes=len(results),
            genes=[DifferentialGene(**r) for r in results],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Differential expression failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
