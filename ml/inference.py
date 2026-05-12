#!/usr/bin/env python3
"""
inference.py — load a trained ContrastiveEncoder and produce embeddings
for a given input parquet file.
"""
import argparse

import numpy as np
import pandas as pd
import torch
import sys
sys.path.insert(0, '../lib')
from openbioops.models.contrastive import ContrastiveEncoder, nt_xent_loss


def load_model(
        checkpoint: str, input_dim: int, hidden: int = 256, emb_dim: int = 64
        ) -> ContrastiveEncoder:
    model = ContrastiveEncoder(input_dim=input_dim, hidden=hidden, emb_dim=emb_dim)
    state = torch.load(checkpoint, map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    return model


def run_inference(input_path: str, checkpoint: str, out_path: str, batch_size: int = 512) -> None:
    df = pd.read_parquet(input_path)
    X = torch.tensor(df.values.astype("float32"))

    model = load_model(checkpoint, input_dim=X.shape[1])

    embeddings = []
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            batch = X[i : i + batch_size]  # noqa: E203
            z = model(batch)
            embeddings.append(z.numpy())

    emb = np.concatenate(embeddings, axis=0)
    out_df = pd.DataFrame(emb, index=df.index, columns=[f"emb_{i}" for i in range(emb.shape[1])])
    out_df.to_parquet(out_path)
    print(f"Wrote embeddings {out_df.shape} -> {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run embedding inference on a parquet input")
    p.add_argument("--input", required=True, help="Input features parquet")
    p.add_argument("--checkpoint", required=True, help="Path to model .pt file")
    p.add_argument("--out", required=True, help="Output embeddings parquet")
    p.add_argument("--batch-size", type=int, default=512)
    args = p.parse_args()
    run_inference(args.input, args.checkpoint, args.out, args.batch_size)
