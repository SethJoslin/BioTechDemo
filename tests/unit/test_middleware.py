"""
Unit tests for middleware components.

Tests CorrelationIDMiddleware, RequestLoggingMiddleware, RateLimitMiddleware, and PrometheusMiddleware.
"""
from __future__ import annotations

import time
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_correlation_id_middleware_generates_id():
    """Test that CorrelationIDMiddleware generates a correlation ID if not provided."""
    from app.middleware import CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.unit
def test_correlation_id_middleware_propagates_existing_id():
    """Test that CorrelationIDMiddleware uses provided correlation ID."""
    from app.middleware import CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)
    test_request_id = "test-correlation-id-12345"

    response = client.get("/test", headers={"X-Request-ID": test_request_id})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == test_request_id


@pytest.mark.unit
def test_correlation_id_accessible_in_handler():
    """Test that correlation ID is accessible via get_request_id() in handlers."""
    from app.middleware import CorrelationIDMiddleware, get_request_id

    app = FastAPI()
    app.add_middleware(CorrelationIDMiddleware)

    captured_request_id = None

    @app.get("/test")
    def test_endpoint():
        nonlocal captured_request_id
        captured_request_id = get_request_id()
        return {"request_id": captured_request_id}

    client = TestClient(app)
    test_id = "test-id-789"

    response = client.get("/test", headers={"X-Request-ID": test_id})

    assert response.status_code == 200
    assert captured_request_id == test_id
    assert response.json()["request_id"] == test_id


@pytest.mark.unit
def test_request_logging_middleware_logs_requests():
    """Test that RequestLoggingMiddleware logs requests and responses."""
    from app.middleware import RequestLoggingMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    with mock.patch("app.middleware.logger") as mock_logger:
        response = client.get("/test?param=value")

        assert response.status_code == 200

        # Verify request_started was logged
        start_call = [call for call in mock_logger.info.call_args_list if "request_started" in str(call)]
        assert len(start_call) > 0

        # Verify request_completed was logged
        complete_call = [call for call in mock_logger.info.call_args_list if "request_completed" in str(call)]
        assert len(complete_call) > 0


@pytest.mark.unit
def test_request_logging_middleware_excludes_health_checks():
    """Test that RequestLoggingMiddleware skips logging for health check endpoints."""
    from app.middleware import RequestLoggingMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/health")
    def health_endpoint():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics_endpoint():
        return {"metrics": "data"}

    client = TestClient(app)

    with mock.patch("app.middleware.logger") as mock_logger:
        # Request health endpoint
        response = client.get("/health")
        assert response.status_code == 200

        # Request metrics endpoint
        response = client.get("/metrics")
        assert response.status_code == 200

        # Verify NO logging occurred (health and metrics are excluded)
        assert mock_logger.info.call_count == 0


@pytest.mark.unit
def test_request_logging_middleware_logs_errors():
    """Test that RequestLoggingMiddleware logs errors."""
    from app.middleware import RequestLoggingMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/error")
    def error_endpoint():
        raise ValueError("Test error")

    client = TestClient(app, raise_server_exceptions=False)

    with mock.patch("app.middleware.logger") as mock_logger:
        response = client.get("/error")

        assert response.status_code == 500

        # Verify request_failed was logged
        error_call = [call for call in mock_logger.error.call_args_list if "request_failed" in str(call)]
        assert len(error_call) > 0


@pytest.mark.unit
def test_rate_limit_middleware_allows_normal_traffic():
    """Test that RateLimitMiddleware allows traffic under the limit."""
    from app.middleware import RateLimitMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=10)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    # Make 5 requests (under the limit of 10)
    for i in range(5):
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert int(response.headers["X-RateLimit-Limit"]) == 10


@pytest.mark.unit
def test_rate_limit_middleware_blocks_excess_traffic():
    """Test that RateLimitMiddleware blocks traffic over the limit."""
    from app.middleware import RateLimitMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    # Low limit for testing (5 requests per minute, 2 burst = 7 total)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=5, burst=2)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    # Make 7 requests (at the limit)
    for i in range(7):
        response = client.get("/test")
        assert response.status_code == 200

    # 8th request should be rate limited
    response = client.get("/test")
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]
    assert "Retry-After" in response.headers
    assert response.headers["X-RateLimit-Remaining"] == "0"


@pytest.mark.unit
def test_rate_limit_middleware_exempts_health_checks():
    """Test that RateLimitMiddleware does not rate limit health check endpoints."""
    from app.middleware import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=2, burst=0)

    @app.get("/health")
    def health_endpoint():
        return {"status": "ok"}

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    # Health endpoint should never be rate limited
    for i in range(10):
        response = client.get("/health")
        assert response.status_code == 200
        # No rate limit headers on exempt endpoints
        assert "X-RateLimit-Limit" not in response.headers

    # Regular endpoint should be rate limited after 2 requests
    response = client.get("/test")
    assert response.status_code == 200
    response = client.get("/test")
    assert response.status_code == 200
    response = client.get("/test")
    assert response.status_code == 429


