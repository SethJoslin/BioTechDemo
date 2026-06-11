"""
Staged single-cell analysis pipeline.

Enterprise-grade design principles:
1. Pure functions - no framework coupling (can run without Prefect)
2. Checkpoint-driven - each stage reads/writes standardized artifacts
3. Single Responsibility - each stage does ONE thing
4. Testable in isolation - no hidden dependencies

Architecture:
    Stage 1: QC → filters cells, saves {run_id}_qc.h5ad
    Stage 2: PCA → dimensionality reduction, saves {run_id}_pca.h5ad
    Stage 3: UMAP → visualization embedding, saves {run_id}_umap.h5ad
    Stage 4: Clustering → cell type discovery, saves final artifacts

Each stage returns a metadata dict (timing, metrics) - NOT Prefect State objects.
Each stage accepts an optional logger - NOT Prefect get_run_logger().
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
import json
import time
from datetime import datetime
import logging

import scanpy as sc
import pandas as pd
import numpy as np

from .qc import compute_qc_metrics, apply_qc_filters


# ═══════════════════════════════════════════════════════════════════════════
# Data Loading Helper
# ═══════════════════════════════════════════════════════════════════════════

def load_h5ad_or_raise(path: Path) -> sc.AnnData:
    """Load AnnData from checkpoint. Raises FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    return sc.read_h5ad(path)


def load_raw_data(raw_path: str | Path) -> sc.AnnData:
    """Load raw count matrix from various formats."""
    raw_path = str(raw_path)
    if raw_path.endswith('.h5ad'):
        return sc.read_h5ad(raw_path)
    elif raw_path.endswith(('.csv', '.csv.gz')):
        df = pd.read_csv(raw_path, index_col=0)
        return sc.AnnData(df)
    elif raw_path.endswith('.parquet'):
        df = pd.read_parquet(raw_path)
        return sc.AnnData(df)
    else:
        raise ValueError(f"Unsupported format: {raw_path}. Expected .h5ad, .csv, or .parquet")


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 1: Load & QC
# ═══════════════════════════════════════════════════════════════════════════

