from abc import ABC, abstractmethod
import numpy as np
from typing import List, Tuple

class VectorStore(ABC):
    @abstractmethod
    def upsert(self, run_id: str, vec: np.ndarray) -> None: ...
    @abstractmethod
    def most_similar(self, run_id: str, k: int = 5) -> List[Tuple[str, float]]: ...
    @abstractmethod
    def __contains__(self, run_id: str) -> bool: ...
