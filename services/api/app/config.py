from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    jwt_secret: str = "replace-me-in-production"
    model_checkpoint: Path = Path("../ml/model.pt")
    artifacts_dir: Path = Path("artifacts/ml")
    features_dir: Path = Path("artifacts/features")
    redis_url: str = "redis://localhost:6379/0"
    database_path: Path = Path("data/runs.db")

    class Config:
        env_file = ".env"

settings = Settings()
