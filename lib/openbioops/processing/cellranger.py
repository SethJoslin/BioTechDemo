"""
Cell Ranger output parsing and integration.

Supports 10x Genomics Cell Ranger output formats:
- filtered_feature_bc_matrix.h5
- raw_feature_bc_matrix.h5
- metrics_summary.csv
- cloupe.cloupe

Compatible with Cell Ranger versions: 3.0+
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import scanpy as sc


def parse_cellranger_h5(
    path: str | Path,
    filtered: bool = True,
    genome: Optional[str] = None
) -> sc.AnnData:
    """Parse Cell Ranger HDF5 output to AnnData.

    Args:
        path: Path to Cell Ranger output directory or H5 file
        filtered: Use filtered (True) or raw (False) matrix
        genome: Genome name if multi-species (e.g., "GRCh38")

    Returns:
        AnnData object with counts matrix

    Example:
        >>> adata = parse_cellranger_h5("sample_123/outs/")
        >>> adata.shape
        (2638, 32738)
    """
    path = Path(path)

    # Handle both directory and direct H5 file paths
    if path.is_dir():
        matrix_name = "filtered" if filtered else "raw"
        h5_path = path / f"{matrix_name}_feature_bc_matrix.h5"
        if not h5_path.exists():
            # Try alternate location (Cell Ranger < 3.0)
            h5_path = path / "filtered_gene_bc_matrices_h5.h5"
    else:
        h5_path = path

    if not h5_path.exists():
        raise FileNotFoundError(f"Cell Ranger H5 not found: {h5_path}")

    # Load with scanpy
    adata = sc.read_10x_h5(h5_path, genome=genome)

    # Add metadata
    adata.uns["cellranger_version"] = "unknown"  # Would need to parse from h5 attrs
    adata.uns["filtered"] = filtered

    return adata


def parse_cellranger_metrics(path: str | Path) -> Dict[str, float]:
    """Extract QC metrics from Cell Ranger metrics_summary.csv.

    Args:
        path: Path to Cell Ranger output directory or metrics_summary.csv

    Returns:
        Dictionary of QC metrics

    Example:
        >>> metrics = parse_cellranger_metrics("sample_123/outs/")
        >>> metrics["estimated_cells"]
        2638
        >>> metrics["sequencing_saturation"]
        0.87
    """
    path = Path(path)

    # Handle both directory and direct CSV paths
    if path.is_dir():
        csv_path = path / "metrics_summary.csv"
    else:
        csv_path = path

    if not csv_path.exists():
        return {}

    # Read CSV (Cell Ranger uses comma as delimiter)
    df = pd.read_csv(csv_path)

    # Extract and clean metrics
    def clean_numeric(value: str) -> float:
        """Convert Cell Ranger formatted numbers to float."""
        if pd.isna(value):
            return 0.0
        # Remove commas and percent signs
        value = str(value).replace(",", "").replace("%", "")
        try:
            return float(value)
        except ValueError:
            return 0.0

    metrics = {}

    # Standard Cell Ranger metrics (column names may vary by version)
    column_map = {
        "Estimated Number of Cells": "estimated_cells",
        "Mean Reads per Cell": "mean_reads_per_cell",
        "Median Genes per Cell": "median_genes_per_cell",
        "Number of Reads": "total_reads",
        "Valid Barcodes": "valid_barcodes_pct",
        "Sequencing Saturation": "sequencing_saturation",
        "Q30 Bases in Barcode": "q30_barcode",
        "Q30 Bases in RNA Read": "q30_rna_read",
        "Q30 Bases in UMI": "q30_umi",
        "Reads Mapped to Genome": "reads_mapped_genome_pct",
        "Reads Mapped Confidently to Genome": "reads_mapped_confidently_genome_pct",
        "Reads Mapped Confidently to Transcriptome": "reads_mapped_transcriptome_pct",
        "Fraction Reads in Cells": "fraction_reads_in_cells",
        "Total Genes Detected": "total_genes_detected",
        "Median UMI Counts per Cell": "median_umi_per_cell",
    }

    for col_name, metric_name in column_map.items():
        if col_name in df.columns:
            value = df[col_name].iloc[0]
            # Convert percentages to decimals (0.87 instead of 87%)
            if "Sequencing Saturation" in col_name or "Q30" in col_name or "Mapped" in col_name or "Valid" in col_name or "Fraction" in col_name:
                metrics[metric_name] = clean_numeric(value) / 100
            else:
                metrics[metric_name] = clean_numeric(value)

    return metrics


def get_cellranger_version(path: str | Path) -> Optional[str]:
    """Extract Cell Ranger version from output directory.

    Args:
        path: Path to Cell Ranger output directory

    Returns:
        Version string (e.g., "7.0.0") or None
    """
    path = Path(path)

    # Try to read from _invocation file
    invocation_path = path / "_invocation"
    if invocation_path.exists():
        content = invocation_path.read_text()
        # Parse version from invocation file
        for line in content.split("/n"):
            if "cellranger" in line.lower() and "version" in line.lower():
                # Extract version number (e.g., "7.0.0")
                import re
                match = re.search(r'(/d+/./d+/./d+)', line)
                if match:
                    return match.group(1)

    return None


def validate_cellranger_output(path: str | Path) -> Dict[str, bool]:
    """Validate Cell Ranger output directory structure.

    Args:
        path: Path to Cell Ranger output directory

    Returns:
        Dictionary indicating which files are present

    Example:
        >>> validation = validate_cellranger_output("sample_123/outs/")
        >>> validation["filtered_matrix"]
        True
        >>> validation["metrics_summary"]
        True
    """
    path = Path(path)

    return {
        "filtered_matrix": (path / "filtered_feature_bc_matrix.h5").exists(),
        "raw_matrix": (path / "raw_feature_bc_matrix.h5").exists(),
        "metrics_summary": (path / "metrics_summary.csv").exists(),
        "web_summary": (path / "web_summary.html").exists(),
        "cloupe": (path / "cloupe.cloupe").exists(),
        "bam": (path / "possorted_genome_bam.bam").exists(),
        "molecule_info": (path / "molecule_info.h5").exists(),
    }
