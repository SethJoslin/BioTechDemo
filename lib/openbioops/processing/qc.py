"""
Quality control metrics for single-cell RNA-seq data.

Implements standard scRNA-seq QC:
- Mitochondrial gene percentage (cell viability)
- Ribosomal gene percentage
- Gene/UMI counts per cell
- Doublet detection (Scrublet algorithm)
- QC filtering thresholds
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple

import numpy as np
import scanpy as sc


def compute_qc_metrics(
    adata: sc.AnnData,
    mt_prefix: str = "MT-",
    ribo_prefix: str = "RPS|RPL",
    detect_doublets: bool = True,
    percent_top: Optional[list] = None,
) -> Dict[str, float]:
    """Compute comprehensive QC metrics for single-cell data.

    Args:
        adata: AnnData object (modified in-place with QC columns)
        mt_prefix: Prefix for mitochondrial genes (default: "MT-" for human)
        ribo_prefix: Prefix for ribosomal genes (regex pattern)
        detect_doublets: Run doublet detection (Scrublet)
        percent_top: Calculate percentage of counts from top N genes

    Returns:
        Dictionary of QC metrics

    Example:
        >>> qc = compute_qc_metrics(adata)
        >>> qc["median_pct_mt"]
        3.2
        >>> qc["n_predicted_doublets"]
        87
    """
    # Identify mitochondrial genes
    adata.var["mt"] = adata.var_names.str.startswith(mt_prefix)
    n_mt_genes = adata.var["mt"].sum()

    # Identify ribosomal genes
    adata.var["ribo"] = adata.var_names.str.match(ribo_prefix, case=False)
    n_ribo_genes = adata.var["ribo"].sum()

    # Calculate QC metrics using scanpy
    sc.pp.calculate_qc_metrics(
        adata,
        qc_vars=["mt", "ribo"],
        percent_top=percent_top,
        log1p=False,
        inplace=True
    )

    # Doublet detection (if requested)
    doublet_scores = None
    predicted_doublets = None
    if detect_doublets:
        try:
            import scrublet as scr

            # Run Scrublet
            scrub = scr.Scrublet(adata.X, expected_doublet_rate=0.06)
            doublet_scores, predicted_doublets = scrub.scrub_doublets(
                min_counts=2,
                min_cells=3,
                min_gene_variability_pctl=85,
                n_prin_comps=30,
            )

            # Add to adata
            adata.obs["doublet_score"] = doublet_scores
            adata.obs["predicted_doublet"] = predicted_doublets

        except ImportError:
            # Scrublet not installed
            doublet_scores = np.zeros(adata.n_obs)
            predicted_doublets = np.zeros(adata.n_obs, dtype=bool)
            adata.obs["doublet_score"] = doublet_scores
            adata.obs["predicted_doublet"] = predicted_doublets
        except Exception:
            # Scrublet failed (e.g., too few cells)
            doublet_scores = np.zeros(adata.n_obs)
            predicted_doublets = np.zeros(adata.n_obs, dtype=bool)
            adata.obs["doublet_score"] = doublet_scores
            adata.obs["predicted_doublet"] = predicted_doublets
    else:
        # Not detecting doublets - set default values
        doublet_scores = np.zeros(adata.n_obs)
        predicted_doublets = np.zeros(adata.n_obs, dtype=bool)
        adata.obs["doublet_score"] = doublet_scores
        adata.obs["predicted_doublet"] = predicted_doublets

    # Extract metrics
    metrics = {
        "n_cells": int(adata.n_obs),
        "n_genes": int(adata.n_vars),
        "n_mt_genes": int(n_mt_genes),
        "n_ribo_genes": int(n_ribo_genes),
        # Per-cell gene counts
        "mean_genes_per_cell": float(adata.obs["n_genes_by_counts"].mean()),
        "median_genes_per_cell": int(np.median(adata.obs["n_genes_by_counts"])),
        "min_genes_per_cell": int(adata.obs["n_genes_by_counts"].min()),
        "max_genes_per_cell": int(adata.obs["n_genes_by_counts"].max()),
        # Per-cell UMI/count
        "mean_counts_per_cell": float(adata.obs["total_counts"].mean()),
        "median_counts_per_cell": int(np.median(adata.obs["total_counts"])),
        # Mitochondrial percentage
        "mean_pct_mt": float(adata.obs["pct_counts_mt"].mean()),
        "median_pct_mt": float(np.median(adata.obs["pct_counts_mt"])),
        "max_pct_mt": float(adata.obs["pct_counts_mt"].max()),
        # Ribosomal percentage
        "mean_pct_ribo": float(adata.obs["pct_counts_ribo"].mean()),
        "median_pct_ribo": float(np.median(adata.obs["pct_counts_ribo"])),
    }

    # Add doublet metrics if computed
    if predicted_doublets is not None:
        metrics["n_predicted_doublets"] = int(predicted_doublets.sum())
        metrics["pct_predicted_doublets"] = float(100 * predicted_doublets.mean())
        metrics["mean_doublet_score"] = float(doublet_scores.mean())
    else:
        metrics["n_predicted_doublets"] = 0
        metrics["pct_predicted_doublets"] = 0.0
        metrics["mean_doublet_score"] = 0.0

    # QC filtering stats (standard thresholds)
    qc_pass = (
        (adata.obs["pct_counts_mt"] < 20) &
        (adata.obs["n_genes_by_counts"] > 200) &
        (adata.obs["n_genes_by_counts"] < 5000) &
        (~adata.obs["predicted_doublet"])
    )
    metrics["cells_passing_qc"] = int(qc_pass.sum())
    metrics["pct_cells_passing_qc"] = float(100 * qc_pass.mean())

    return metrics


def apply_qc_filters(
    adata: sc.AnnData,
    min_genes: int = 200,
    max_genes: int = 5000,
    max_pct_mt: float = 20.0,
    remove_doublets: bool = True,
) -> Tuple[sc.AnnData, Dict[str, int]]:
    """Apply standard QC filters to single-cell data.

    Args:
        adata: AnnData object
        min_genes: Minimum genes per cell
        max_genes: Maximum genes per cell (filters likely doublets)
        max_pct_mt: Maximum mitochondrial percentage
        remove_doublets: Remove predicted doublets

    Returns:
        Tuple of (filtered_adata, filter_stats)

    Example:
        >>> filtered, stats = apply_qc_filters(adata)
        >>> stats["cells_removed"]
        215
        >>> stats["cells_remaining"]
        2423
    """
    n_cells_before = adata.n_obs

    # Build filter mask
    filters = (
        (adata.obs["n_genes_by_counts"] >= min_genes) &
        (adata.obs["n_genes_by_counts"] <= max_genes) &
        (adata.obs["pct_counts_mt"] <= max_pct_mt)
    )

    if remove_doublets and "predicted_doublet" in adata.obs:
        filters = filters & (~adata.obs["predicted_doublet"])

    # Apply filter
    adata_filtered = adata[filters].copy()

    # Compute statistics
    stats = {
        "cells_before": int(n_cells_before),
        "cells_removed": int(n_cells_before - adata_filtered.n_obs),
        "cells_remaining": int(adata_filtered.n_obs),
        "pct_removed": float(100 * (1 - adata_filtered.n_obs / n_cells_before)),
        "min_genes_threshold": min_genes,
        "max_genes_threshold": max_genes,
        "max_pct_mt_threshold": max_pct_mt,
        "doublets_removed": remove_doublets,
    }

    return adata_filtered, stats


def flag_low_quality_cells(
    adata: sc.AnnData,
    min_genes: int = 200,
    max_genes: int = 5000,
    max_pct_mt: float = 20.0,
    n_mad: float = 5.0,
) -> sc.AnnData:
    """Flag low-quality cells without removing them.

    Uses both hard thresholds and MAD (median absolute deviation) approach.

    Args:
        adata: AnnData object (modified in-place)
        min_genes: Hard threshold for minimum genes
        max_genes: Hard threshold for maximum genes
        max_pct_mt: Hard threshold for MT%
        n_mad: Number of MADs from median for outlier detection

    Returns:
        AnnData with 'is_low_quality' column added to obs

    Example:
        >>> adata = flag_low_quality_cells(adata)
        >>> adata.obs["is_low_quality"].sum()
        187
    """
    # Hard thresholds
    hard_filter = (
        (adata.obs["n_genes_by_counts"] < min_genes) |
        (adata.obs["n_genes_by_counts"] > max_genes) |
        (adata.obs["pct_counts_mt"] > max_pct_mt)
    )

    # MAD-based outlier detection
    def is_outlier(values: np.ndarray, n_mad: float) -> np.ndarray:
        """Detect outliers using MAD method."""
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        return np.abs(values - median) > n_mad * mad

    mad_filter_genes = is_outlier(adata.obs["n_genes_by_counts"], n_mad)
    mad_filter_counts = is_outlier(adata.obs["total_counts"], n_mad)

    # Combine filters
    adata.obs["is_low_quality"] = hard_filter | mad_filter_genes | mad_filter_counts

    if "predicted_doublet" in adata.obs:
        adata.obs["is_low_quality"] = adata.obs["is_low_quality"] | adata.obs["predicted_doublet"]

    return adata
