"""
Shared Pydantic schemas for request/response validation.

This module contains:
- Error response models for consistent API error formatting
- Common validators and types
- Shared response models
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── Error Response Models ─────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Details about an error for debugging."""
    field: Optional[str] = Field(None, description="Field that caused the error, if applicable")
    message: str = Field(..., description="Human-readable error message")
    code: Optional[str] = Field(None, description="Machine-readable error code")


class ErrorResponse(BaseModel):
    """Standard error response format.

    All API errors return this format for consistency.
    """
    detail: str = Field(..., description="Human-readable error summary")
    errors: Optional[list[ErrorDetail]] = Field(
        None, description="Detailed error information for validation errors"
    )
    request_id: Optional[str] = Field(
        None, description="Request correlation ID for debugging"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Validation error",
                "errors": [
                    {"field": "run_id", "message": "Invalid UUID format", "code": "invalid_uuid"}
                ],
                "request_id": "abc123"
            }
        }


class ValidationErrorResponse(ErrorResponse):
    """Response for 422 validation errors."""
    detail: str = "Validation error"


class NotFoundErrorResponse(ErrorResponse):
    """Response for 404 not found errors."""
    detail: str = "Resource not found"


class ServiceUnavailableResponse(ErrorResponse):
    """Response for 503 service unavailable errors."""
    detail: str = "Service temporarily unavailable"


# ── Common Validators ─────────────────────────────────────────────────────────

class UUIDStr(str):
    """String that must be a valid UUID.

    Usage:
        run_id: UUIDStr = Path(...)
    """
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> str:
        if isinstance(v, str):
            try:
                UUID(v)
                return v
            except ValueError:
                raise ValueError("Invalid UUID format")
        raise ValueError("String required")


# ── Pagination Models ─────────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    """Standard pagination parameters."""
    offset: int = Field(0, ge=0, description="Number of items to skip")
    limit: int = Field(50, ge=1, le=200, description="Maximum items to return")


class PaginatedResponse(BaseModel):
    """Base model for paginated responses."""
    total: int = Field(..., description="Total number of items")
    offset: int = Field(..., description="Current offset")
    limit: int = Field(..., description="Current limit")


# ── Common Response Models ────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    """Simple status response."""
    status: str = Field(..., description="Status string")
    message: Optional[str] = Field(None, description="Optional message")


class TimestampMixin(BaseModel):
    """Mixin for models with timestamps."""
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


# ── OpenAPI Response Examples ─────────────────────────────────────────────────
# These are used for generating better API documentation

COMMON_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad Request - Invalid input"},
    401: {"model": ErrorResponse, "description": "Unauthorized - Invalid or missing token"},
    403: {"model": ErrorResponse, "description": "Forbidden - Insufficient permissions"},
    404: {"model": NotFoundErrorResponse, "description": "Not Found - Resource doesn't exist"},
    422: {"model": ValidationErrorResponse, "description": "Validation Error"},
    500: {"model": ErrorResponse, "description": "Internal Server Error"},
    503: {"model": ServiceUnavailableResponse, "description": "Service Unavailable"},
}