def stage_1_qc(
    run_id: str,
    raw_path: str,
    output_dir: Path,
    min_genes: int = 200,
    max_genes: int = 5000,
    max_pct_mt: float = 20.0,
    mt_prefix: str = "MT-",
    detect_doublets: bool = True,
    remove_doublets: bool = True,
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Stage 1: Load raw data, compute QC metrics, apply filters.

    Args:
        run_id: Unique identifier for this analysis run
        raw_path: Path to raw count matrix (.h5ad, .csv, .parquet)
        output_dir: Directory to write outputs (creates if missing)
        min_genes: Minimum genes per cell threshold
        max_genes: Maximum genes per cell (doublet filter)
        max_pct_mt: Maximum mitochondrial percentage
        mt_prefix: Prefix for mitochondrial genes (default: MT-)
        detect_doublets: Run Scrublet doublet detection
        remove_doublets: Filter out predicted doublets
        logger: Optional logger (accepts any standard Python logger)

    Outputs:
        - {output_dir}/{run_id}.json: QC metrics for dashboard
        - {output_dir}/{run_id}_qc.h5ad: Filtered AnnData checkpoint

    Returns:
        Metadata dict with status, timing, QC metrics, filter stats
    """
    start_time = time.time()
    log = logger or logging.getLogger(__name__)
    log.info(f"[{run_id}] Stage 1/4: Load & QC")

    # Load raw data
    adata = load_raw_data(raw_path)
    log.info(f"[{run_id}] Loaded {adata.n_obs:,} cells × {adata.n_vars:,} genes")

    # Compute QC metrics (modifies adata.obs in-place)
    qc_metrics = compute_qc_metrics(
        adata,
        mt_prefix=mt_prefix,
        detect_doublets=detect_doublets
    )

    # Apply QC filters
    adata_filtered, filter_stats = apply_qc_filters(
        adata,
        min_genes=min_genes,
        max_genes=max_genes,
        max_pct_mt=max_pct_mt,
        remove_doublets=remove_doublets
    )
    log.info(f"[{run_id}] Filtered: {filter_stats['cells_removed']:,} removed, "
             f"{filter_stats['cells_remaining']:,} remaining")

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. QC metrics JSON (for API/dashboard)
    qc_json = output_dir / f"{run_id}.json"
    with open(qc_json, 'w') as f:
        json.dump({
            "metrics": qc_metrics,
            "filter_stats": filter_stats,
            "computed_at": datetime.utcnow().isoformat()
        }, f, indent=2)

    # 2. Checkpoint: filtered AnnData
    checkpoint = output_dir / f"{run_id}_qc.h5ad"
    adata_filtered.write_h5ad(checkpoint)

    duration = time.time() - start_time
    log.info(f"[{run_id}] ✓ Stage 1 complete ({duration:.1f}s)")

    return {
        "stage": 1,
        "status": "completed",
        "duration_sec": round(duration, 2),
        "checkpoint_path": str(checkpoint),
        "n_cells_out": adata_filtered.n_obs,
        "n_genes_out": adata_filtered.n_vars,
        "qc_metrics": qc_metrics,
        "filter_stats": filter_stats
    }


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 2: PCA (Dimensionality Reduction)
# ═══════════════════════════════════════════════════════════════════════════

def stage_2_pca(
    run_id: str,
    qc_checkpoint: Path,
    output_dir: Path,
    features_dir: Path,
    n_top_genes: int = 2000,
    n_pcs: int = 50,
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Stage 2: Normalize, select HVGs, compute PCA.

    Args:
        run_id: Unique identifier for this analysis run
        qc_checkpoint: Path to {run_id}_qc.h5ad from Stage 1
        output_dir: Directory to write checkpoint
        features_dir: Directory to write PCA embeddings parquet
        n_top_genes: Number of highly variable genes to select
        n_pcs: Number of principal components
        logger: Optional logger

    Outputs:
        - {features_dir}/{run_id}.parquet: PCA embeddings (for similarity search)
        - {output_dir}/{run_id}_pca.h5ad: AnnData with PCA checkpoint

    Returns:
        Metadata dict with status, timing, variance explained
    """
    start_time = time.time()
    log = logger or logging.getLogger(__name__)
    log.info(f"[{run_id}] Stage 2/4: PCA")

    # Load from Stage 1 checkpoint
    adata = load_h5ad_or_raise(qc_checkpoint)
    log.info(f"[{run_id}] Loaded QC checkpoint: {adata.n_obs:,} cells × {adata.n_vars:,} genes")

    # Normalization & log-transform
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)

    # Highly variable genes
    sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, flavor='seurat')
    adata_hvg = adata[:, adata.var.highly_variable].copy()
    log.info(f"[{run_id}] Selected {adata_hvg.n_vars:,} HVGs from {adata.n_vars:,} genes")

    # PCA
    sc.tl.pca(adata_hvg, n_comps=n_pcs, svd_solver='arpack')
    variance_ratio = float(adata_hvg.uns['pca']['variance_ratio'].sum())
    log.info(f"[{run_id}] PCA: {n_pcs} components, {variance_ratio*100:.1f}% variance explained")

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    features_dir.mkdir(parents=True, exist_ok=True)

    # 1. PCA embeddings as Parquet (for similarity search)
    pca_df = pd.DataFrame(
        adata_hvg.obsm['X_pca'],
        index=adata_hvg.obs_names,
        columns=[f'PC{i}' for i in range(n_pcs)]
    )
    features_parquet = features_dir / f"{run_id}.parquet"
    pca_df.to_parquet(features_parquet)

    # 2. Checkpoint: AnnData with PCA
    checkpoint = output_dir / f"{run_id}_pca.h5ad"
    adata_hvg.write_h5ad(checkpoint)

    duration = time.time() - start_time
    log.info(f"[{run_id}] ✓ Stage 2 complete ({duration:.1f}s)")

    return {
        "stage": 2,
        "status": "completed",
        "duration_sec": round(duration, 2),
        "checkpoint_path": str(checkpoint),
        "n_hvg": adata_hvg.n_vars,
        "n_pcs": n_pcs,
        "variance_explained": round(variance_ratio, 4)
    }


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 3: UMAP (Visualization Embedding)
# ═══════════════════════════════════════════════════════════════════════════

