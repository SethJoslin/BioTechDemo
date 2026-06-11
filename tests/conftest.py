"""Shared pytest fixtures for all tests."""
import os
from pathlib import Path
from typing import Generator
import tempfile

# Set testing mode before importing app
os.environ["TESTING"] = "1"

import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.main import app
from app.db import Base, get_db
from app import dependencies


# ── Test Database ────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine."""
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Keep same connection for all threads
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine) -> Generator[Session, None, None]:
    """Create a fresh test database session for each test."""
    SessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    db = SessionLocal()

    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def client(test_engine) -> TestClient:
    """FastAPI test client with test database."""
    # Create a session factory for the test engine
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Reset dependency state for testing
    dependencies.reset_state()

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    app.dependency_overrides.clear()


# ── Authentication ───────────────────────────────────────────────────────────

@pytest.fixture
def auth_token(client: TestClient) -> str:
    """Generate test authentication token."""
    response = client.post("/v1/auth/token", json={"username": "test_user"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ── Sample Data ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_adata():
    """Generate sample AnnData for testing."""
    import scanpy as sc

    n_cells = 100
    n_genes = 200

    # Random count matrix
    X = np.random.poisson(5, size=(n_cells, n_genes)).astype(float)

    # Add MT genes for QC testing
    gene_names = [f"Gene_{i}" for i in range(n_genes - 10)]
    gene_names += [f"MT-{i}" for i in range(10)]  # 10 MT genes

    adata = sc.AnnData(
        X=X,
        obs=pd.DataFrame({"cell_id": [f"cell_{i}" for i in range(n_cells)]}),
        var=pd.DataFrame({"gene_name": gene_names}, index=gene_names)
    )

    return adata


@pytest.fixture
def sample_features() -> pd.DataFrame:
    """Generate sample feature matrix (PCA-like)."""
    n_cells = 100
    n_features = 50

    features = np.random.randn(n_cells, n_features)
    df = pd.DataFrame(
        features,
        index=[f"cell_{i}" for i in range(n_cells)],
        columns=[f"PC{i}" for i in range(n_features)]
    )

    return df


@pytest.fixture
def sample_embeddings() -> pd.DataFrame:
    """Generate sample embeddings."""
    n_cells = 100
    emb_dim = 64

    embeddings = np.random.randn(n_cells, emb_dim)
    df = pd.DataFrame(
        embeddings,
        index=[f"cell_{i}" for i in range(n_cells)],
        columns=[f"emb_{i}" for i in range(emb_dim)]
    )

    return df


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_cellranger_metrics(temp_dir: Path) -> Path:
    """Generate mock Cell Ranger metrics_summary.csv."""
    metrics_path = temp_dir / "metrics_summary.csv"

    metrics_data = {
        "Estimated Number of Cells": ["2,638"],
        "Mean Reads per Cell": ["50,345"],
        "Median Genes per Cell": ["1,234"],
        "Total Genes Detected": ["15,678"],
        "Median UMI Counts per Cell": ["3,456"],
        "Sequencing Saturation": ["87.5%"],
        "Q30 Bases in Barcode": ["95.2%"],
        "Q30 Bases in RNA Read": ["91.3%"],
        "Reads Mapped Confidently to Transcriptome": ["82.4%"],
        "Fraction Reads in Cells": ["78.9%"],
    }

    df = pd.DataFrame(metrics_data)
    df.to_csv(metrics_path, index=False)

    return metrics_path


@pytest.fixture
def sample_h5ad(sample_adata, temp_dir: Path) -> Path:
    """Save sample AnnData as H5AD file."""
    h5ad_path = temp_dir / "sample.h5ad"
    sample_adata.write_h5ad(h5ad_path)
    return h5ad_path


@pytest.fixture
def sample_parquet(sample_features, temp_dir: Path) -> Path:
    """Save sample features as Parquet file."""
    parquet_path = temp_dir / "features.parquet"
    sample_features.to_parquet(parquet_path)
    return parquet_path


# ── Mock Model ───────────────────────────────────────────────────────────────

@pytest.fixture
def mock_model_checkpoint(temp_dir: Path) -> Path:
    """Create a minimal mock model checkpoint for testing."""
    import torch
    from openbioops.models.contrastive import ContrastiveEncoder

    model = ContrastiveEncoder(input_dim=50, hidden=128, emb_dim=64)
    checkpoint_path = temp_dir / "model.pt"
    torch.save(model.state_dict(), checkpoint_path)

    return checkpoint_path


# ── Database Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def sample_run(test_db: Session):
    """Create a sample run in the test database."""
    from app.db import RunModel
    from datetime import datetime
    import uuid

    run = RunModel(
        id=str(uuid.uuid4()),
        name="test_run",
        created_at=datetime.utcnow(),
        metadata={"tissue": "PBMC", "donor": "healthy"},
    )

    test_db.add(run)
    test_db.commit()
    test_db.refresh(run)

    return run


# ── Test Markers ─────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests (slow)")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "requires_model: Requires trained model")
    config.addinivalue_line("markers", "benchmark: Performance benchmarks")
