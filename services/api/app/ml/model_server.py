from __future__ import annotations
import os
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import sys
from pathlib import Path
from openbioops.models.contrastive import ContrastiveEncoder, get_dims_from_checkpoint

DEFAULT_CHECKPOINT = Path(__file__).parents[4] / "ml" / "model.pt"

class ModelServer:
    """Singleton wrapper around the trained contrastive encoder."""

    def __init__(self, checkpoint: str | Path | None = None) -> None:
        checkpoint = checkpoint or os.environ.get("MODEL_CHECKPOINT", str(DEFAULT_CHECKPOINT))
        ckpt_path = Path(checkpoint)
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {ckpt_path}")

        state = torch.load(ckpt_path, map_location="cpu")
        input_dim, hidden_dim, emb_dim = get_dims_from_checkpoint(state) 
        self._input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.emb_dim = emb_dim

        self.model = ContrastiveEncoder(
            input_dim=input_dim,
            hidden=hidden_dim,
            emb_dim=emb_dim,
        )
        self.model.load_state_dict(state)
        self.model.eval()

    @property
    def input_dim(self) -> int:
        return self._input_dim

    def embed(self, feature_path: str | Path, batch_size: int = 512) -> pd.DataFrame:
        """Run inference on a feature parquet and return a DataFrame of embeddings."""
        df = pd.read_parquet(feature_path)
        X = torch.tensor(df.values.astype("float32"))

        embeddings = []
        with torch.no_grad():
            for i in range(0, len(X), batch_size):
                batch = X[i:i + batch_size]
                z = self.model(batch)
                embeddings.append(z.numpy())

        emb = np.concatenate(embeddings, axis=0)
        return pd.DataFrame(emb, index=df.index,
                              columns=[f"emb_{i}" for i in range(emb.shape[1])])