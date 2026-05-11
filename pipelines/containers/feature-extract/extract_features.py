#!/usr/bin/env python3
import argparse
import pandas as pd
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
        df = pd.read_parquet(args.counts)

    # Basic normalization and HVG selection for demo
    ad = sc.AnnData(df)  # cells x genes
    sc.pp.normalize_total(ad, target_sum=1e4)
    sc.pp.log1p(ad)
    sc.pp.highly_variable_genes(ad, n_top_genes=2000, flavor="seurat")
    ad = ad[:, ad.var.highly_variable]
    # compute PCA + UMAP coordinates for visualization
    sc.tl.pca(ad, n_comps=50, svd_solver="arpack")
    sc.pp.neighbors(ad, n_neighbors=10, n_pcs=20)
    sc.tl.umap(ad)

    # Export features and embeddings as parquet
    n_pcs = ad.obsm["X_pca"].shape[1]
    pca_df = pd.DataFrame(
        ad.obsm["X_pca"],
        index=ad.obs_names,
        columns=[f"PC{i}" for i in range(n_pcs)],
    )
    pca_df.to_parquet(args.out)
    print(f"Exported {pca_df.shape[0]} cells x {pca_df.shape[1]} PCs -> {args.out}")


if __name__ == "__main__":
    main()
