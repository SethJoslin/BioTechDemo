"""
Prometheus metrics for monitoring API performance.

This module provides application-level metrics for observability:
- Request counts and latencies
- Embedding computation times
- Database query times
- Error rates and types
"""
from __future__ import annotations

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# ── Request Metrics ───────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "api_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0),
)

REQUEST_IN_PROGRESS = Gauge(
    "api_requests_in_progress",
    "Number of requests currently being processed",
)

# ── ML Model Metrics ──────────────────────────────────────────────────────────

EMBEDDING_COMPUTE_TIME = Histogram(
    "embedding_compute_seconds",
    "Time to compute embeddings",
    ["model_version"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

EMBEDDING_BATCH_SIZE = Histogram(
    "embedding_batch_size",
    "Number of samples in embedding batch",
    buckets=(1, 10, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
)

MODEL_LOAD_TIME = Histogram(
    "model_load_seconds",
    "Time to load ML model",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# ── Database Metrics ──────────────────────────────────────────────────────────

DB_QUERY_TIME = Histogram(
    "db_query_seconds",
    "Database query execution time",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

DB_CONNECTIONS = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

# ── Application Metrics ───────────────────────────────────────────────────────

RUNS_TOTAL = Gauge(
    "runs_total",
    "Total number of runs in database",
)

VECTOR_INDEX_SIZE = Gauge(
    "vector_index_size",
    "Number of vectors in similarity search index",
)

CELERY_QUEUE_DEPTH = Gauge(
    "celery_queue_depth",
    "Number of tasks in Celery queue",
    ["queue"],
)

# ── Error Metrics ─────────────────────────────────────────────────────────────

ERROR_COUNT = Counter(
    "api_errors_total",
    "Total number of errors",
    ["error_type", "endpoint"],
)

VALIDATION_ERROR_COUNT = Counter(
    "validation_errors_total",
    "Total number of validation errors",
    ["field"],
)


# ── Middleware ────────────────────────────────────────────────────────────────


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track request count, latency, and errors."""
        # Skip metrics endpoint itself to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        # Extract endpoint pattern (remove IDs for aggregation)
        endpoint = self._normalize_endpoint(request.url.path)
        method = request.method

        REQUEST_IN_PROGRESS.inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            status = response.status_code

            # Track request
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(
                time.time() - start_time
            )

            # Track errors
            if status >= 400:
                error_type = "client_error" if status < 500 else "server_error"
                ERROR_COUNT.labels(error_type=error_type, endpoint=endpoint).inc()

            return response

        except Exception as exc:
            # Track unhandled exceptions
            ERROR_COUNT.labels(error_type="exception", endpoint=endpoint).inc()
            raise

        finally:
            REQUEST_IN_PROGRESS.dec()

    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for aggregation (remove UUIDs, IDs)."""
        import re

        # Replace UUIDs with :id
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            ":id",
            path,
            flags=re.IGNORECASE,
        )

        # Replace numeric IDs with :id
        path = re.sub(r"/\d+", "/:id", path)

        return path


# ── Metrics Endpoint ──────────────────────────────────────────────────────────


def get_metrics_response() -> StarletteResponse:
    """
    Generate Prometheus metrics response.

    Returns:
        Response with metrics in Prometheus exposition format
    """
    return StarletteResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Helper Functions ──────────────────────────────────────────────────────────


def track_embedding_computation(duration: float, batch_size: int, model_version: str = "v1"):
    """
    Track embedding computation metrics.

    Args:
        duration: Time taken in seconds
        batch_size: Number of samples in batch
        model_version: Model version identifier
    """
    EMBEDDING_COMPUTE_TIME.labels(model_version=model_version).observe(duration)
    EMBEDDING_BATCH_SIZE.observe(batch_size)


def track_db_query(operation: str, duration: float):
    """
    Track database query metrics.

    Args:
        operation: Type of operation (e.g., "select", "insert", "update")
        duration: Query duration in seconds
    """
    DB_QUERY_TIME.labels(operation=operation).observe(duration)


def update_application_metrics(runs_total: int, vector_index_size: int):
    """
    Update application-level gauges.

    Args:
        runs_total: Total number of runs in database
        vector_index_size: Number of vectors in search index
    """
    RUNS_TOTAL.set(runs_total)
    VECTOR_INDEX_SIZE.set(vector_index_size)
