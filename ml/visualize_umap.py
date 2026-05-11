#!/usr/bin/env python3
import argparse
import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import umap
from sklearn.cluster import KMeans


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--embeddings", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n-clusters", type=int, default=5)
    p.add_argument("--label-col", default=None)
    args = p.parse_args()

    df = pd.read_parquet(args.embeddings)
    X = df.select_dtypes(include=["number"]).values

    reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=42)
    emb = reducer.fit_transform(X)

    if args.label_col and args.label_col in df.columns:
        labels = df[args.label_col].astype("category")
        codes = labels.cat.codes.values
        legend_labels = labels.cat.categories.tolist()
    else:
        km = KMeans(n_clusters=args.n_clusters, random_state=42, n_init="auto")
        codes = km.fit_predict(X)
        legend_labels = [f"Cluster {i}" for i in range(args.n_clusters)]

    cmap = matplotlib.colormaps.get_cmap("tab10").resampled(len(legend_labels))

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(emb[:, 0], emb[:, 1], c=codes, cmap="tab10",
               s=5, alpha=0.8, vmin=0, vmax=len(legend_labels) - 1)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor=cmap(i), markersize=8, label=l)
        for i, l in enumerate(legend_labels)
    ]
    ax.legend(handles=handles, loc="best", fontsize=8, framealpha=0.7)
    ax.set_title("UMAP Embedding")
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()