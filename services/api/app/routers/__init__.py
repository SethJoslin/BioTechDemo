"""
API Routers for OpenBioOps.

This module organizes API endpoints into versioned routers.
"""
from .v1 import router as v1_router

__all__ = ["v1_router"]
