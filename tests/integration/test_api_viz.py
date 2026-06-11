"""
Integration tests for visualization API endpoints.

Tests /v1/viz/* endpoints for UMAP, gene expression, and differential expression.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_get_umap_coordinates(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test retrieving UMAP coordinates."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "viz_test_run", "metadata": {}},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock UMAP data
    n_cells = 100
    umap_data = pd.DataFrame({
        "UMAP1": np.random.randn(n_cells),
        "UMAP2": np.random.randn(n_cells),
        "cluster": np.random.randint(0, 5, n_cells),
        "cell_id": [f"cell_{i}" for i in range(n_cells)],
    })

    # Save to artifacts directory
    from app.config import settings
    artifacts_dir = settings.absolute_artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    umap_path = artifacts_dir / f"{run_id}_umap.parquet"
    umap_data.to_parquet(umap_path)

    # Get UMAP coordinates
    response = client.get(f"/v1/viz/{run_id}/umap", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["run_id"] == run_id
    assert data["n_cells"] == n_cells
    assert len(data["coordinates"]) == n_cells
    assert len(data["clusters"]) <= 5
    assert "bounds" in data
    assert all(k in data["bounds"] for k in ["x_min", "x_max", "y_min", "y_max"])

    # Verify coordinate structure
    first_cell = data["coordinates"][0]
    assert "cell_id" in first_cell
    assert "x" in first_cell
    assert "y" in first_cell
    assert "cluster" in first_cell


@pytest.mark.integration
def test_get_umap_coordinates_missing(client: TestClient, auth_headers: dict, test_db):
    """Test UMAP endpoint with missing data."""
    # Create test run without UMAP data
    response = client.post(
        "/v1/runs",
        json={"name": "no_umap_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Try to get UMAP (should fail)
    response = client.get(f"/v1/viz/{run_id}/umap", headers=auth_headers)
    assert response.status_code == 404
    assert "UMAP coordinates not found" in response.json()["detail"]


@pytest.mark.integration
def test_stream_umap_coordinates(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test streaming UMAP coordinates (NDJSON)."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "stream_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock UMAP data
    n_cells = 50
    umap_data = pd.DataFrame({
        "UMAP1": np.random.randn(n_cells),
        "UMAP2": np.random.randn(n_cells),
        "cluster": np.random.randint(0, 3, n_cells),
    })

    # Save to artifacts
    from app.config import settings
    artifacts_dir = settings.absolute_artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    umap_path = artifacts_dir / f"{run_id}_umap.parquet"
    umap_data.to_parquet(umap_path)

    # Stream UMAP coordinates
    response = client.get(f"/v1/viz/{run_id}/umap/stream", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-ndjson"

    # Parse NDJSON response
    lines = [line for line in response.text.splitlines() if line.strip()]
    assert len(lines) == n_cells

    # Verify each line is valid JSON with expected fields
    first_point = json.loads(lines[0])
    assert "x" in first_point
    assert "y" in first_point
    assert "c" in first_point  # cluster
    assert "i" in first_point  # index


@pytest.mark.integration
def test_get_gene_expression(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test retrieving gene expression data."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "expression_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock expression data
    n_cells = 100
    n_genes = 50
    gene_names = [f"Gene_{i}" for i in range(n_genes)] + ["CD4", "CD8A", "IL2RA"]
    expr_data = pd.DataFrame(
        np.random.poisson(5, size=(n_cells, n_genes + 3)),
        columns=gene_names,  # gene_names already includes CD4, CD8A, IL2RA
    )

    # Save to features directory
    from app.config import settings
    features_dir = settings.absolute_features_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    expr_path = features_dir / f"{run_id}.parquet"
    expr_data.to_parquet(expr_path)

    # Get expression for specific gene
    response = client.get(f"/v1/viz/{run_id}/expression/CD4", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["run_id"] == run_id
    assert data["gene"] == "CD4"
    assert data["n_cells"] == n_cells
    assert len(data["expression"]) == n_cells
    assert "min_value" in data
    assert "max_value" in data
    assert "mean_value" in data
    assert data["min_value"] <= data["mean_value"] <= data["max_value"]


@pytest.mark.integration
def test_get_gene_expression_not_found(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test gene expression endpoint with nonexistent gene."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "expression_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock expression data
    expr_data = pd.DataFrame(np.random.randn(50, 20), columns=[f"Gene_{i}" for i in range(20)])

    # Save to features directory
    from app.config import settings
    features_dir = settings.absolute_features_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    expr_path = features_dir / f"{run_id}.parquet"
    expr_data.to_parquet(expr_path)

    # Try to get nonexistent gene
    response = client.get(f"/v1/viz/{run_id}/expression/NOTEXIST", headers=auth_headers)
    assert response.status_code == 404
    assert "Gene 'NOTEXIST' not found" in response.json()["detail"]


@pytest.mark.integration
def test_list_genes(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test listing available genes."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "genes_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock expression data with known genes
    gene_names = ["CD4", "CD8A", "CD8B", "IL2", "IL2RA", "ACTB", "GAPDH"] + [f"Gene_{i}" for i in range(43)]
    expr_data = pd.DataFrame(np.random.randn(50, 50), columns=gene_names)

    # Save to features directory
    from app.config import settings
    features_dir = settings.absolute_features_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    expr_path = features_dir / f"{run_id}.parquet"
    expr_data.to_parquet(expr_path)

    # List all genes
    response = client.get(f"/v1/viz/{run_id}/genes", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["run_id"] == run_id
    assert data["total_genes"] == 50
    assert len(data["genes"]) <= 100  # default limit


@pytest.mark.integration
def test_list_genes_with_search(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test listing genes with search filter."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "search_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock expression data
    gene_names = ["CD4", "CD8A", "CD8B", "IL2", "ACTB", "GAPDH"] + [f"Gene_{i}" for i in range(44)]
    expr_data = pd.DataFrame(np.random.randn(50, 50), columns=gene_names)

    # Save to features directory
    from app.config import settings
    features_dir = settings.absolute_features_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    expr_path = features_dir / f"{run_id}.parquet"
    expr_data.to_parquet(expr_path)

    # Search for "CD" genes
    response = client.get(f"/v1/viz/{run_id}/genes?search=CD", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["total_genes"] == 50
    assert len(data["genes"]) == 3  # CD4, CD8A, CD8B
    assert all("CD" in gene for gene in data["genes"])


@pytest.mark.integration
def test_get_cluster_summary(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test getting cluster summary statistics."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "cluster_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock UMAP data with clusters
    n_cells = 100
    clusters = np.random.randint(0, 4, n_cells)  # 4 clusters
    umap_data = pd.DataFrame({
        "UMAP1": np.random.randn(n_cells),
        "UMAP2": np.random.randn(n_cells),
        "cluster": clusters,
    })

    # Save to artifacts
    from app.config import settings
    artifacts_dir = settings.absolute_artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    umap_path = artifacts_dir / f"{run_id}_umap.parquet"
    umap_data.to_parquet(umap_path)

    # Optionally save cluster metadata
    cluster_metadata = {
        "0": {"markers": ["CD4", "IL7R"], "cell_type": "CD4+ T cell"},
        "1": {"markers": ["CD8A", "CD8B"], "cell_type": "CD8+ T cell"},
        "2": {"markers": ["MS4A1", "CD79A"], "cell_type": "B cell"},
        "3": {"markers": ["LYZ", "CD14"], "cell_type": "Monocyte"},
    }
    cluster_json_path = artifacts_dir / f"{run_id}_clusters.json"
    cluster_json_path.write_text(json.dumps(cluster_metadata))

    # Get cluster summary
    response = client.get(f"/v1/viz/{run_id}/clusters", headers=auth_headers)
    assert response.status_code == 200

    data = response.json()
    assert data["run_id"] == run_id
    assert data["n_clusters"] == 4
    assert len(data["clusters"]) == 4

    # Verify cluster structure
    first_cluster = data["clusters"][0]
    assert "cluster_id" in first_cluster
    assert "n_cells" in first_cluster
    assert "percentage" in first_cluster
    assert "top_markers" in first_cluster
    assert "cell_type" in first_cluster

    # Verify percentages sum to ~100
    total_pct = sum(c["percentage"] for c in data["clusters"])
    assert 99.9 <= total_pct <= 100.1


@pytest.mark.integration
def test_compute_differential_expression(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test differential expression analysis between clusters."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "de_test_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create mock data with 2 distinct clusters
    n_cells = 100
    clusters = np.concatenate([np.zeros(50, dtype=int), np.ones(50, dtype=int)])

    # Create expression data where some genes are differentially expressed
    expr_data = pd.DataFrame({
        "Gene_A": np.concatenate([np.random.normal(10, 2, 50), np.random.normal(5, 2, 50)]),  # Higher in cluster 0
        "Gene_B": np.concatenate([np.random.normal(5, 2, 50), np.random.normal(10, 2, 50)]),  # Higher in cluster 1
        "Gene_C": np.random.normal(7, 2, 100),  # No difference
    })

    umap_data = pd.DataFrame({
        "UMAP1": np.random.randn(n_cells),
        "UMAP2": np.random.randn(n_cells),
        "cluster": clusters,
    })

    # Save data
    from app.config import settings
    features_dir = settings.absolute_features_dir
    artifacts_dir = settings.absolute_artifacts_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    expr_path = features_dir / f"{run_id}.parquet"
    expr_data.to_parquet(expr_path)

    umap_path = artifacts_dir / f"{run_id}_umap.parquet"
    umap_data.to_parquet(umap_path)

    # Compute differential expression
    response = client.post(
        f"/v1/viz/{run_id}/differential?group1=0&group2=1&top_n=10",
        headers=auth_headers,
    )
    assert response.status_code == 200

    data = response.json()
    assert data["run_id"] == run_id
    assert data["group1"] == "0"
    assert data["group2"] == "1"
    assert data["n_genes"] <= 10
    assert len(data["genes"]) == data["n_genes"]

    # Verify gene structure
    if data["genes"]:
        first_gene = data["genes"][0]
        assert "gene" in first_gene
        assert "log_fold_change" in first_gene
        assert "p_value" in first_gene
        assert "adjusted_p_value" in first_gene
        assert "mean_expression_group1" in first_gene
        assert "mean_expression_group2" in first_gene

        # Verify genes are sorted by adjusted p-value
        p_values = [g["adjusted_p_value"] for g in data["genes"]]
        assert p_values == sorted(p_values)


@pytest.mark.integration
def test_differential_expression_invalid_group(client: TestClient, auth_headers: dict, temp_dir: Path, test_db):
    """Test differential expression with invalid group."""
    # Create test run
    response = client.post(
        "/v1/runs",
        json={"name": "de_invalid_run"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    run_id = response.json()["id"]

    # Create minimal data
    expr_data = pd.DataFrame(np.random.randn(50, 10), columns=[f"Gene_{i}" for i in range(10)])
    umap_data = pd.DataFrame({
        "UMAP1": np.random.randn(50),
        "UMAP2": np.random.randn(50),
        "cluster": np.zeros(50, dtype=int),  # Only cluster 0
    })

    # Save data
    from app.config import settings
    features_dir = settings.absolute_features_dir
    artifacts_dir = settings.absolute_artifacts_dir
    features_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    expr_data.to_parquet(features_dir / f"{run_id}.parquet")
    umap_data.to_parquet(artifacts_dir / f"{run_id}_umap.parquet")

    # Try to compare with nonexistent cluster
    response = client.post(
        f"/v1/viz/{run_id}/differential?group1=0&group2=999",
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Group '999' not found" in response.json()["detail"]


@pytest.mark.integration
def test_visualization_requires_auth(client: TestClient, test_db):
    """Test that visualization endpoints require authentication."""
    # Create a run (with auth)
    auth_response = client.post("/v1/auth/token", json={"username": "test_user"})
    token = auth_response.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/v1/runs", json={"name": "auth_test"}, headers=auth_headers)
    run_id = response.json()["id"]

    # Try to access without auth
    endpoints = [
        f"/v1/viz/{run_id}/umap",
        f"/v1/viz/{run_id}/umap/stream",
        f"/v1/viz/{run_id}/expression/CD4",
        f"/v1/viz/{run_id}/genes",
        f"/v1/viz/{run_id}/clusters",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 401, f"Endpoint {endpoint} should require auth"
