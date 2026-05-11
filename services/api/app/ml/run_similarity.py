from __future__ import annotations
from typing import Dict, List, Tuple

import numpy as np
import faiss


def _to_array(rows: List[dict]) -> np.ndarray:
    """Convert embedding records to a 2D float32 array."""
    if not rows:
        raise ValueError("No rows provided for embeddings")
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


class RunSimilarityIndex:
    """
    FAISS-backed similarity index over run-level vectors.
    Uses IndexFlatIP (inner product) on L2-normalised vectors,
    which is equivalent to cosine similarity.
    """

    def __init__(self) -> None:
        self._dim: int | None = None
        self._index: faiss.IndexFlatIP | None = None
        self._id_map: List[str] = []          # position → run_id
        self._pos_map: Dict[str, int] = {}    # run_id → position

    def _init_index(self, dim: int) -> None:
        self._dim = dim
        self._index = faiss.IndexFlatIP(dim)

    def upsert(self, run_id: str, vec: np.ndarray) -> None:
        """Add or replace a run vector."""
        vec = vec.astype(np.float32)
        normed = vec.reshape(1, -1).copy()
        faiss.normalize_L2(normed)

        if self._index is None:
            self._init_index(vec.shape[0])

        if run_id in self._pos_map:
            # FAISS FlatIP doesn't support in-place update — rebuild index
            self._id_map[self._pos_map[run_id]] = None  # mark slot deleted
            self._rebuild(run_id, normed[0])
        else:
            self._index.add(normed)
            self._pos_map[run_id] = len(self._id_map)
            self._id_map.append(run_id)

    def _rebuild(self, updated_id: str, updated_vec: np.ndarray) -> None:
        """Rebuild the index after an upsert on an existing run."""
        live_ids = [(pos, rid) for pos, rid in enumerate(self._id_map) if rid is not None]
        old_index = self._index
        self._init_index(self._dim)
        self._id_map = []
        self._pos_map = {}
        for old_pos, rid in live_ids:
            vec = old_index.reconstruct(old_pos).reshape(1, -1).copy()
            if rid == updated_id:
                vec = updated_vec.reshape(1, -1).copy()
            faiss.normalize_L2(vec)
            self._index.add(vec)
            self._pos_map[rid] = len(self._id_map)
            self._id_map.append(rid)

    @property
    def vectors(self) -> Dict[str, np.ndarray]:
        """Expose stored vectors for compatibility with force-flag check in main.py."""
        if self._index is None:
            return {}
        return {
            rid: self._index.reconstruct(pos)
            for rid, pos in self._pos_map.items()
        }

    def most_similar(self, run_id: str, k: int = 5) -> List[Tuple[str, float]]:
        if run_id not in self._pos_map:
            raise KeyError(f"run_id {run_id!r} not in index")

        n_live = len([r for r in self._id_map if r is not None])
        if n_live < 2:
            return []

        # Search for k+1 so we can exclude the query itself
        k_search = min(k + 1, n_live)
        query = self._index.reconstruct(self._pos_map[run_id]).reshape(1, -1).copy()
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