def stage_3_umap(
    run_id: str,
    pca_checkpoint: Path,
    output_dir: Path,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    n_pcs: int = 50,
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Stage 3: Compute neighbor graph and UMAP embedding.

    Args:
        run_id: Unique identifier for this analysis run
        pca_checkpoint: Path to {run_id}_pca.h5ad from Stage 2
        output_dir: Directory to write outputs
        n_neighbors: UMAP n_neighbors (lower=local, higher=global structure)
        min_dist: UMAP min_dist (lower=tighter clusters)
        n_pcs: Number of PCs to use for neighbor graph
        logger: Optional logger

    Outputs:
        - {output_dir}/{run_id}_umap.parquet: 2D coordinates (no clusters yet)
        - {output_dir}/{run_id}_umap.h5ad: AnnData with UMAP checkpoint

    Returns:
        Metadata dict with status, timing, UMAP bounds
    """
    start_time = time.time()
    log = logger or logging.getLogger(__name__)
    log.info(f"[{run_id}] Stage 3/4: UMAP")

    # Load from Stage 2 checkpoint
    adata = load_h5ad_or_raise(pca_checkpoint)
    log.info(f"[{run_id}] Loaded PCA checkpoint: {adata.n_obs:,} cells")

    # Neighbors graph
    sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs)
    log.info(f"[{run_id}] Computed neighbor graph (n_neighbors={n_neighbors})")

    # UMAP
    sc.tl.umap(adata, min_dist=min_dist)
    log.info(f"[{run_id}] Computed UMAP (min_dist={min_dist})")

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. UMAP coordinates as Parquet (for visualization - no clusters yet)
    umap_df = pd.DataFrame({
        'UMAP1': adata.obsm['X_umap'][:, 0],
        'UMAP2': adata.obsm['X_umap'][:, 1],
        'cell_id': adata.obs_names
    })
    umap_parquet = output_dir / f"{run_id}_umap.parquet"
    umap_df.to_parquet(umap_parquet)

    # 2. Checkpoint: AnnData with UMAP
    checkpoint = output_dir / f"{run_id}_umap.h5ad"
    adata.write_h5ad(checkpoint)

    # Compute bounds for visualization
    bounds = {
        "x_min": float(adata.obsm['X_umap'][:, 0].min()),
        "x_max": float(adata.obsm['X_umap'][:, 0].max()),
        "y_min": float(adata.obsm['X_umap'][:, 1].min()),
        "y_max": float(adata.obsm['X_umap'][:, 1].max())
    }

    duration = time.time() - start_time
    log.info(f"[{run_id}] ✓ Stage 3 complete ({duration:.1f}s)")

    return {
        "stage": 3,
        "status": "completed",
        "duration_sec": round(duration, 2),
        "checkpoint_path": str(checkpoint),
        "n_neighbors": n_neighbors,
        "min_dist": min_dist,
        "umap_bounds": bounds
    }


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 4: Clustering (Cell Type Discovery)
# ═══════════════════════════════════════════════════════════════════════════

def compute_cluster_markers(adata: sc.AnnData, n_genes: int = 25) -> Dict[str, Any]:
    """
    Compute top marker genes for each cluster using Wilcoxon rank-sum test.

    Returns dict mapping cluster_id → {n_cells, top_markers, marker_scores}
    """
    # Run differential expression
    sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')

    # Extract top markers per cluster
    cluster_metadata = {}
    for cluster_id in sorted(adata.obs['leiden'].unique()):
        marker_df = sc.get.rank_genes_groups_df(
            adata,
            group=cluster_id,
            key='rank_genes_groups'
        ).head(n_genes)

        cluster_metadata[str(cluster_id)] = {
            "cluster_id": str(cluster_id),
            "n_cells": int((adata.obs['leiden'] == cluster_id).sum()),
            "top_markers": marker_df['names'].tolist(),
            "marker_scores": marker_df['scores'].round(3).tolist()
        }

    return cluster_metadata


def stage_4_clustering(
    run_id: str,
    umap_checkpoint: Path,
    output_dir: Path,
    resolution: float = 1.0,
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Stage 4: Leiden clustering and marker gene detection.

    Args:
        run_id: Unique identifier for this analysis run
        umap_checkpoint: Path to {run_id}_umap.h5ad from Stage 3
        output_dir: Directory to write outputs
        resolution: Leiden resolution (higher = more granular clusters)
        logger: Optional logger

    Outputs:
        - {output_dir}/{run_id}_umap.parquet: UPDATED with cluster assignments
        - {output_dir}/{run_id}_clusters.json: Cluster metadata & markers
        - {output_dir}/{run_id}_final.h5ad: Final annotated AnnData

    Returns:
        Metadata dict with status, timing, cluster info
    """
    start_time = time.time()
    log = logger or logging.getLogger(__name__)
    log.info(f"[{run_id}] Stage 4/4: Clustering")

    # Load from Stage 3 checkpoint
    adata = load_h5ad_or_raise(umap_checkpoint)
    log.info(f"[{run_id}] Loaded UMAP checkpoint: {adata.n_obs:,} cells")

    # Leiden clustering
    sc.tl.leiden(adata, resolution=resolution)
    n_clusters = len(adata.obs['leiden'].unique())
    log.info(f"[{run_id}] Leiden clustering (resolution={resolution}): {n_clusters} clusters")

    # Compute marker genes
    cluster_metadata = compute_cluster_markers(adata, n_genes=25)
    log.info(f"[{run_id}] Computed marker genes for {n_clusters} clusters")

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Update UMAP parquet with cluster assignments
    umap_df = pd.DataFrame({
        'UMAP1': adata.obsm['X_umap'][:, 0],
        'UMAP2': adata.obsm['X_umap'][:, 1],
        'cluster': adata.obs['leiden'].values,
        'cell_id': adata.obs_names
    })
    umap_parquet = output_dir / f"{run_id}_umap.parquet"
    umap_df.to_parquet(umap_parquet)

    # 2. Cluster metadata JSON
    cluster_json = output_dir / f"{run_id}_clusters.json"
    with open(cluster_json, 'w') as f:
        json.dump(cluster_metadata, f, indent=2)

    # 3. Final annotated AnnData
    final_h5ad = output_dir / f"{run_id}_final.h5ad"
    adata.write_h5ad(final_h5ad)

    # Cluster size distribution
    cluster_sizes = adata.obs['leiden'].value_counts().to_dict()

    duration = time.time() - start_time
    log.info(f"[{run_id}] ✓ Stage 4 complete ({duration:.1f}s)")

    return {
        "stage": 4,
        "status": "completed",
        "duration_sec": round(duration, 2),
        "final_path": str(final_h5ad),
        "resolution": resolution,
        "n_clusters": n_clusters,
        "cluster_sizes": {str(k): int(v) for k, v in cluster_sizes.items()}
    }