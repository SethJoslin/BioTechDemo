"""
Authentication endpoints for API v1.
"""
from fastapi import APIRouter, Body

from ...auth import create_access_token

router = APIRouter()


@router.post("/token", summary="Get a demo access token")
def get_token(username: str = Body(..., embed=True)):
    """
    Issues a signed JWT for the given username.

    In production this would validate credentials against a user store.
    For demo purposes, any username is accepted.

    Returns:
        access_token: JWT token for API authentication
        token_type: Token type (always "bearer")
    """
    token = create_access_token(subject=username)
    return {"access_token": token, "token_type": "bearer"}
