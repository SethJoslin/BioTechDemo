# ============================================================================
# OpenBioOps API Dockerfile
# Multi-stage build for minimal production image
# ============================================================================

# ── Build Stage ──────────────────────────────────────────────────────────────
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install openbioops library
COPY lib /tmp/lib
RUN pip install --no-cache-dir /tmp/lib


# ── Production Stage ─────────────────────────────────────────────────────────
FROM python:3.11-slim as production

# Labels for container metadata
LABEL org.opencontainers.image.title="OpenBioOps API"
LABEL org.opencontainers.image.description="Bioinformatics run management and ML similarity search API"
LABEL org.opencontainers.image.vendor="OpenBioOps"
LABEL org.opencontainers.image.source="https://github.com/SethJoslin/BioTechDemo"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appgroup services/api/app/ ./app/
COPY --chown=appuser:appgroup services/api/alembic/ ./alembic/
COPY --chown=appuser:appgroup services/api/alembic.ini ./

# Create directories for data with proper permissions
RUN mkdir -p /app/data /app/artifacts /app/.numba_cache && \
    chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ── Development Stage ────────────────────────────────────────────────────────
FROM production as development

USER root

# Install development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    httpx \
    ruff \
    mypy

# Copy tests directory for development/testing
COPY --chown=appuser:appgroup ml/ ./ml/
COPY --chown=appuser:appgroup services/api/tests/ ./tests/
COPY --chown=appuser:appgroup services/api/pytest.ini ./

RUN python ml/generate_test_model.py && chown appuser:appgroup /app/ml/model.pt && ls -lah /app/ml/model.pt && echo "Test fixture generated succesfully"

USER appuser

# Enable hot reload for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]