"""
Single-cell analysis workflow using Prefect.

This module provides thin Prefect orchestration around the pure pipeline functions.
The business logic lives in openbioops.processing.pipeline - this file only adds:
- Workflow orchestration (@flow, @task decorators)
- Retry logic and timeouts
- Prefect logging integration
- Stage-level status tracking

Design principle: Keep it thin. If you're writing logic here, it belongs in pipeline.py.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional

from prefect import flow, task, get_run_logger

# Import pure pipeline functions (no Prefect coupling)
from openbioops.processing.pipeline import (
    stage_1_qc,
    stage_2_pca,
    stage_3_umap,
    stage_4_clustering,
)


# ═══════════════════════════════════════════════════════════════════════════
# Prefect Task Wrappers (Thin Orchestration Layer)
# ═══════════════════════════════════════════════════════════════════════════

@task(
    name="Stage 1: Load & QC",
    description="Load raw data, compute QC metrics, apply filters",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=600  # 10 minutes
)
def qc_task(
    run_id: str,
    raw_path: str,
    output_dir: Path,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Prefect task wrapper for stage_1_qc."""
    logger = get_run_logger()

    return stage_1_qc(
        run_id=run_id,
        raw_path=raw_path,
        output_dir=output_dir,
        min_genes=params.get('min_genes', 200),
        max_genes=params.get('max_genes', 5000),
        max_pct_mt=params.get('max_pct_mt', 20.0),
        mt_prefix=params.get('mt_prefix', 'MT-'),
        detect_doublets=params.get('detect_doublets', True),
        remove_doublets=params.get('remove_doublets', True),
        logger=logger
    )


