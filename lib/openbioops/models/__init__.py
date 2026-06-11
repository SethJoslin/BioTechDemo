"""
OpenBioOps ML models.

Includes:
- ContrastiveEncoder: NT-Xent trained encoder for run embeddings
- CellTypeClassifier: Transfer learning classifier for cell type annotation
- EmbeddingAnomalyDetector: Outlier detection using embedding distances
- QCMetricAnomalyDetector: Statistical QC metric validation
- load_encoder/embed_features: Unified inference utilities
"""
from .contrastive import ContrastiveEncoder, nt_xent_loss, get_dims_from_checkpoint
from .classifier import CellTypeClassifier, CellTypeTrainer
from .anomaly import (
    AnomalyMethod,
    AnomalyResult,
    EmbeddingAnomalyDetector,
    QCMetricAnomalyDetector,
)
from .inference import load_encoder, embed_features

__all__ = [
    # Contrastive learning
    "ContrastiveEncoder",
    "nt_xent_loss",
    "get_dims_from_checkpoint",
    # Classification
    "CellTypeClassifier",
    "CellTypeTrainer",
    # Anomaly detection
    "AnomalyMethod",
    "AnomalyResult",
    "EmbeddingAnomalyDetector",
    "QCMetricAnomalyDetector",
    # Inference
    "load_encoder",
    "embed_features",
]
