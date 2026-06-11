"""
API v1 Router.

Aggregates all v1 API endpoints.
"""
from fastapi import APIRouter

from .runs import router as runs_router
from .similarity import router as similarity_router
from .auth import router as auth_router
from .workflows import router as workflows_router
from .visualization import router as viz_router
from .model_management import router as models_router
from .model_monitoring import router as monitoring_router
from .batch import router as batch_router
from .analysis import router as analysis_router

router = APIRouter(prefix="/v1")

# Include sub-routers
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(runs_router, prefix="/runs", tags=["runs"])
router.include_router(analysis_router, tags=["analysis"])
router.include_router(similarity_router, prefix="/similarity", tags=["similarity"])
router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
router.include_router(viz_router, prefix="/viz", tags=["visualization"])
router.include_router(models_router, tags=["models"])
router.include_router(monitoring_router, tags=["monitoring"])
router.include_router(batch_router, tags=["batch"])

__all__ = ["router"]