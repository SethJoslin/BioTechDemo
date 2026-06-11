"""
Serialization utilities for consistent JSON and data handling.

Provides centralized serialization/deserialization to eliminate
duplicate code patterns across the codebase.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


class JSONField:
    """Wrapper for JSON serialization/deserialization of model fields."""

    @staticmethod
    def dumps(data: dict | None) -> str:
        """Serialize dict to JSON string, returning empty object for None."""
        return json.dumps(data or {})

    @staticmethod
    def loads(data: str | None) -> dict:
        """Deserialize JSON string to dict, returning empty dict for None/empty."""
        return json.loads(data or "{}")


class EmbeddingSerializer:
    """Handle embedding JSON/Parquet conversions consistently."""

    @staticmethod
    def save(path: Path, rows: list[dict]) -> None:
        """Save embeddings to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows))

    @staticmethod
    def load(json_path: Path | None, parquet_path: Path | None) -> list[dict]:
        """Load embeddings from JSON or Parquet with automatic fallback.

        Args:
            json_path: Path to JSON file
            parquet_path: Path to Parquet file

        Returns:
            List of embedding dictionaries

        Raises:
            FileNotFoundError: If neither file exists
        """
        if json_path and json_path.exists():
            return json.loads(json_path.read_text())
        elif parquet_path and parquet_path.exists():
            return pd.read_parquet(parquet_path).to_dict(orient="records")
        raise FileNotFoundError("No embedding file found")


class ArtifactLoader:
    """Unified artifact file loading with format detection and fallback."""

    def __init__(self, base_dir: Path, run_id: str):
        """Initialize loader for a specific run.

        Args:
            base_dir: Base directory containing artifacts
            run_id: Run identifier
        """
        self.base_dir = Path(base_dir)
        self.run_id = run_id

    def load_embeddings(self, suffix: str = "") -> list[dict]:
        """Load embeddings with JSON/Parquet fallback.

        Args:
            suffix: Optional suffix (e.g., "_umap")

        Returns:
            List of embedding dictionaries
        """
        name = f"{self.run_id}{suffix}"
        json_path = self.base_dir / f"{name}.json"
        parquet_path = self.base_dir / f"{name}.parquet"
        return EmbeddingSerializer.load(json_path, parquet_path)

    def load_dataframe(self, name: str, formats: list[str] | None = None) -> pd.DataFrame:
        """Load DataFrame trying multiple formats in order.

        Args:
            name: Filename (without extension)
            formats: Formats to try, defaults to ["parquet", "csv", "json"]

        Returns:
            Loaded DataFrame

        Raises:
            FileNotFoundError: If file not found in any format
        """
        formats = formats or ["parquet", "csv", "json"]
        filename_base = f"{self.run_id}_{name}"

        for fmt in formats:
            path = self.base_dir / f"{filename_base}.{fmt}"
            if path.exists():
                if fmt == "parquet":
                    return pd.read_parquet(path)
                elif fmt == "csv":
                    return pd.read_csv(path)
                elif fmt == "json":
                    return pd.read_json(path)

        raise FileNotFoundError(f"No artifact found: {filename_base} (tried: {', '.join(formats)})")

    def load_json(self, name: str, default: Any = None) -> dict:
        """Load JSON file with default fallback.

        Args:
            name: Filename (without extension)
            default: Value to return if file doesn't exist

        Returns:
            Loaded dict or default
        """
        path = self.base_dir / f"{self.run_id}_{name}.json"
        if not path.exists():
            return default or {}
        return json.loads(path.read_text())

    def exists(self, name: str, formats: list[str] | None = None) -> bool:
        """Check if artifact exists in any format.

        Args:
            name: Filename (without extension)
            formats: Formats to check

        Returns:
            True if file exists in any format
        """
        formats = formats or ["parquet", "csv", "json"]
        filename_base = f"{self.run_id}_{name}"

        return any(
            (self.base_dir / f"{filename_base}.{fmt}").exists()
            for fmt in formats
        )
