#!/usr/bin/env python3
import argparse
import pandas as pd
import numpy as np
import scanpy as sc

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # Minimal loader: accept a CSV or directory with counts; adapt to your pipeline output
    try:
        df = pd.read_csv(args.counts, index_col=0)
    except Exception:
        # fallback: try parquet
        df = pd.read_parquet(args.counts)

    # Basic normalization and HVG selection for demo
    ad = sc.AnnData(df.T)  # cells x genes
    sc.pp.normalize_total(ad, target_sum=1e4)
    sc.pp.log1p(ad)
    sc.pp.highly_variable_genes(ad, n_top_genes=2000, flavor="seurat_v3")
    ad = ad[:, ad.var.highly_variable]
    # compute PCA + UMAP coordinates for visualization
    sc.tl.pca(ad, n_comps=50, svd_solver='arpack')
    sc.pp.neighbors(ad, n_neighbors=10, n_pcs=20)
    sc.tl.umap(ad)

    # Export features and embeddings as parquet
    features = pd.DataFrame(ad.X, index=ad.obs_names, columns=[f"PC{i}" for i in range(ad.X.shape[1])])
    features.to_parquet(args.out)

if __name__ == "__main__":
    main()
