"""
FastAPI Middleware for request processing.

Includes:
- Request correlation ID generation and propagation
- Request/response logging
- Rate limiting
- Error formatting
"""
from __future__ import annotations
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar
from threading import Lock
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .logger import get_logger

logger = get_logger(__name__)

# Context variable for request correlation ID
# This allows any code in the request chain to access the correlation ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Get the current request's correlation ID.

    Returns empty string if called outside of a request context.
    """
    return request_id_ctx.get()


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates and propagates request correlation IDs.

    The correlation ID is:
    1. Read from X-Request-ID header if present
    2. Generated as a new UUID if not present
    3. Stored in context for logging
    4. Returned in X-Request-ID response header
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Store in context for logging
        token = request_id_ctx.set(request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging.

    Logs:
    - Request method, path, and correlation ID
    - Response status code and timing
    - Excludes health check endpoints to reduce noise
    """

    # Paths to exclude from logging (health checks, metrics)
    EXCLUDE_PATHS = {"/health", "/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip logging for excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        request_id = get_request_id()
        start_time = time.perf_counter()

        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client_ip": request.client.host if request.client else None,
            }
        )

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                },
                exc_info=True,
            )
            raise


def format_error_response(
    status_code: int,
    detail: str,
    errors: list | None = None,
) -> JSONResponse:
    """Format a consistent error response.

    Args:
        status_code: HTTP status code
        detail: Human-readable error summary
        errors: Optional list of detailed error information

    Returns:
        JSONResponse with standard error format
    """
    content = {
        "detail": detail,
        "request_id": get_request_id() or None,
    }

    if errors:
        content["errors"] = errors

    return JSONResponse(status_code=status_code, content=content)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter using sliding window.

    For production, use Redis-backed rate limiting for multi-instance support.
    This implementation is suitable for single-instance deployments.

    Args:
        requests_per_minute: Maximum requests allowed per minute per client
        burst: Additional burst capacity (default: 10)
    """

    def __init__(self, app, requests_per_minute: int = 60, burst: int = 10, window: float = 60.0):
        super().__init__(app)
        self.rate = requests_per_minute
        self.burst = burst
        self.window = window  # Time window in seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

        # Paths exempt from rate limiting
        self.exempt_paths = {"/health", "/health/live", "/health/ready", "/docs", "/redoc", "/openapi.json"}

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Use X-Forwarded-For if behind a proxy, otherwise use client IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_rate_limited(self, client_id: str) -> tuple[bool, int]:
        """Check if client is rate limited.

        Returns:
            (is_limited, remaining_requests)
        """
        now = time.time()
        window_start = now - self.window

        with self._lock:
            # Clean old requests outside the window
            requests = self._requests[client_id]
            requests[:] = [t for t in requests if t > window_start]

            # Check limit (rate + burst)
            max_requests = self.rate + self.burst
            if len(requests) >= max_requests:
                return True, 0

            # Record this request
            requests.append(now)
            remaining = max_requests - len(requests)
            return False, remaining

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_id = self._get_client_id(request)
        is_limited, remaining = self._is_rate_limited(client_id)

        if is_limited:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "client_id": client_id,
                    "path": request.url.path,
                    "request_id": get_request_id(),
                }
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "request_id": get_request_id() or None,
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.rate),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
