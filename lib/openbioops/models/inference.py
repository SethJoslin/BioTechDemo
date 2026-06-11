"""Unified model loading and inference utilities."""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .contrastive import ContrastiveEncoder, get_dims_from_checkpoint


def load_encoder(
    checkpoint: str | Path,
    map_location: str = "cpu"
) -> ContrastiveEncoder:
    """Load a trained ContrastiveEncoder from checkpoint.

    Args:
        checkpoint: Path to .pt file
        map_location: torch device mapping (e.g., "cpu", "cuda")

    Returns:
        Loaded encoder in eval mode

    Example:
        >>> model = load_encoder("model.pt")
        >>> embeddings = embed_features(model, "features.parquet")
    """
    state = torch.load(checkpoint, map_location=map_location)
    input_dim, hidden_dim, emb_dim = get_dims_from_checkpoint(state)

    model = ContrastiveEncoder(
        input_dim=input_dim,
        hidden=hidden_dim,
        emb_dim=emb_dim,
    )
    model.load_state_dict(state)
    model.eval()
    return model


def embed_features(
    model: ContrastiveEncoder,
    feature_path: str | Path,
    batch_size: int = 512
) -> pd.DataFrame:
    """Run batch inference on a feature matrix.

    Args:
        model: Trained encoder in eval mode
        feature_path: Path to feature parquet file
        batch_size: Number of samples per batch

    Returns:
        DataFrame with embedding columns (emb_0, emb_1, ...)

    Example:
        >>> model = load_encoder("model.pt")
        >>> df = embed_features(model, "features.parquet", batch_size=256)
        >>> df.shape
        (2638, 64)
    """
    df = pd.read_parquet(feature_path)
    X = torch.tensor(df.values.astype("float32"))

    embeddings = []
    with torch.no_grad():
        for i in range(0, len(X), batch_size):
            batch = X[i:i + batch_size]
            z = model(batch)
            embeddings.append(z.numpy())

    emb = np.concatenate(embeddings, axis=0)
    return pd.DataFrame(
        emb,
        index=df.index,
        columns=[f"emb_{i}" for i in range(emb.shape[1])]
    )
