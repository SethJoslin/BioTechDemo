from __future__ import annotations
from pathlib import Path
import scanpy as sc
import pandas as pd

def generate_features(raw_path: str | Path, output_path: Path, n_pcs: int = 50) -> None:
    """Load, preprocess, save PCA features."""
    raw_path = str(raw_path)
    if raw_path.endswith('.h5ad'):
        ad = sc.read_h5ad(raw_path)
    elif raw_path.endswith(('.csv', '.csv.gz')):
        ad = sc.AnnData(pd.read_csv(raw_path, index_col=0))
    elif raw_path.endswith('.parquet'):
        df = pd.read_parquet(raw_path)
        ad = sc.AnnData(df.values, index=df.index, columns=df.columns)
    else:
        raise ValueError(f"Unsupported format: {raw_path}")

    sc.pp.normalize_total(ad, target_sum=1e4)
    sc.pp.log1p(ad)
    sc.pp.highly_variable_genes(ad, n_top_genes=2000, flavor='seurat')
    ad = ad[:, ad.var.highly_variable]
    sc.tl.pca(ad, n_comps=n_pcs, svd_solver='arpack')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pca_df = pd.DataFrame(
        ad.obsm['X_pca'],
        index=ad.obs_names,
        columns=[f'PC{i}' for i in range(n_pcs)]
    )
    pca_df.to_parquet(output_path)