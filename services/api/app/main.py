"""
OpenBioOps API - Bioinformatics run management and similarity search.

This is the main FastAPI application entry point. All business logic
is handled by versioned routers under /v1/*.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .logger import get_logger
from .routers import v1_router
from . import dependencies
from .middleware import (
    CorrelationIDMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware,
    get_request_id,
)
from .metrics import PrometheusMiddleware, get_metrics_response, update_application_metrics

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    logger.info("Starting OpenBioOps API...")
    dependencies.startup()
    yield
    logger.info("Shutting down OpenBioOps API...")
    dependencies.shutdown()


app = FastAPI(
    title="OpenBioOps API",
    description="Bioinformatics run management and similarity search. "
                "Use /v1/auth/token to get a bearer token, then include it "
                "as `Authorization: Bearer <token>` on protected endpoints.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware (order matters - outermost first)
# 1. CORS - must be first for preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 2. Prometheus metrics - track all requests
app.add_middleware(PrometheusMiddleware)
# 3. Rate limiting - protect against abuse
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.rate_limit_requests_per_minute
)
# 4. Correlation ID - for request tracing
app.add_middleware(CorrelationIDMiddleware)
# 5. Logging - log all requests
app.add_middleware(RequestLoggingMiddleware)

# API routers
app.include_router(v1_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions with consistent error response."""
    request_id = get_request_id()
    logger.error(
        "Unhandled exception",
        extra={"request_id": request_id, "path": request.url.path, "error": str(exc)},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id or None},
        headers={"X-Request-ID": request_id} if request_id else {},
    )


# ── Health Checks ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    model_loaded: bool
    index_size: int


class ReadinessResponse(BaseModel):
    """Readiness probe response."""
    ready: bool
    checks: dict


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """Health check for load balancers and monitoring."""
    sim_index = dependencies.get_sim_index()
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        model_loaded=dependencies.get_model_server() is not None,
        index_size=len(sim_index.vectors),
    )


@app.get("/health/live", tags=["health"])
def liveness_probe():
    """Kubernetes liveness probe - is the process running?"""
    return {"status": "alive"}


@app.get("/health/ready", response_model=ReadinessResponse, tags=["health"])
def readiness_probe(db: Session = Depends(get_db)):
    """Kubernetes readiness probe - can we serve traffic?"""
    checks = {
        "database": False,
        "model": False,
        "vector_index": False,
    }

    # Check database connectivity
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    # Check model server availability
    try:
        checks["model"] = dependencies.get_model_server() is not None
    except Exception as e:
        logger.warning(f"Model health check failed: {e}")

    # Check vector index availability
    try:
        sim_index = dependencies.get_sim_index()
        checks["vector_index"] = sim_index is not None
    except Exception as e:
        logger.warning(f"Vector index health check failed: {e}")

    ready = all(checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"ready": ready, "checks": checks},
    )


# ── Metrics Endpoint ──────────────────────────────────────────────────────────


@app.get("/metrics", tags=["observability"])
def metrics_endpoint():
    """
    Prometheus metrics endpoint.

    Returns application metrics in Prometheus exposition format:
    - Request counts, latencies, and error rates
    - ML model inference metrics
    - Database query performance
    - Application state (runs, vector index size)

    This endpoint is typically scraped by Prometheus every 15-30 seconds.
    """
    # Update application-level metrics
    try:
        sim_index = dependencies.get_sim_index()
        update_application_metrics(
            runs_total=0,  # Would query DB in production
            vector_index_size=len(sim_index.vectors),
        )
    except Exception as e:
        logger.warning(f"Failed to update application metrics: {e}")

    return get_metrics_response()