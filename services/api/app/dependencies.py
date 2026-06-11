"""
FastAPI Dependency Injection for OpenBioOps API.

This module provides dependency providers for shared resources like
the ML model server and similarity index. Using DI instead of global
state enables:
- Easier testing (mock dependencies)
- Better resource management
- Cleaner separation of concerns
- Horizontal scaling support
"""
from __future__ import annotations
import logging
from functools import lru_cache
from typing import Optional

from .config import settings
from .ml import ModelServer, RunSimilarityIndex

logger = logging.getLogger(__name__)


# ── Singleton Containers ───────────────────────────────────────────────────────
# These hold the actual instances. Using a class allows for proper lifecycle
# management and makes testing easier.

class _AppState:
    """Container for application-level singleton state."""

    _model_server: Optional[ModelServer] = None
    _sim_index: Optional[RunSimilarityIndex] = None
    _initialized: bool = False

    @classmethod
    def initialize(cls) -> None:
        """Initialize all singletons. Called during app startup."""
        if cls._initialized:
            return

        # Initialize ModelServer
        try:
            cls._model_server = ModelServer()
            logger.info("ModelServer initialized successfully")
        except Exception as e:
            logger.error(f"ModelServer failed to initialize: {e}")
            cls._model_server = None

        # Initialize SimilarityIndex
        try:
            cls._sim_index = RunSimilarityIndex()
            logger.info("RunSimilarityIndex initialized successfully")
        except Exception as e:
            logger.error(f"RunSimilarityIndex failed to initialize: {e}")
            cls._sim_index = RunSimilarityIndex()  # Use default

        cls._initialized = True

    @classmethod
    def shutdown(cls) -> None:
        """Cleanup resources. Called during app shutdown."""
        cls._model_server = None
        cls._sim_index = None
        cls._initialized = False
        logger.info("AppState cleaned up")

    @classmethod
    def get_model_server(cls) -> Optional[ModelServer]:
        """Get the ModelServer instance."""
        return cls._model_server

    @classmethod
    def get_sim_index(cls) -> RunSimilarityIndex:
        """Get the RunSimilarityIndex instance."""
        if cls._sim_index is None:
            cls._sim_index = RunSimilarityIndex()
        return cls._sim_index

    @classmethod
    def is_ready(cls) -> bool:
        """Check if all required services are ready."""
        return cls._initialized and cls._model_server is not None


# ── FastAPI Dependencies ───────────────────────────────────────────────────────
# These are the actual dependency functions used in route handlers.

def get_model_server() -> Optional[ModelServer]:
    """
    Dependency that provides the ML ModelServer.

    Returns None if the model failed to load, allowing routes to handle
    gracefully (e.g., return 503).

    Usage:
        @app.get("/predict")
        def predict(model: ModelServer = Depends(get_model_server)):
            if model is None:
                raise HTTPException(503, "Model not available")
            return model.predict(...)
    """
    return _AppState.get_model_server()


def get_sim_index() -> RunSimilarityIndex:
    """
    Dependency that provides the similarity search index.

    Usage:
        @app.get("/similar")
        def similar(index: RunSimilarityIndex = Depends(get_sim_index)):
            return index.most_similar(...)
    """
    return _AppState.get_sim_index()


def require_model_server() -> ModelServer:
    """
    Dependency that requires a working ModelServer.

    Raises HTTPException 503 if model is not available.

    Usage:
        @app.post("/embed")
        def embed(model: ModelServer = Depends(require_model_server)):
            return model.embed(...)  # Guaranteed to work
    """
    from fastapi import HTTPException

    server = _AppState.get_model_server()
    if server is None:
        raise HTTPException(
            status_code=503,
            detail="Model server not available. Check logs for initialization errors.",
        )
    return server


# ── Lifecycle Functions ────────────────────────────────────────────────────────
# These are called from main.py's lifespan context manager.

def startup() -> None:
    """Initialize all dependencies on application startup."""
    logger.info("Initializing application dependencies...")
    _AppState.initialize()


def shutdown() -> None:
    """Cleanup all dependencies on application shutdown."""
    logger.info("Shutting down application dependencies...")
    _AppState.shutdown()


# ── Testing Utilities ──────────────────────────────────────────────────────────

def override_model_server(server: Optional[ModelServer]) -> None:
    """Override ModelServer for testing. Pass None to simulate failure."""
    _AppState._model_server = server


def override_sim_index(index: RunSimilarityIndex) -> None:
    """Override SimilarityIndex for testing."""
    _AppState._sim_index = index


def reset_state() -> None:
    """Reset all state. Used in tests."""
    _AppState.shutdown()
