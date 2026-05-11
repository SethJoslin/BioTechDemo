#!/usr/bin/env python3
"""
Evaluate embedding quality via k-NN label consistency and silhouette score.
Requires embeddings parquet + a metadata CSV with a 'label' column.
"""
import argparse
import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import silhouette_score


def knn_label_accuracy(X: np.ndarray, labels: np.ndarray, k: int = 5) -> float:
    """Fraction of points whose k nearest neighbours share their label."""
    nn = NearestNeighbors(n_neighbors=k + 1).fit(X)
    _, indices = nn.kneighbors(X)
    correct = 0
    for i, nbrs in enumerate(indices):
        nbrs = nbrs[1:]  # exclude self
        correct += np.sum(labels[nbrs] == labels[i])
    return correct / (len(X) * k)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--embeddings", required=True)
    p.add_argument("--metadata", required=True, help="CSV with index + 'label' column")
    p.add_argument("--k", type=int, default=5)
    args = p.parse_args()

    emb_df = pd.read_parquet(args.embeddings)
    meta = pd.read_csv(args.metadata, index_col=0)
    joined = emb_df.join(meta, how="inner")

    X = joined.drop(columns=["label"]).values
    labels = joined["label"].values

    sil = silhouette_score(X, labels, sample_size=min(5000, len(X)))
    knn_acc = knn_label_accuracy(X, labels, k=args.k)

    print(f"Silhouette score : {sil:.4f}  (higher is better, range [-1, 1])")
    print(f"k-NN accuracy    : {knn_acc:.4f}  (k={args.k})")


if __name__ == "__main__":
    main()