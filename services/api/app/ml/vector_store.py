"""
Abstract base class for vector similarity stores.

This defines the interface that any similarity index implementation must follow,
enabling easy swapping between FAISS, Pinecone, Milvus, etc.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

import numpy as np


class VectorStore(ABC):
    """
    Abstract base class for vector similarity stores.

    Implementations must provide methods for:
    - Upserting vectors (add or update)
    - Querying for most similar vectors
    - Checking if a vector exists
    """

    @abstractmethod
    def upsert(self, run_id: str, vec: np.ndarray) -> None:
        """
        Add or update a vector in the store.

        Args:
            run_id: Unique identifier for the run
            vec: Vector to store (will be L2-normalized)
        """
        ...

    @abstractmethod
    def most_similar(self, run_id: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Find the k most similar vectors to the given run.

        Args:
            run_id: Run to find similar vectors for
            k: Number of similar vectors to return

        Returns:
            List of (run_id, similarity_score) tuples, sorted by similarity descending

        Raises:
            KeyError: If run_id is not in the store
        """
        ...

    @abstractmethod
    def __contains__(self, run_id: str) -> bool:
        """Check if a run_id exists in the store."""
        ...

    @property
    @abstractmethod
    def vectors(self) -> Dict[str, np.ndarray]:
        """Return all stored vectors as a dict mapping run_id -> vector."""
        ...

    def delete(self, run_id: str) -> bool:
        """
        Delete a vector from the store.

        Args:
            run_id: Run to delete

        Returns:
            True if deleted, False if not found

        Note: Default implementation does nothing. Override in subclasses.
        """
        return False

    def clear(self) -> None:
        """
        Clear all vectors from the store.

        Note: Default implementation does nothing. Override in subclasses.
        """
        pass
