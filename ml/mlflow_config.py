"""
MLflow configuration for experiment tracking and model registry.

This module provides centralized configuration for MLflow tracking,
ensuring consistent experiment logging across all ML training scripts.
"""
import os
from pathlib import Path
from typing import Optional

import mlflow
from mlflow.tracking import MlflowClient


class MLflowConfig:
    """MLflow configuration manager."""

    def __init__(
        self,
        tracking_uri: Optional[str] = None,
        experiment_name: str = "openbioops-contrastive",
        registry_uri: Optional[str] = None,
    ):
        """Initialize MLflow configuration.

        Args:
            tracking_uri: MLflow tracking server URI. Defaults to env var or local.
            experiment_name: Name of the MLflow experiment.
            registry_uri: Model registry URI. Defaults to tracking_uri.
        """
        default_uri = str(Path.cwd() / "mlruns")
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", default_uri
        )
        self.experiment_name = experiment_name
        self.registry_uri = registry_uri or self.tracking_uri

        # Configure MLflow
        mlflow.set_tracking_uri(self.tracking_uri)
        if self.registry_uri:
            mlflow.set_registry_uri(self.registry_uri)

        # Create experiment if it doesn't exist
        try:
            self.experiment_id = mlflow.create_experiment(self.experiment_name)
        except Exception:
            # Experiment already exists
            self.experiment_id = mlflow.get_experiment_by_name(
                self.experiment_name
            ).experiment_id

        mlflow.set_experiment(self.experiment_name)

    def get_client(self) -> MlflowClient:
        """Get MLflow client for programmatic access."""
        return MlflowClient(tracking_uri=self.tracking_uri)


def log_training_run(
    model,
    config: dict,
    metrics: dict,
    artifacts: Optional[dict] = None,
    tags: Optional[dict] = None,
) -> str:
    """Log a training run to MLflow.

    Args:
        model: Trained PyTorch model
        config: Training configuration (hyperparameters)
        metrics: Training metrics (loss, accuracy, etc.)
        artifacts: Optional dict of artifact paths to log
        tags: Optional tags for the run

    Returns:
        Run ID for the logged experiment
    """
    with mlflow.start_run() as run:
        # Log hyperparameters
        mlflow.log_params(config)

        # Log metrics
        mlflow.log_metrics(metrics)

        # Log tags
        if tags:
            mlflow.set_tags(tags)

        # Log model
        mlflow.pytorch.log_model(
            model,
            "model",
            registered_model_name="contrastive_encoder",
        )

        # Log artifacts (plots, files, etc.)
        if artifacts:
            for name, path in artifacts.items():
                if Path(path).exists():
                    mlflow.log_artifact(path, artifact_path=name)

        return run.info.run_id


def log_metrics_step(metrics: dict, step: int):
    """Log metrics for a specific training step.

    Args:
        metrics: Dict of metric names to values
        step: Training step/epoch number
    """
    mlflow.log_metrics(metrics, step=step)
