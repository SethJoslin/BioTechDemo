"""
Pytest configuration and shared fixtures for OpenBioOps API tests.
"""
import os
from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient

# Set test environment variables BEFORE importing app
os.environ["TESTING"] = "1"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"

# Import app modules
from app.main import app
from app.db import Base, engine, SessionLocal
from app import dependencies


# Ensure tables exist (idempotent - won't recreate if they already exist)
Base.metadata.create_all(bind=engine)


# ── Test Model Fixture Setup ─────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def ensure_test_model():
    """Validate test model fixture exists before running integration tests.

    The model is generated during Docker build and should be at /app/ml/model.pt.
    For local development, run 'make generate-test-model' first.
    """
    from pathlib import Path
    import os

    # Check multiple possible locations
    possible_paths = [
        Path("/app/ml/model.pt"),  # Docker
        Path(os.environ.get("PROJECT_ROOT", "/app")) / "ml" / "model.pt",  # Configurable
    ]

    # Local dev fallback
    try:
        project_root = Path(__file__).resolve().parents[3]
        possible_paths.append(project_root / "ml" / "model.pt")
    except (IndexError, OSError):
        pass

    # Check if model exists at any location
    for model_path in possible_paths:
        if model_path.exists():
            return  # Found it!

    # Model not found - provide clear error
    checked = "\n  ".join(str(p) for p in possible_paths)
    pytest.fail(
        f"Test model fixture not found. Checked:\n  {checked}\n\n"
        f"To fix:\n"
        f"  Docker: Rebuild image with 'docker compose build api'\n"
        f"  Local:  Run 'make generate-test-model'\n"
    )


# ── Database Setup ────────────────────────────────────────────────────────────


@pytest.fixture(scope="function", autouse=True)
def test_db():
    """Clean database before each test."""
    from sqlalchemy import text

    # Clean all data from tables before each test
    session = SessionLocal()
    try:
        # Delete all data from tables in reverse order (to handle foreign keys)
        session.execute(text("DELETE FROM workflow_runs"))
        session.execute(text("DELETE FROM prediction_logs"))
        session.execute(text("DELETE FROM runs"))
        session.commit()
    finally:
        session.close()

    yield


# ── Client Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def client(clean_sim_index):
    """FastAPI test client."""
    # Reset dependencies state for clean test
    dependencies.reset_state()
    dependencies._AppState.initialize()
    dependencies._AppState._sim_index = clean_sim_index

    # TestClient with raise_server_exceptions=True to see full errors
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client

    # Cleanup
    dependencies.reset_state()


@pytest.fixture(scope="function")
def auth_headers(client):
    """
    Generate authentication headers with a valid JWT token.

    Uses the /v1/auth/token endpoint to get a real token.
    """
    response = client.post("/v1/auth/token", json={"username": "testuser"})
    assert response.status_code == 200, f"Auth failed: {response.json()}"

    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Data Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def sample_run(client, auth_headers):
    """Create a sample run for testing."""
    response = client.post(
        "/v1/runs",
        json={"name": "test-run", "metadata": {"source": "pytest"}},
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create run: {response.json()}"
    return response.json()


@pytest.fixture(scope="function")
def temp_dir():
    """Provide a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ── Cleanup Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def clean_sim_index(tmp_path):
    """Reset the similarity index before each test with a fresh temp directory."""
    from app.ml.run_similarity import RunSimilarityIndex

    # Create a fresh index in a temp directory for isolation
    temp_index_dir = tmp_path / "sim_index"
    fresh_index = RunSimilarityIndex(index_dir=temp_index_dir)

    return fresh_index