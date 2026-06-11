"""
Model registry integration for production model management.

This module provides an interface to the MLflow model registry,
allowing the API to fetch, promote, and manage model versions.
"""
from __future__ import annotations

import os
from typing import Optional, List, Dict
from datetime import datetime

from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException

from ..logger import get_logger

logger = get_logger(__name__)


class ModelRegistry:
    """MLflow-backed model registry for production model management."""

    def __init__(self, tracking_uri: Optional[str] = None):
        """Initialize model registry client.

        Args:
            tracking_uri: MLflow tracking server URI
        """
        self.tracking_uri = tracking_uri or os.getenv(
            "MLFLOW_TRACKING_URI", "http://localhost:5000"
        )
        self.client = MlflowClient(tracking_uri=self.tracking_uri)

    def get_production_model(self, model_name: str = "contrastive_encoder") -> Optional[Dict]:
        """Get the current production model version.

        Args:
            model_name: Name of the registered model

        Returns:
            Dict with model version info or None if no production model exists
        """
        try:
            versions = self.client.get_latest_versions(
                name=model_name,
                stages=["Production"]
            )

            if not versions:
                logger.warning(f"No production version found for model '{model_name}'")
                return None

            version = versions[0]
            return {
                "name": version.name,
                "version": version.version,
                "run_id": version.run_id,
                "source": version.source,
                "status": version.status,
                "stage": version.current_stage,
                "creation_timestamp": datetime.fromtimestamp(version.creation_timestamp / 1000),
                "last_updated_timestamp": datetime.fromtimestamp(version.last_updated_timestamp / 1000),
            }

        except MlflowException as e:
            logger.error(f"Error fetching production model: {e}")
            return None

    def get_staging_model(self, model_name: str = "contrastive_encoder") -> Optional[Dict]:
        """Get the current staging model version.

        Args:
            model_name: Name of the registered model

        Returns:
            Dict with model version info or None if no staging model exists
        """
        try:
            versions = self.client.get_latest_versions(
                name=model_name,
                stages=["Staging"]
            )

            if not versions:
                logger.warning(f"No staging version found for model '{model_name}'")
                return None

            version = versions[0]
            return {
                "name": version.name,
                "version": version.version,
                "run_id": version.run_id,
                "source": version.source,
                "status": version.status,
                "stage": version.current_stage,
                "creation_timestamp": datetime.fromtimestamp(version.creation_timestamp / 1000),
                "last_updated_timestamp": datetime.fromtimestamp(version.last_updated_timestamp / 1000),
            }

        except MlflowException as e:
            logger.error(f"Error fetching staging model: {e}")
            return None

    def list_model_versions(
        self,
        model_name: str = "contrastive_encoder",
        max_results: int = 10,
    ) -> List[Dict]:
        """List all versions of a model.

        Args:
            model_name: Name of the registered model
            max_results: Maximum number of versions to return

        Returns:
            List of model version info dicts
        """
        try:
            versions = self.client.search_model_versions(
                f"name='{model_name}'",
                max_results=max_results,
                order_by=["creation_timestamp DESC"]
            )

            return [
                {
                    "name": v.name,
                    "version": v.version,
                    "run_id": v.run_id,
                    "stage": v.current_stage,
                    "status": v.status,
                    "creation_timestamp": datetime.fromtimestamp(v.creation_timestamp / 1000),
                }
                for v in versions
            ]

        except MlflowException as e:
            logger.error(f"Error listing model versions: {e}")
            return []

    def promote_to_production(
        self,
        model_name: str,
        version: str,
        archive_existing: bool = True,
    ) -> bool:
        """Promote a model version to production.

        Args:
            model_name: Name of the registered model
            version: Version number to promote
            archive_existing: Whether to archive existing production version

        Returns:
            True if successful, False otherwise
        """
        try:
            # Archive existing production version if requested
            if archive_existing:
                prod_versions = self.client.get_latest_versions(
                    name=model_name,
                    stages=["Production"]
                )
                for v in prod_versions:
                    self.client.transition_model_version_stage(
                        name=model_name,
                        version=v.version,
                        stage="Archived",
                    )
                    logger.info(f"Archived previous production version {v.version}")

            # Promote new version to production
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Production",
            )

            logger.info(f"Promoted {model_name} version {version} to Production")
            return True

        except MlflowException as e:
            logger.error(f"Error promoting model to production: {e}")
            return False

    def promote_to_staging(
        self,
        model_name: str,
        version: str,
    ) -> bool:
        """Promote a model version to staging.

        Args:
            model_name: Name of the registered model
            version: Version number to promote

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.transition_model_version_stage(
                name=model_name,
                version=version,
                stage="Staging",
            )

            logger.info(f"Promoted {model_name} version {version} to Staging")
            return True

        except MlflowException as e:
            logger.error(f"Error promoting model to staging: {e}")
            return False

    def get_model_by_run_id(self, run_id: str) -> Optional[Dict]:
        """Get model info by MLflow run ID.

        Args:
            run_id: MLflow run ID

        Returns:
            Dict with run info and metrics
        """
        try:
            run = self.client.get_run(run_id)

            return {
                "run_id": run.info.run_id,
                "experiment_id": run.info.experiment_id,
                "status": run.info.status,
                "start_time": datetime.fromtimestamp(run.info.start_time / 1000),
                "end_time": datetime.fromtimestamp(run.info.end_time / 1000) if run.info.end_time else None,
                "params": run.data.params,
                "metrics": run.data.metrics,
                "tags": run.data.tags,
            }

        except MlflowException as e:
            logger.error(f"Error fetching run {run_id}: {e}")
            return None

    def rollback_production(self, model_name: str = "contrastive_encoder") -> Optional[str]:
        """Rollback production to the most recent archived version.

        This is a critical production feature - if a deployed model has issues,
        immediately rollback to the last known-good version.

        Args:
            model_name: Name of the registered model

        Returns:
            Version number that was promoted to production, None if failed

        Example:
            >>> registry = ModelRegistry()
            >>> version = registry.rollback_production()
            >>> print(f"Rolled back to v{version}")
        """
        try:
            # Get current production version
            prod_versions = self.client.get_latest_versions(
                name=model_name,
                stages=["Production"]
            )

            if not prod_versions:
                logger.error("No production version to rollback from")
                return None

            current_prod = prod_versions[0]
            logger.info(f"Current production: v{current_prod.version}")

            # Find most recent archived version (highest version number)
            archived = self.client.get_latest_versions(
                name=model_name,
                stages=["Archived"]
            )

            if not archived:
                logger.error("No archived version available for rollback")
                return None

            # Get the archived version with highest version number
            latest_archived = max(archived, key=lambda v: int(v.version))
            logger.info(f"Rolling back to archived v{latest_archived.version}")

            # Archive current production
            self.client.transition_model_version_stage(
                name=model_name,
                version=current_prod.version,
                stage="Archived",
            )
            logger.info(f"Archived v{current_prod.version} (was Production)")

            # Promote archived version to production
            self.client.transition_model_version_stage(
                name=model_name,
                version=latest_archived.version,
                stage="Production",
            )
            logger.info(f"Promoted v{latest_archived.version} to Production")

            return latest_archived.version

        except MlflowException as e:
            logger.error(f"Rollback failed: {e}")
            return None

    def load_model_from_registry(
        self,
        model_name: str = "contrastive_encoder",
        version: Optional[str] = None,
        stage: str = "Production",
    ):
        """Load PyTorch model from MLflow registry.

        Args:
            model_name: Name of the registered model
            version: Specific version to load. If None, loads from stage.
            stage: Model stage (Production, Staging, Archived, None)

        Returns:
            Tuple of (model, version_info_dict)

        Raises:
            MlflowException: If model not found
        """
        import mlflow.pytorch

        try:
            if version:
                model_uri = f"models:/{model_name}/{version}"
                logger.info(f"Loading {model_name} v{version} from registry")
            else:
                model_uri = f"models:/{model_name}/{stage}"
                logger.info(f"Loading {model_name} from {stage} stage")

            # Load the PyTorch model
            model = mlflow.pytorch.load_model(model_uri)

            # Get version metadata
            if version:
                version_info = self.client.get_model_version(model_name, version)
            else:
                versions = self.client.get_latest_versions(model_name, stages=[stage])
                if not versions:
                    raise MlflowException(f"No {stage} version for {model_name}")
                version_info = versions[0]

            metadata = {
                "name": version_info.name,
                "version": version_info.version,
                "stage": version_info.current_stage,
                "run_id": version_info.run_id,
                "source": version_info.source,
                "status": version_info.status,
            }

            logger.info(
                f"Loaded {model_name} v{metadata['version']} "
                f"(stage={metadata['stage']}, run_id={metadata['run_id'][:8]}...)"
            )

            return model, metadata

        except MlflowException as e:
            logger.error(f"Failed to load model: {e}")
            raise
