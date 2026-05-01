#!/usr/bin/env python3
import argparse
import pandas as pd
import umap
import matplotlib.pyplot as plt

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--embeddings", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    df = pd.read_parquet(args.embeddings)
    X = df.select_dtypes(include=['number']).values
    reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, random_state=0)
    emb = reducer.fit_transform(X)

    plt.figure(figsize=(6,6))
    plt.scatter(emb[:,0], emb[:,1], s=5, alpha=0.8)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(args.out, dpi=150)
    print("Wrote", args.out)

if __name__ == "__main__":
    main()