@task(
    name="Stage 2: PCA",
    description="Normalize, select HVGs, compute PCA",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=900  # 15 minutes
)
def pca_task(
    run_id: str,
    qc_checkpoint: Path,
    output_dir: Path,
    features_dir: Path,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Prefect task wrapper for stage_2_pca."""
    logger = get_run_logger()

    return stage_2_pca(
        run_id=run_id,
        qc_checkpoint=qc_checkpoint,
        output_dir=output_dir,
        features_dir=features_dir,
        n_top_genes=params.get('n_hvg', 2000),
        n_pcs=params.get('n_pcs', 50),
        logger=logger
    )


@task(
    name="Stage 3: UMAP",
    description="Compute neighbor graph and UMAP embedding",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=600  # 10 minutes
)
def umap_task(
    run_id: str,
    pca_checkpoint: Path,
    output_dir: Path,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Prefect task wrapper for stage_3_umap."""
    logger = get_run_logger()

    return stage_3_umap(
        run_id=run_id,
        pca_checkpoint=pca_checkpoint,
        output_dir=output_dir,
        n_neighbors=params.get('n_neighbors', 15),
        min_dist=params.get('min_dist', 0.1),
        n_pcs=params.get('n_pcs', 50),
        logger=logger
    )


@task(
    name="Stage 4: Clustering",
    description="Leiden clustering and marker gene detection",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=1200  # 20 minutes
)
def clustering_task(
    run_id: str,
    umap_checkpoint: Path,
    output_dir: Path,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """Prefect task wrapper for stage_4_clustering."""
    logger = get_run_logger()

    return stage_4_clustering(
        run_id=run_id,
        umap_checkpoint=umap_checkpoint,
        output_dir=output_dir,
        resolution=params.get('resolution', 1.0),
        logger=logger
    )


# ═══════════════════════════════════════════════════════════════════════════
# Main Flow (Orchestrates the Full Pipeline)
# ═══════════════════════════════════════════════════════════════════════════

@flow(
    name="Single-Cell Analysis Pipeline",
    description="4-stage scRNA-seq analysis: QC → PCA → UMAP → Clustering",
    timeout_seconds=3600  # 1 hour total
)
def run_single_cell_analysis(
    run_id: str,
    raw_path: str,
    output_dir: str,
    features_dir: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute full single-cell analysis pipeline with checkpointing.

    This flow orchestrates 4 stages:
        1. QC - Load data, compute metrics, filter cells
        2. PCA - Normalize, select HVGs, dimensionality reduction
        3. UMAP - Compute visualization embedding
        4. Clustering - Leiden clustering, marker genes

    Each stage saves a checkpoint, enabling:
    - Fault tolerance (restart from last successful stage)
    - Parameter tuning (re-run downstream stages with different params)
    - Progress visibility (track which stage is executing)

    Args:
        run_id: Unique identifier for this analysis run
        raw_path: Path to raw count matrix (.h5ad, .csv, .parquet)
        output_dir: Directory for checkpoints and final outputs
        features_dir: Directory for PCA embeddings (similarity search)
        params: Pipeline parameters (min_genes, n_pcs, n_neighbors, resolution, etc.)

    Returns:
        Dict with final status, timing, and artifact paths for all stages
    """
    logger = get_run_logger()
    logger.info(f"Starting single-cell analysis pipeline for run_id={run_id}")

    params = params or {}
    output_path = Path(output_dir)
    features_path = Path(features_dir)

    # Stage 1: QC
    logger.info("=" * 70)
    logger.info("STAGE 1/4: Load & QC")
    logger.info("=" * 70)
    stage_1_result = qc_task(run_id, raw_path, output_path, params)
    qc_checkpoint = Path(stage_1_result["checkpoint_path"])
    logger.info(f"✓ Stage 1 complete: {stage_1_result['n_cells_out']} cells")

    # Stage 2: PCA
    logger.info("=" * 70)
    logger.info("STAGE 2/4: PCA")
    logger.info("=" * 70)
    stage_2_result = pca_task(run_id, qc_checkpoint, output_path, features_path, params)
    pca_checkpoint = Path(stage_2_result["checkpoint_path"])
    logger.info(f"✓ Stage 2 complete: {stage_2_result['n_pcs']} PCs")

    # Stage 3: UMAP
    logger.info("=" * 70)
    logger.info("STAGE 3/4: UMAP")
    logger.info("=" * 70)
    stage_3_result = umap_task(run_id, pca_checkpoint, output_path, params)
    umap_checkpoint = Path(stage_3_result["checkpoint_path"])
    logger.info("✓ Stage 3 complete: UMAP computed")

    # Stage 4: Clustering
    logger.info("=" * 70)
    logger.info("STAGE 4/4: Clustering")
    logger.info("=" * 70)
    stage_4_result = clustering_task(run_id, umap_checkpoint, output_path, params)
    logger.info(f"✓ Stage 4 complete: {stage_4_result['n_clusters']} clusters identified")

    # Final summary
    total_duration = (
        stage_1_result["duration_sec"] +
        stage_2_result["duration_sec"] +
        stage_3_result["duration_sec"] +
        stage_4_result["duration_sec"]
    )

    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} min)")
    logger.info(f"Final output: {stage_4_result['final_path']}")

    return {
        "run_id": run_id,
        "status": "completed",
        "total_duration_sec": round(total_duration, 2),
        "stages": {
            "stage_1_qc": stage_1_result,
            "stage_2_pca": stage_2_result,
            "stage_3_umap": stage_3_result,
            "stage_4_clustering": stage_4_result
        },
        "final_artifacts": {
            "qc_metrics": str(output_path / f"{run_id}.json"),
            "pca_embeddings": str(features_path / f"{run_id}.parquet"),
            "umap_coordinates": str(output_path / f"{run_id}_umap.parquet"),
            "cluster_metadata": str(output_path / f"{run_id}_clusters.json"),
            "final_h5ad": stage_4_result["final_path"]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# Partial Pipeline Functions (Re-run Single Stages)
# ═══════════════════════════════════════════════════════════════════════════

@flow(
    name="Re-run UMAP",
    description="Re-compute UMAP with different parameters"
)
def rerun_umap_flow(
    run_id: str,
    output_dir: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Re-run just UMAP stage (Stage 3) with new parameters.

    Useful for tuning n_neighbors without re-running expensive QC/PCA.
    Requires that Stage 2 (PCA) has already completed.
    """
    logger = get_run_logger()
    output_path = Path(output_dir)
    pca_checkpoint = output_path / f"{run_id}_pca.h5ad"

    if not pca_checkpoint.exists():
        raise FileNotFoundError(
            f"PCA checkpoint not found: {pca_checkpoint}. "
            "Run full pipeline first (stages 1-2 required)."
        )

    logger.info(f"Re-running UMAP for run_id={run_id} with params={params}")

    # Re-run UMAP
    stage_3_result = umap_task(run_id, pca_checkpoint, output_path, params)

    # Re-run clustering (since UMAP changed)
    umap_checkpoint = Path(stage_3_result["checkpoint_path"])
    stage_4_result = clustering_task(run_id, umap_checkpoint, output_path, params)

    logger.info(f"✓ UMAP + Clustering re-run complete: {stage_4_result['n_clusters']} clusters")

    return {
        "run_id": run_id,
        "status": "completed",
        "rerun_stages": ["stage_3_umap", "stage_4_clustering"],
        "stage_3_umap": stage_3_result,
        "stage_4_clustering": stage_4_result
    }


@flow(
    name="Re-run Clustering",
    description="Re-compute clustering with different resolution"
)
def rerun_clustering_flow(
    run_id: str,
    output_dir: str,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Re-run just clustering stage (Stage 4) with new resolution parameter.

    Useful for tuning clustering granularity without re-running UMAP.
    Requires that Stage 3 (UMAP) has already completed.
    """
    logger = get_run_logger()
    output_path = Path(output_dir)
    umap_checkpoint = output_path / f"{run_id}_umap.h5ad"

    if not umap_checkpoint.exists():
        raise FileNotFoundError(
            f"UMAP checkpoint not found: {umap_checkpoint}. "
            "Run full pipeline first (stages 1-3 required)."
        )

    logger.info(f"Re-running clustering for run_id={run_id} with resolution={params.get('resolution')}")

    stage_4_result = clustering_task(run_id, umap_checkpoint, output_path, params)

    logger.info(f"✓ Clustering re-run complete: {stage_4_result['n_clusters']} clusters")

    return {
        "run_id": run_id,
        "status": "completed",
        "rerun_stages": ["stage_4_clustering"],
        "stage_4_clustering": stage_4_result
    }