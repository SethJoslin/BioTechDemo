from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np


def _to_array(rows: List[dict]) -> np.ndarray:
    """
    Convert a list of dict rows (embedding records) into a 2D numpy array.
    Assumes all numeric columns are embedding dimensions.
    """
    if not rows:
        raise ValueError("No rows provided for embeddings")

    # pick numeric keys from first row
    keys = [k for k, v in rows[0].items() if isinstance(v, (int, float))]
    if not keys:
        raise ValueError("No numeric columns found in embeddings")

    mat = np.array([[float(r[k]) for k in keys] for r in rows], dtype=np.float32)
    return mat


def compute_run_vector(rows: List[dict]) -> np.ndarray:
    """
    Compute a single vector representation for a run from its embeddings.
    Here: simple mean embedding.
    """
    mat = _to_array(rows)
    centroid = mat.mean(axis=0)
    return centroid


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two 1D vectors.
    """
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


class RunSimilarityIndex:
    """
    In-memory similarity index over run-level vectors.

    vectors: dict[run_id -> np.ndarray]
    """

    def __init__(self, vectors: Dict[str, np.ndarray] | None = None) -> None:
        self.vectors: Dict[str, np.ndarray] = vectors or {}

    def upsert(self, run_id: str, vec: np.ndarray) -> None:
        self.vectors[run_id] = vec

    def most_similar(self, run_id: str, k: int = 5) -> List[Tuple[str, float]]:
        if run_id not in self.vectors:
            raise KeyError(f"run_id {run_id!r} not found in similarity index")

        target = self.vectors[run_id]
        sims: List[Tuple[str, float]] = []

        for other_id, vec in self.vectors.items():
            if other_id == run_id:
                continue
            sim = cosine_similarity(target, vec)
            sims.append((other_id, sim))

        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[:k]
