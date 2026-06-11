"""Unit tests for Cell Ranger parsing."""
import pytest
from pathlib import Path
import pandas as pd
import numpy as np

from openbioops.processing.cellranger import (
    parse_cellranger_metrics,
    validate_cellranger_output,
)


@pytest.mark.unit
def test_parse_cellranger_metrics(sample_cellranger_metrics):
    """Test parsing Cell Ranger metrics_summary.csv."""
    metrics = parse_cellranger_metrics(sample_cellranger_metrics.parent)

    # Check numeric metrics
    assert metrics["estimated_cells"] == 2638
    assert metrics["mean_reads_per_cell"] == 50345
    assert metrics["median_genes_per_cell"] == 1234
    assert metrics["total_genes_detected"] == 15678
    assert metrics["median_umi_per_cell"] == 3456

    # Check percentage metrics (converted to decimals)
    assert 0.87 < metrics["sequencing_saturation"] < 0.88
    assert 0.95 < metrics["q30_barcode"] < 0.96
    assert 0.91 < metrics["q30_rna_read"] < 0.92
    assert 0.82 < metrics["reads_mapped_transcriptome_pct"] < 0.83
    assert 0.78 < metrics["fraction_reads_in_cells"] < 0.79


@pytest.mark.unit
def test_parse_cellranger_metrics_missing_file(temp_dir):
    """Test handling of missing metrics file."""
    metrics = parse_cellranger_metrics(temp_dir / "nonexistent")
    assert metrics == {}


@pytest.mark.unit
def test_parse_cellranger_metrics_direct_csv_path(sample_cellranger_metrics):
    """Test parsing when given direct path to CSV."""
    metrics = parse_cellranger_metrics(sample_cellranger_metrics)

    assert "estimated_cells" in metrics
    assert metrics["estimated_cells"] == 2638


@pytest.mark.unit
def test_validate_cellranger_output_empty_dir(temp_dir):
    """Test validation on empty directory."""
    validation = validate_cellranger_output(temp_dir)

    assert validation["filtered_matrix"] is False
    assert validation["raw_matrix"] is False
    assert validation["metrics_summary"] is False
    assert validation["web_summary"] is False
    assert validation["cloupe"] is False
    assert validation["bam"] is False
    assert validation["molecule_info"] is False


@pytest.mark.unit
def test_validate_cellranger_output_with_metrics(sample_cellranger_metrics):
    """Test validation when metrics file exists."""
    validation = validate_cellranger_output(sample_cellranger_metrics.parent)

    assert validation["metrics_summary"] is True
    # Other files don't exist in our fixture
    assert validation["filtered_matrix"] is False
