"""
Model performance monitoring API endpoints.

Provides endpoints for:
- Tracking prediction logs
- Detecting feature drift
- Monitoring model performance over time
- Alerting on quality issues
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict

import numpy as np
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from scipy.stats import ks_2samp
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from ...db import get_db, PredictionLog
from ...auth import verify_token

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class ModelPerformanceMetrics(BaseModel):
    """Model performance metrics over time."""
    model_version: str
    period_start: datetime
    period_end: datetime
    n_predictions: int
    avg_confidence: Optional[float]
    low_confidence_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


class FeatureDriftMetric(BaseModel):
    """Feature distribution drift metrics."""
    feature_name: str
    ks_statistic: float
    p_value: float
    is_drifting: bool
    drift_severity: str  # "none", "low", "medium", "high"


class DriftDetectionResponse(BaseModel):
    """Response for drift detection analysis."""
    model_version: str
    analysis_period_days: int
    n_recent_predictions: int
    n_baseline_predictions: int
    features_analyzed: int
    drifting_features: int
    drift_metrics: List[FeatureDriftMetric]
    overall_drift_detected: bool


class PredictionDistribution(BaseModel):
    """Distribution of predictions over time."""
    timestamp: datetime
    count: int
    avg_confidence: Optional[float]
    avg_latency_ms: float


@router.get("/performance", response_model=ModelPerformanceMetrics)
def get_model_performance(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    model_version: str = Query("current", description="Model version to analyze"),
    db: Session = Depends(get_db),
    _user: str = Depends(verify_token),
):
    """Get model performance metrics over specified time window.

    Analyzes prediction logs to compute:
    - Total number of predictions
    - Average and distribution of confidence scores
    - Latency percentiles (p50, p95, p99)
    - Low confidence rate (predictions with confidence < 0.5)

    Used for monitoring model health and detecting performance degradation.
    """
    period_start = datetime.utcnow() - timedelta(days=days)

    # Query prediction logs
    query = db.query(PredictionLog).filter(
        PredictionLog.timestamp >= period_start
    )

    if model_version != "current":
        query = query.filter(PredictionLog.model_version == model_version)

    logs = query.all()

    if not logs:
        raise HTTPException(
            status_code=404,
            detail=f"No predictions found for the last {days} days"
        )

    # Calculate metrics
    confidences = [log.confidence for log in logs if log.confidence is not None]
    latencies = [log.latency_ms for log in logs]

    avg_confidence = np.mean(confidences) if confidences else None
    low_confidence_rate = (
        sum(1 for c in confidences if c < 0.5) / len(confidences)
        if confidences else 0.0
    )

    latency_array = np.array(latencies)

    return ModelPerformanceMetrics(
        model_version=model_version,
        period_start=period_start,
        period_end=datetime.utcnow(),
        n_predictions=len(logs),
        avg_confidence=avg_confidence,
        low_confidence_rate=low_confidence_rate,
        avg_latency_ms=float(np.mean(latency_array)),
        p50_latency_ms=float(np.percentile(latency_array, 50)),
        p95_latency_ms=float(np.percentile(latency_array, 95)),
        p99_latency_ms=float(np.percentile(latency_array, 99)),
    )


@router.get("/drift", response_model=DriftDetectionResponse)
def detect_feature_drift(
    analysis_days: int = Query(7, ge=1, le=30, description="Days of recent data to analyze"),
    baseline_days: int = Query(30, ge=7, le=90, description="Days of baseline data for comparison"),
    model_version: str = Query("current", description="Model version to analyze"),
    alpha: float = Query(0.05, ge=0.01, le=0.1, description="Significance level for drift detection"),
    db: Session = Depends(get_db),
    _user: str = Depends(verify_token),
):
    """Detect feature drift using Kolmogorov-Smirnov test.

    Compares recent predictions to a baseline period to detect distribution shifts.
    Uses the two-sample KS test to compare feature distributions.

    **Drift Severity Levels:**
    - **None**: p-value > 0.05 (no significant drift)
    - **Low**: 0.01 < p-value ≤ 0.05 (weak drift)
    - **Medium**: 0.001 < p-value ≤ 0.01 (moderate drift)
    - **High**: p-value ≤ 0.001 (severe drift)

    **When to investigate:**
    - Any feature shows "High" drift severity
    - Multiple features show "Medium" drift
    - Model performance metrics degrade simultaneously

    Returns KS statistic and p-value for each feature.
    """
    # Get recent predictions
    recent_start = datetime.utcnow() - timedelta(days=analysis_days)
    recent_logs = db.query(PredictionLog).filter(
        and_(
            PredictionLog.timestamp >= recent_start,
            PredictionLog.model_version == model_version if model_version != "current" else True
        )
    ).all()

    # Get baseline predictions (older data)
    baseline_end = recent_start
    baseline_start = baseline_end - timedelta(days=baseline_days)
    baseline_logs = db.query(PredictionLog).filter(
        and_(
            PredictionLog.timestamp >= baseline_start,
            PredictionLog.timestamp < baseline_end,
            PredictionLog.model_version == model_version if model_version != "current" else True
        )
    ).all()

    if len(recent_logs) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient recent data: {len(recent_logs)} predictions (need at least 30)"
        )

    if len(baseline_logs) < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient baseline data: {len(baseline_logs)} predictions (need at least 100)"
        )

    # Parse input features and compute drift for each feature
    recent_features = [json.loads(log.input_features) for log in recent_logs]
    baseline_features = [json.loads(log.input_features) for log in baseline_logs]

    # Get feature names (assuming all logs have same features)
    feature_names = list(recent_features[0].keys())

    drift_metrics = []
    drifting_count = 0

    for feature_name in feature_names:
        # Extract feature values
        recent_values = [f[feature_name] for f in recent_features if feature_name in f]
        baseline_values = [f[feature_name] for f in baseline_features if feature_name in f]

        # Skip non-numeric features
        if not all(isinstance(v, (int, float)) for v in recent_values[:5]):
            continue

        # Kolmogorov-Smirnov test
        ks_stat, p_value = ks_2samp(recent_values, baseline_values)

        # Determine drift severity
        if p_value > 0.05:
            drift_severity = "none"
            is_drifting = False
        elif p_value > 0.01:
            drift_severity = "low"
            is_drifting = True
            drifting_count += 1
        elif p_value > 0.001:
            drift_severity = "medium"
            is_drifting = True
            drifting_count += 1
        else:
            drift_severity = "high"
            is_drifting = True
            drifting_count += 1

        drift_metrics.append(FeatureDriftMetric(
            feature_name=feature_name,
            ks_statistic=float(ks_stat),
            p_value=float(p_value),
            is_drifting=is_drifting,
            drift_severity=drift_severity,
        ))

    # Sort by KS statistic (most drifted first)
    drift_metrics.sort(key=lambda x: x.ks_statistic, reverse=True)

    overall_drift_detected = drifting_count > 0

    return DriftDetectionResponse(
        model_version=model_version,
        analysis_period_days=analysis_days,
        n_recent_predictions=len(recent_logs),
        n_baseline_predictions=len(baseline_logs),
        features_analyzed=len(drift_metrics),
        drifting_features=drifting_count,
        drift_metrics=drift_metrics,
        overall_drift_detected=overall_drift_detected,
    )


@router.get("/predictions/distribution", response_model=List[PredictionDistribution])
def get_prediction_distribution(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    bucket_hours: int = Query(24, ge=1, le=168, description="Time bucket size in hours"),
    model_version: str = Query("current", description="Model version to analyze"),
    db: Session = Depends(get_db),
    _user: str = Depends(verify_token),
):
    """Get prediction distribution over time in time buckets.

    Returns aggregated metrics for each time bucket:
    - Number of predictions
    - Average confidence score
    - Average latency

    Useful for visualizing prediction volume and quality over time.
    """
    period_start = datetime.utcnow() - timedelta(days=days)

    query = db.query(PredictionLog).filter(
        PredictionLog.timestamp >= period_start
    )

    if model_version != "current":
        query = query.filter(PredictionLog.model_version == model_version)

    logs = query.order_by(PredictionLog.timestamp).all()

    if not logs:
        return []

    # Group into time buckets
    bucket_size = timedelta(hours=bucket_hours)
    buckets: Dict[datetime, List[PredictionLog]] = {}

    for log in logs:
        bucket_time = log.timestamp.replace(minute=0, second=0, microsecond=0)
        bucket_time = bucket_time - timedelta(hours=bucket_time.hour % bucket_hours)

        if bucket_time not in buckets:
            buckets[bucket_time] = []
        buckets[bucket_time].append(log)

    # Calculate metrics for each bucket
    distribution = []
    for timestamp, bucket_logs in sorted(buckets.items()):
        confidences = [log.confidence for log in bucket_logs if log.confidence is not None]
        latencies = [log.latency_ms for log in bucket_logs]

        distribution.append(PredictionDistribution(
            timestamp=timestamp,
            count=len(bucket_logs),
            avg_confidence=np.mean(confidences) if confidences else None,
            avg_latency_ms=float(np.mean(latencies)),
        ))

    return distribution


@router.post("/predictions/log")
def log_prediction(
    run_id: Optional[str],
    model_version: str,
    input_features: dict,
    prediction: dict,
    confidence: Optional[float],
    latency_ms: float,
    endpoint: str,
    db: Session = Depends(get_db),
    _user: str = Depends(verify_token),
):
    """Log a prediction for monitoring purposes.

    **Internal API**: Used by other endpoints to log predictions automatically.

    Stores prediction details for drift detection and performance monitoring.
    Should be called after every model inference.
    """
    log_entry = PredictionLog(
        run_id=run_id,
        model_version=model_version,
        input_features=json.dumps(input_features),
        prediction=json.dumps(prediction),
        confidence=confidence,
        latency_ms=latency_ms,
        endpoint=endpoint,
    )

    db.add(log_entry)
    db.commit()

    return {"message": "Prediction logged successfully", "log_id": log_entry.id}
