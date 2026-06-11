import os
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch


def get_model_input_dim():
    """Return the number of input features the trained model expects."""
    checkpoint = os.environ.get("MODEL_CHECKPOINT")
    if checkpoint is None:
        repo_root = Path(__file__).resolve().parents[1]
        checkpoint = repo_root / "ml" / "pbmc3k_model.pt"
        if not checkpoint.exists():
            checkpoint = repo_root / "ml" / "model.pt"
        if not checkpoint.exists():
            checkpoint = Path("/app/ml/model.pt")
    else:
        checkpoint = Path(checkpoint)
    state = torch.load(checkpoint, map_location="cpu")
    return state["net.0.weight"].shape[1]


def make_minimal_h5ad(filepath, n_cells=100, n_genes=2000, seed=None):
    """Write a minimal h5ad file for testing the feature extraction pipeline."""
    import anndata as ad
    import pandas as pd
    from scipy.sparse import csr_matrix

    if seed is not None:
        np.random.seed(seed)
    X = np.random.poisson(lam=2, size=(n_cells, n_genes))
    obs = pd.DataFrame(index=[f"cell_{i}" for i in range(n_cells)])
    var = pd.DataFrame(index=[f"gene_{i}" for i in range(n_genes)])
    adata = ad.AnnData(X=csr_matrix(X), obs=obs, var=var)
    adata.write_h5ad(filepath)
    return filepath


def generate_features_offline(raw_h5ad, output_parquet, n_pcs):
    """Call the same feature generation logic that runs in the API."""
    import scanpy as sc
    import pandas as pd

    ad = sc.read_h5ad(raw_h5ad)
    sc.pp.normalize_total(ad, target_sum=1e4)
    sc.pp.log1p(ad)
    sc.pp.highly_variable_genes(ad, n_top_genes=2000, flavor="seurat")
    ad = ad[:, ad.var.highly_variable]
    sc.tl.pca(ad, n_comps=n_pcs, svd_solver="arpack")
    pca_df = pd.DataFrame(
        ad.obsm["X_pca"],
        index=ad.obs_names,
        columns=[f"PC{i}" for i in range(n_pcs)],
    )
    pca_df.to_parquet(output_parquet)
    return output_parquet


def test_compute_vector_with_prebuilt_features(client, auth_headers):
    """Create a run, supply features offline, then compute vector."""
    n_pcs = get_model_input_dim()

    # 1. Create a run
    run_id = client.post("/v1/runs", json={"name": "test-inf"}, headers=auth_headers).json()["id"]

    # 2. Build a features file offline and place it where compute_vector expects
    raw_h5ad = tempfile.mkstemp(suffix=".h5ad")[1]
    make_minimal_h5ad(raw_h5ad, seed=100)
    features_dir = Path(os.environ["FEATURES_DIR"])
    features_path = features_dir / f"{run_id}.parquet"
    generate_features_offline(raw_h5ad, features_path, n_pcs=n_pcs)

    # 3. Compute vector (live inference)
    resp = client.post(f"/v1/runs/{run_id}/compute_vector", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["indexed"] is True
    assert data["vector_len"] == 64


def test_similarity_after_compute_vector(client, auth_headers):
    """Similarity endpoint returns empty list for a single run."""
    n_pcs = get_model_input_dim()

    run_id = client.post("/v1/runs", json={"name": "test-sim"}, headers=auth_headers).json()["id"]
    raw_h5ad = tempfile.mkstemp(suffix=".h5ad")[1]
    make_minimal_h5ad(raw_h5ad, seed=200)
    features_dir = Path(os.environ["FEATURES_DIR"])
    generate_features_offline(raw_h5ad, features_dir / f"{run_id}.parquet", n_pcs=n_pcs)

    client.post(f"/v1/runs/{run_id}/compute_vector", headers=auth_headers)
    resp = client.get(f"/v1/similarity/{run_id}?k=5", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    sims = resp.json()
    assert isinstance(sims, list)
    assert len(sims) == 0  # only one run, self excluded


def test_compute_vector_missing_features(client, auth_headers):
    """Without features, compute_vector gives a clear 404."""
    run_id = client.post("/v1/runs", json={"name": "no-features"}, headers=auth_headers).json()["id"]
    resp = client.post(f"/v1/runs/{run_id}/compute_vector", headers=auth_headers)
    assert resp.status_code == 404, resp.text
    detail = resp.json()["detail"].lower()
    assert "No embedding" in detail or "no feature" in detail or "not found" in detail


def test_similarity_between_two_runs(client, auth_headers):
    """With two runs indexed, similarity returns the nearest neighbour."""
    n_pcs = get_model_input_dim()

    raw1 = tempfile.mkstemp(suffix=".h5ad")[1]
    raw2 = tempfile.mkstemp(suffix=".h5ad")[1]
    make_minimal_h5ad(raw1, seed=300)
    make_minimal_h5ad(raw2, seed=301)
    features_dir = Path(os.environ["FEATURES_DIR"])

    id1 = client.post("/v1/runs", json={"name": "run-A"}, headers=auth_headers).json()["id"]
    id2 = client.post("/v1/runs", json={"name": "run-B"}, headers=auth_headers).json()["id"]

    generate_features_offline(raw1, features_dir / f"{id1}.parquet", n_pcs=n_pcs)
    generate_features_offline(raw2, features_dir / f"{id2}.parquet", n_pcs=n_pcs)

    client.post(f"/v1/runs/{id1}/compute_vector", headers=auth_headers)
    client.post(f"/v1/runs/{id2}/compute_vector", headers=auth_headers)

    similar = client.get(f"/v1/similarity/{id1}?k=1", headers=auth_headers).json()
    assert len(similar) == 1
    assert similar[0]["run_id"] == id2