from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np

from .vector_store import VectorStore

logger = logging.getLogger(__name__)


def _to_array(rows: List[dict]) -> np.ndarray:
    """Convert embedding records to a 2D float32 array."""
    if not rows:
        raise ValueError("No rows provided for embeddings")
    if not isinstance(rows, list):
        raise TypeError(f"Expected list of dicts, got {type(rows).__name__}")
    if not isinstance(rows[0], dict):
        raise TypeError(f"Expected list of dicts, got list of {type(rows[0]).__name__}")
    keys = sorted(k for k, v in rows[0].items() if isinstance(v, (int, float)))
    if not keys:
        raise ValueError("No numeric columns found in embeddings")
    return np.array([[float(r[k]) for k in keys] for r in rows], dtype=np.float32)


def compute_run_vector(rows: List[dict]) -> np.ndarray:
    """Mean-pool embedding rows into a single L2-normalised run vector."""
    mat = _to_array(rows)
    centroid = mat.mean(axis=0, keepdims=True).astype(np.float32)
    faiss.normalize_L2(centroid)
    return centroid[0]


class RunSimilarityIndex(VectorStore):
    """
    FAISS-backed cosine similarity index with disk persistence.

    Implements the VectorStore interface using FAISS IndexFlatIP for
    efficient inner product (cosine) similarity search.

    Persists two files:
      <index_dir>/faiss.index   — the FAISS binary index
      <index_dir>/id_map.json   — ordered list of run_ids matching FAISS positions
    """

    DEFAULT_DIR = Path(__file__).parents[2] / "data" / "sim_index"

    def __init__(self, index_dir: Optional[Path] = None) -> None:
        self._dir = Path(index_dir or self.DEFAULT_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "faiss.index"
        self._map_path = self._dir / "id_map.json"
        self._vectors_path = self._dir / "vectors.npz"
        self._dim: Optional[int] = None
        self._index: Optional[faiss.IndexIDMap] = None
        self._id_map: List[Optional[str]] = []
        self._pos_map: Dict[str, int] = {}
        self._vectors_cache: Dict[str, np.ndarray] = {}

        self._load()

    # ── persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self._index is None:
            return
        faiss.write_index(self._index, str(self._index_path))
        self._map_path.write_text(json.dumps(self._id_map))
        if self._vectors_cache:
            np.savez(str(self._vectors_path), **self._vectors_cache)

    def _load(self) -> None:
        if not self._index_path.exists() or not self._map_path.exists():
            return
        try:
            self._index = faiss.read_index(str(self._index_path))
            self._dim = self._index.d
            self._id_map = json.loads(self._map_path.read_text())
            self._pos_map = {
                rid: pos
                for pos, rid in enumerate(self._id_map)
                if rid is not None
            }
            if self._vectors_path.exists():
                vectors_data = np.load(str(self._vectors_path))
                self._vectors_cache = {key: vectors_data[key] for key in vectors_data.files}
        except Exception as e:
            logger.warning(f"Warning: could not load FAISS index from disk: {e}")

    # ── index operations ──────────────────────────────────────────────────────

    def _init_index(self, dim: int) -> None:
        self._dim = dim
        base_index = faiss.IndexFlatIP(dim)
        self._index = faiss.IndexIDMap(base_index)

    def upsert(self, run_id: str, vec: np.ndarray) -> None:
        """Add or replace a run vector, then persist to disk."""
        vec = vec.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(vec)
        if self._index is None:
            self._init_index(vec.shape[1])
        elif self._dim != vec.shape[1]:
            # Dimension mismatch - reinitialize index
            logger.warning(f"Dimension mismatch: index has {self._dim}, vector has {vec.shape[1]}. Reinitializing index.")
            self._init_index(vec.shape[1])
            self._id_map = []
            self._pos_map = {}
            self._vectors_cache = {}
        if run_id in self._pos_map:
            idx = self._pos_map[run_id]
            self._index.remove_ids(np.array([idx]))
            self._index.add_with_ids(vec, np.array([idx]))
        else:
            new_idx = self._index.ntotal  # FAISS adds sequentially
            self._index.add_with_ids(vec, np.array([new_idx]))
            self._pos_map[run_id] = new_idx
            self._id_map.append(run_id)
        self._vectors_cache[run_id] = vec[0].copy()
        self._save()

    def __contains__(self, run_id: str) -> bool:
        return run_id in self._pos_map

    def _rebuild(self, updated_id: str, updated_vec: np.ndarray) -> None:
        live = [(pos, rid) for pos, rid in enumerate(self._id_map) if rid is not None]
        old_index = self._index
        self._init_index(self._dim)
        self._id_map = []
        self._pos_map = {}
        for old_pos, rid in live:
            vec = old_index.reconstruct(old_pos).reshape(1, -1).copy()
            if rid == updated_id:
                vec = updated_vec.reshape(1, -1).copy()
            faiss.normalize_L2(vec)
            self._index.add(vec)
            self._pos_map[rid] = len(self._id_map)
            self._id_map.append(rid)

    @property
    def vectors(self) -> Dict[str, np.ndarray]:
        """Expose stored vectors for force-flag check in main.py."""
        return self._vectors_cache

    def most_similar(self, run_id: str, k: int = 5) -> List[Tuple[str, float]]:
        if run_id not in self._pos_map:
            raise KeyError(f"run_id {run_id!r} not in index")

        n_live = sum(1 for r in self._id_map if r is not None)
        if n_live < 2:
            return []

        k_search = min(k + 1, n_live)
        query = self._vectors_cache[run_id].reshape(1,-1).copy()
        faiss.normalize_L2(query)

        scores, positions = self._index.search(query, k_search)

        results = []
        for score, pos in zip(scores[0], positions[0]):
            if pos < 0:
                continue
            rid = self._id_map[pos]
            if rid is None or rid == run_id:
                continue
            results.append((rid, float(score)))

        return results[:k]
