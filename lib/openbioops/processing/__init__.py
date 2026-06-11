"""Data processing utilities for scRNA-seq."""

from .pipeline import (
    stage_1_qc,
    stage_2_pca,
    stage_3_umap,
    stage_4_clustering,
)

from .cellranger import (
    parse_cellranger_h5,
    parse_cellranger_metrics,
    get_cellranger_version,
    validate_cellranger_output,
)
from .qc import (
    compute_qc_metrics,
    apply_qc_filters,
    flag_low_quality_cells,
)

__all__ = [
    # Staged pipeline
    "stage_1_qc",
    "stage_2_pca",
    "stage_3_umap",
    "stage_4_clustering",
    # CellRanger utilities
    "parse_cellranger_h5",
    "parse_cellranger_metrics",
    "get_cellranger_version",
    "validate_cellranger_output",
    # QC utilities
    "compute_qc_metrics",
    "apply_qc_filters",
    "flag_low_quality_cells",
]