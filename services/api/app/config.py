"""
Centralized configuration for OpenBioOps API.

All settings are loaded from environment variables with sensible defaults.
Use a .env file for local development.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # ── Paths ──────────────────────────────────────────────────────────────────
    project_root: Path = Path(
        os.getenv(
            "PROJECT_ROOT",
            str(Path(__file__).resolve().parents[3] if len(Path(__file__).resolve().parents) > 3 else Path.cwd())
        )
    )
    artifacts_dir: Path = Path("artifacts/ml")
    features_dir: Path = Path("artifacts/features")
    model_checkpoint: Path = Path("ml/model.pt")
    database_url: str = "sqlite:///./data/runs.db"

    # ── Security ───────────────────────────────────────────────────────────────
    # IMPORTANT: MUST set JWT_SECRET environment variable in production
    # Development default is allowed for testing, but production should fail if not set
    jwt_secret: str = "CHANGE-ME-IN-PRODUCTION-dev-only"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret is not using default value in production."""
        # Allow default in development (when DATABASE_URL contains sqlite)
        is_dev = "sqlite" in os.getenv("DATABASE_URL", "sqlite")
        is_default = v == "CHANGE-ME-IN-PRODUCTION-dev-only"

        if is_default and not is_dev:
            raise ValueError(
                "JWT_SECRET must be set via environment variable in production. "
                "Do not use the default value. "
                "Generate a secure secret: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        if len(v) < 32 and not is_dev:
            raise ValueError("JWT_SECRET must be at least 32 characters for production security")

        return v

    # ── CORS ───────────────────────────────────────────────────────────────────
    cors_origins: List[str] = ["http://localhost:3000"]

    # ── Celery ─────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # ── Computed paths ─────────────────────────────────────────────────────────
    @property
    def absolute_artifacts_dir(self) -> Path:
        if self.artifacts_dir.is_absolute():
            return self.artifacts_dir
        return self.project_root / self.artifacts_dir

    @property
    def absolute_features_dir(self) -> Path:
        if self.features_dir.is_absolute():
            return self.features_dir
        return self.project_root / self.features_dir

    @property
    def absolute_model_checkpoint(self) -> Path:
        if self.model_checkpoint.is_absolute():
            return self.model_checkpoint
        return self.project_root / self.model_checkpoint

    def get_feature_path(self, run_id: str) -> Path:
        """Get the feature file path for a run."""
        return self.absolute_features_dir / f"{run_id}.parquet"

    def get_artifact_path(self, run_id: str, extension: str = "parquet") -> Path:
        """Get the artifact file path for a run."""
        return self.absolute_artifacts_dir / f"{run_id}.{extension}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience export
settings = get_settings()