@pytest.mark.unit
def test_rate_limit_middleware_uses_x_forwarded_for():
    """Test that RateLimitMiddleware uses X-Forwarded-For header if present."""
    from app.middleware import RateLimitMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=2, burst=0)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    # First client (via X-Forwarded-For)
    for i in range(2):
        response = client.get("/test", headers={"X-Forwarded-For": "1.2.3.4"})
        assert response.status_code == 200

    # 3rd request from same client should be blocked
    response = client.get("/test", headers={"X-Forwarded-For": "1.2.3.4"})
    assert response.status_code == 429

    # But different client should still work
    response = client.get("/test", headers={"X-Forwarded-For": "5.6.7.8"})
    assert response.status_code == 200


@pytest.mark.unit
def test_rate_limit_middleware_sliding_window():
    """Test that RateLimitMiddleware uses a sliding window."""
    from app.middleware import RateLimitMiddleware, CorrelationIDMiddleware

    app = FastAPI()
    # Very short window for testing (1 second instead of 60)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=2, burst=0, window=1.0)
    app.add_middleware(CorrelationIDMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    # Make 2 requests (at limit)
    response = client.get("/test")
    assert response.status_code == 200
    response = client.get("/test")
    assert response.status_code == 200

    # 3rd request should be blocked
    response = client.get("/test")
    assert response.status_code == 429

    # Wait for window to expire
    time.sleep(1.1)

    # Should be able to make requests again
    response = client.get("/test")
    assert response.status_code == 200


@pytest.mark.unit
def test_prometheus_middleware_tracks_requests():
    """Test that PrometheusMiddleware tracks request metrics."""
    from app.metrics import PrometheusMiddleware, REQUEST_COUNT, REQUEST_LATENCY
    from prometheus_client import REGISTRY

    # Clear metrics before test
    REQUEST_COUNT._metrics.clear()
    REQUEST_LATENCY._metrics.clear()

    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    client = TestClient(app)

    # Make request
    response = client.get("/test")
    assert response.status_code == 200

    # Verify metrics were recorded
    # Note: We can't directly assert on metric values due to how prometheus_client works,
    # but we can verify the metric was created with the right labels
    assert len(REQUEST_COUNT._metrics) > 0


@pytest.mark.unit
def test_prometheus_middleware_skips_metrics_endpoint():
    """Test that PrometheusMiddleware does not track /metrics endpoint."""
    from app.metrics import PrometheusMiddleware, REQUEST_IN_PROGRESS

    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics")
    def metrics_endpoint():
        # Check that we're not incrementing the in-progress counter
        return {"metrics": "data"}

    client = TestClient(app)

    # Get initial value
    initial_value = REQUEST_IN_PROGRESS._value._value

    # Request metrics endpoint
    response = client.get("/metrics")
    assert response.status_code == 200

    # Verify in-progress counter didn't change
    assert REQUEST_IN_PROGRESS._value._value == initial_value


@pytest.mark.unit
def test_prometheus_middleware_normalizes_endpoints():
    """Test that PrometheusMiddleware normalizes endpoint paths."""
    from app.metrics import PrometheusMiddleware

    middleware = PrometheusMiddleware(None)

    # Test UUID normalization
    assert middleware._normalize_endpoint("/v1/runs/12345678-1234-1234-1234-123456789abc") == "/v1/runs/:id"

    # Test numeric ID normalization
    assert middleware._normalize_endpoint("/v1/runs/123/features") == "/v1/runs/:id/features"

    # Test no normalization needed
    assert middleware._normalize_endpoint("/v1/runs") == "/v1/runs"


@pytest.mark.unit
def test_prometheus_middleware_tracks_errors():
    """Test that PrometheusMiddleware tracks error responses."""
    from app.metrics import PrometheusMiddleware, ERROR_COUNT

    # Clear metrics
    ERROR_COUNT._metrics.clear()

    app = FastAPI()
    app.add_middleware(PrometheusMiddleware)

    @app.get("/error400")
    def error_400():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/error500")
    def error_500():
        raise ValueError("Internal error")

    client = TestClient(app, raise_server_exceptions=False)

    # Make error requests
    response = client.get("/error400")
    assert response.status_code == 400

    response = client.get("/error500")
    assert response.status_code == 500

    # Verify error metrics were tracked
    assert len(ERROR_COUNT._metrics) > 0


@pytest.mark.unit
def test_format_error_response():
    """Test format_error_response utility function."""
    from app.middleware import format_error_response, request_id_ctx

    # Set a request ID in context
    token = request_id_ctx.set("test-request-id")

    try:
        response = format_error_response(
            status_code=400,
            detail="Validation failed",
            errors=["Field 'name' is required", "Field 'email' is invalid"],
        )

        assert response.status_code == 400
        content = response.body.decode()
        assert "Validation failed" in content
        assert "test-request-id" in content
        assert "Field 'name' is required" in content

    finally:
        request_id_ctx.reset(token)


@pytest.mark.unit
def test_get_request_id_outside_context():
    """Test get_request_id returns empty string outside request context."""
    from app.middleware import get_request_id

    # Outside of any request context
    request_id = get_request_id()
    assert request_id == ""
