"""Model server for ML inference with MLflow registry integration."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import pandas as pd

from openbioops.models import ContrastiveEncoder, load_encoder, embed_features
from .model_registry import ModelRegistry
from ..config import settings

DEFAULT_CHECKPOINT = settings.project_root / settings.model_checkpoint


class ModelServer:
    """
    Model server with MLflow registry integration.

    Supports:
    - Loading from local checkpoint (fallback)
    - Loading from MLflow registry by version or stage
    - Hot-swapping models without restart (for A/B testing)
    """

    def __init__(
        self,
        checkpoint: str | Path | None = None,
        use_registry: bool = True,
        model_version: Optional[str] = None,
        model_stage: str = "Production",
    ) -> None:
        """Initialize model server.

        Args:
            checkpoint: Path to local checkpoint (fallback if registry unavailable)
            use_registry: If True, attempt to load from MLflow registry first
            model_version: Specific version to load from registry
            model_stage: Stage to load if version not specified (Production, Staging)
        """
        self.model: ContrastiveEncoder
        self.version_info: Optional[dict] = None
        self.registry = ModelRegistry() if use_registry else None

        # Try loading from registry first
        if use_registry and self.registry:
            try:
                self.model, self.version_info = self._load_from_registry(
                    version=model_version,
                    stage=model_stage
                )
                print(f"✓ Loaded model from MLflow registry: v{self.version_info['version']} ({self.version_info['stage']})")

            except Exception as e:
                print(f" MLflow registry unavailable ({e}), falling back to local checkpoint")
                self.model = self._load_from_checkpoint(checkpoint)
        else:
            self.model = self._load_from_checkpoint(checkpoint)

        # Store dimensions
        self._input_dim = self.model.net[0].in_features
        self.hidden_dim = self.model.net[0].out_features
        self.emb_dim = self.model.net[-1].out_features

    def _load_from_registry(
        self,
        version: Optional[str] = None,
        stage: str = "Production"
    ) -> tuple[ContrastiveEncoder, dict]:
        """Load model from MLflow registry."""
        if not self.registry:
            raise RuntimeError("Registry not initialized")

        model, metadata = self.registry.load_model_from_registry(
            model_name="contrastive_encoder",
            version=version,
            stage=stage,
        )
        return model, metadata

    def _load_from_checkpoint(self, checkpoint: str | Path | None = None) -> ContrastiveEncoder:
        """Load model from local checkpoint."""
        checkpoint = checkpoint or os.environ.get("MODEL_CHECKPOINT", str(DEFAULT_CHECKPOINT))
        ckpt_path = Path(checkpoint)

        if not ckpt_path.exists():
            raise FileNotFoundError(
                f"Model checkpoint not found: {ckpt_path}\n"
                f"Run 'make generate-model' to create it."
            )

        return load_encoder(ckpt_path)

    @property
    def input_dim(self) -> int:
        return self._input_dim

    @property
    def model_version(self) -> Optional[str]:
        """Get current model version from registry metadata."""
        return self.version_info["version"] if self.version_info else None

    def embed(self, feature_path: str | Path, batch_size: int = 512) -> pd.DataFrame:
        """Run inference on a feature parquet and return a DataFrame of embeddings.

        Args:
            feature_path: Path to feature parquet file
            batch_size: Inference batch size

        Returns:
            DataFrame with embedding columns (emb_0, emb_1, ...)
        """
        return embed_features(self.model, feature_path, batch_size=batch_size)

    def reload_from_registry(
        self,
        version: Optional[str] = None,
        stage: str = "Production"
    ) -> bool:
        """
        Hot-swap the model without restarting the server.

        Useful for:
        - Rolling back to a previous version
        - A/B testing different models
        - Deploying model updates without downtime

        Args:
            version: Specific version to load
            stage: Stage to load if version not specified

        Returns:
            True if reload successful, False otherwise
        """
        try:
            new_model, new_metadata = self._load_from_registry(version=version, stage=stage)

            # Atomic swap
            self.model = new_model
            self.version_info = new_metadata

            print(
                f"✓ Model hot-swapped to v{new_metadata['version']} "
                f"(stage={new_metadata['stage']})"
            )
            return True

        except Exception as e:
            print(f"✗ Model reload failed: {e}")
            return False