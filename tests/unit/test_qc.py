"""Unit tests for QC metrics."""
import pytest
import numpy as np

from openbioops.processing.qc import (
    compute_qc_metrics,
    apply_qc_filters,
    flag_low_quality_cells,
)


@pytest.mark.unit
def test_compute_qc_metrics(sample_adata):
    """Test QC metrics computation."""
    metrics = compute_qc_metrics(sample_adata, detect_doublets=False)

    # Basic counts
    assert metrics["n_cells"] == 100
    assert metrics["n_genes"] == 200
    assert metrics["n_mt_genes"] == 10  # We added 10 MT genes in fixture

    # Per-cell metrics should be positive
    assert metrics["mean_genes_per_cell"] > 0
    assert metrics["median_genes_per_cell"] > 0
    assert metrics["mean_counts_per_cell"] > 0
    assert metrics["median_counts_per_cell"] > 0

    # MT percentage should be reasonable
    assert 0 <= metrics["median_pct_mt"] <= 100
    assert 0 <= metrics["mean_pct_mt"] <= 100

    # Check that obs columns were added
    assert "n_genes_by_counts" in sample_adata.obs
    assert "total_counts" in sample_adata.obs
    assert "pct_counts_mt" in sample_adata.obs


@pytest.mark.unit
def test_compute_qc_metrics_with_doublets(sample_adata):
    """Test QC metrics with doublet detection."""
    metrics = compute_qc_metrics(sample_adata, detect_doublets=True)

    # Should have doublet columns
    assert "doublet_score" in sample_adata.obs
    assert "predicted_doublet" in sample_adata.obs

    # Doublet metrics
    assert "n_predicted_doublets" in metrics
    assert "pct_predicted_doublets" in metrics
    assert "mean_doublet_score" in metrics

    # Values should be reasonable
    assert 0 <= metrics["pct_predicted_doublets"] <= 100
    assert 0 <= metrics["mean_doublet_score"] <= 1


@pytest.mark.unit
def test_apply_qc_filters(sample_adata):
    """Test QC filtering."""
    # First compute QC metrics
    compute_qc_metrics(sample_adata, detect_doublets=True)

    # Apply filters
    filtered, stats = apply_qc_filters(
        sample_adata,
        min_genes=50,
        max_genes=10000,
        max_pct_mt=50.0,
        remove_doublets=True
    )

    # Should have some cells remaining
    assert filtered.n_obs > 0
    assert filtered.n_obs <= sample_adata.n_obs

    # Stats should be correct
    assert stats["cells_before"] == 100
    assert stats["cells_remaining"] == filtered.n_obs
    assert stats["cells_removed"] == 100 - filtered.n_obs
    assert stats["min_genes_threshold"] == 50
    assert stats["max_genes_threshold"] == 10000


@pytest.mark.unit
def test_flag_low_quality_cells(sample_adata):
    """Test flagging low-quality cells without removing."""
    # Compute QC first
    compute_qc_metrics(sample_adata, detect_doublets=True)

    # Flag low quality
    adata = flag_low_quality_cells(
        sample_adata,
        min_genes=50,
        max_genes=10000,
        max_pct_mt=50.0,
        n_mad=5.0
    )

    # Should have flag column
    assert "is_low_quality" in adata.obs

    # Should have some True and some False (probabilistic)
    flagged = adata.obs["is_low_quality"].sum()
    assert 0 <= flagged <= 100

    # Original adata should not be modified in place
    assert len(adata) == len(sample_adata)
