"""
Anomaly detection for QC failures using embedding distances.

Detects outlier runs that deviate significantly from the learned
embedding space, indicating potential quality issues or novel biology.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from scipy import stats


class AnomalyMethod(str, Enum):
    """Anomaly detection methods."""
    ZSCORE = "zscore"           # Distance from centroid
    ISOLATION_FOREST = "iforest"  # Isolation Forest
    LOF = "lof"                 # Local Outlier Factor
    MAHALANOBIS = "mahalanobis"  # Mahalanobis distance


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""
    is_anomaly: bool
    score: float  # Higher = more anomalous
    threshold: float
    method: AnomalyMethod
    details: dict


class EmbeddingAnomalyDetector:
    """Detect anomalous runs using embedding distances.

    Fits a distribution on reference embeddings and flags new
    embeddings that deviate significantly.

    Args:
        method: Detection method to use
        threshold: Z-score or percentile threshold for anomaly detection
        contamination: Expected proportion of anomalies (for some methods)
    """

    def __init__(
        self,
        method: AnomalyMethod = AnomalyMethod.ZSCORE,
        threshold: float = 3.0,
        contamination: float = 0.05,
    ):
        self.method = method
        self.threshold = threshold
        self.contamination = contamination

        # Fitted parameters
        self._centroid: Optional[np.ndarray] = None
        self._std: Optional[float] = None
        self._cov_inv: Optional[np.ndarray] = None
        self._reference_distances: Optional[np.ndarray] = None
        self._fitted = False

    def fit(self, embeddings: np.ndarray) -> "EmbeddingAnomalyDetector":
        """Fit the detector on reference embeddings.

        Args:
            embeddings: Reference embeddings [n_samples, emb_dim]

        Returns:
            Self for chaining
        """
        if len(embeddings) < 10:
            raise ValueError("Need at least 10 samples to fit anomaly detector")

        self._centroid = embeddings.mean(axis=0)

        if self.method == AnomalyMethod.ZSCORE:
            distances = np.linalg.norm(embeddings - self._centroid, axis=1)
            self._std = distances.std()
            self._reference_distances = distances

        elif self.method == AnomalyMethod.MAHALANOBIS:
            # Compute covariance matrix inverse
            cov = np.cov(embeddings.T)
            # Regularize to ensure invertibility
            cov += np.eye(cov.shape[0]) * 1e-6
            self._cov_inv = np.linalg.inv(cov)

        elif self.method == AnomalyMethod.ISOLATION_FOREST:
            try:
                from sklearn.ensemble import IsolationForest
                self._iforest = IsolationForest(
                    contamination=self.contamination,
                    random_state=42,
                )
                self._iforest.fit(embeddings)
            except ImportError:
                raise ImportError("sklearn required for Isolation Forest")

        elif self.method == AnomalyMethod.LOF:
            try:
                from sklearn.neighbors import LocalOutlierFactor
                self._lof = LocalOutlierFactor(
                    n_neighbors=min(20, len(embeddings) - 1),
                    contamination=self.contamination,
                    novelty=True,
                )
                self._lof.fit(embeddings)
            except ImportError:
                raise ImportError("sklearn required for LOF")

        self._fitted = True
        return self

    def predict(self, embedding: np.ndarray) -> AnomalyResult:
        """Predict if an embedding is anomalous.

        Args:
            embedding: Single embedding [emb_dim] or [1, emb_dim]

        Returns:
            AnomalyResult with detection details
        """
        if not self._fitted:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        embedding = np.atleast_2d(embedding)
        if embedding.shape[0] != 1:
            raise ValueError("predict() expects a single embedding")
        embedding = embedding[0]

        if self.method == AnomalyMethod.ZSCORE:
            distance = np.linalg.norm(embedding - self._centroid)
            zscore = distance / self._std if self._std > 0 else 0
            is_anomaly = zscore > self.threshold
            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=float(zscore),
                threshold=self.threshold,
                method=self.method,
                details={
                    "distance": float(distance),
                    "mean_distance": float(self._reference_distances.mean()),
                    "percentile": float(stats.percentileofscore(self._reference_distances, distance)),
                },
            )

        elif self.method == AnomalyMethod.MAHALANOBIS:
            diff = embedding - self._centroid
            mahal_dist = np.sqrt(diff @ self._cov_inv @ diff)
            # Use chi-squared distribution for threshold
            # Degrees of freedom = embedding dimension
            p_value = 1 - stats.chi2.cdf(mahal_dist ** 2, df=len(embedding))
            is_anomaly = p_value < (1 - stats.norm.cdf(self.threshold))
            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=float(mahal_dist),
                threshold=self.threshold,
                method=self.method,
                details={
                    "p_value": float(p_value),
                    "chi2_stat": float(mahal_dist ** 2),
                },
            )

        elif self.method == AnomalyMethod.ISOLATION_FOREST:
            score = -self._iforest.score_samples(embedding.reshape(1, -1))[0]
            prediction = self._iforest.predict(embedding.reshape(1, -1))[0]
            is_anomaly = prediction == -1
            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=float(score),
                threshold=0.0,  # IF uses internal threshold
                method=self.method,
                details={"raw_score": float(score)},
            )

        elif self.method == AnomalyMethod.LOF:
            score = -self._lof.score_samples(embedding.reshape(1, -1))[0]
            prediction = self._lof.predict(embedding.reshape(1, -1))[0]
            is_anomaly = prediction == -1
            return AnomalyResult(
                is_anomaly=is_anomaly,
                score=float(score),
                threshold=0.0,  # LOF uses internal threshold
                method=self.method,
                details={"raw_score": float(score)},
            )

        raise ValueError(f"Unknown method: {self.method}")

    def predict_batch(self, embeddings: np.ndarray) -> list[AnomalyResult]:
        """Predict anomalies for multiple embeddings.

        Args:
            embeddings: Multiple embeddings [n_samples, emb_dim]

        Returns:
            List of AnomalyResult for each embedding
        """
        return [self.predict(emb) for emb in embeddings]

    def get_statistics(self) -> dict:
        """Get fitted statistics for inspection."""
        if not self._fitted:
            raise RuntimeError("Detector not fitted")

        stats_dict = {
            "method": self.method.value,
            "threshold": self.threshold,
            "centroid_norm": float(np.linalg.norm(self._centroid)) if self._centroid is not None else None,
        }

        if self.method == AnomalyMethod.ZSCORE and self._reference_distances is not None:
            stats_dict.update({
                "mean_distance": float(self._reference_distances.mean()),
                "std_distance": float(self._std),
                "min_distance": float(self._reference_distances.min()),
                "max_distance": float(self._reference_distances.max()),
            })

        return stats_dict


class QCMetricAnomalyDetector:
    """Detect anomalies in QC metrics using statistical thresholds.

    Simpler approach for structured QC data with known distributions.
    """

    def __init__(self, metric_thresholds: Optional[dict[str, tuple[float, float]]] = None):
        """Initialize with optional metric thresholds.

        Args:
            metric_thresholds: Dict mapping metric name to (min, max) acceptable range
        """
        self.thresholds = metric_thresholds or self._default_thresholds()
        self._fitted_thresholds: dict[str, tuple[float, float]] = {}

    @staticmethod
    def _default_thresholds() -> dict[str, tuple[float, float]]:
        """Default QC thresholds for scRNA-seq."""
        return {
            "n_genes_by_counts": (200, 10000),
            "total_counts": (1000, 100000),
            "pct_counts_mt": (0, 20),  # Mitochondrial %
            "pct_counts_ribo": (0, 50),  # Ribosomal %
            "doublet_score": (0, 0.3),
            "n_cells": (100, None),  # Minimum cells per sample
        }

    def fit(self, qc_metrics: list[dict]) -> "QCMetricAnomalyDetector":
        """Fit thresholds from reference QC metrics.

        Args:
            qc_metrics: List of QC metric dictionaries

        Returns:
            Self for chaining
        """
        import pandas as pd
        df = pd.DataFrame(qc_metrics)

        for col in df.columns:
            if col in self.thresholds:
                continue  # Use predefined threshold
            if df[col].dtype in [np.float64, np.int64]:
                # Use IQR-based thresholds
                q1, q3 = df[col].quantile([0.25, 0.75])
                iqr = q3 - q1
                self._fitted_thresholds[col] = (
                    q1 - 1.5 * iqr,
                    q3 + 1.5 * iqr,
                )

        return self

    def check(self, qc_metrics: dict) -> list[dict]:
        """Check QC metrics for anomalies.

        Args:
            qc_metrics: Single sample's QC metrics

        Returns:
            List of failed checks with details
        """
        failures = []
        all_thresholds = {**self._fitted_thresholds, **self.thresholds}

        for metric, value in qc_metrics.items():
            if metric not in all_thresholds:
                continue

            min_val, max_val = all_thresholds[metric]

            if min_val is not None and value < min_val:
                failures.append({
                    "metric": metric,
                    "value": value,
                    "threshold": f">= {min_val}",
                    "severity": "warning" if value > min_val * 0.5 else "critical",
                })

            if max_val is not None and value > max_val:
                failures.append({
                    "metric": metric,
                    "value": value,
                    "threshold": f"<= {max_val}",
                    "severity": "warning" if value < max_val * 1.5 else "critical",
                })

        return failures
