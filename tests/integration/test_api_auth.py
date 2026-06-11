"""Integration tests for authentication."""
import pytest


@pytest.mark.integration
def test_get_token(client):
    """Test getting authentication token."""
    response = client.post("/v1/auth/token", json={"username": "test_user"})

    assert response.status_code == 200
    data = response.json()

    assert "access_token" in data
    assert "token_type" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


@pytest.mark.integration
def test_get_token_no_username(client):
    """Test getting token without username fails."""
    response = client.post("/v1/auth/token", json={})

    assert response.status_code == 422  # Validation error


@pytest.mark.integration
def test_protected_endpoint_no_token(client):
    """Test accessing protected endpoint without token."""
    response = client.get("/v1/runs")

    assert response.status_code == 401


@pytest.mark.integration
def test_protected_endpoint_invalid_token(client):
    """Test accessing protected endpoint with invalid token."""
    response = client.get(
        "/v1/runs",
        headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status_code == 401


@pytest.mark.integration
def test_protected_endpoint_with_valid_token(client, auth_token):
    """Test accessing protected endpoint with valid token."""
    response = client.get(
        "/v1/runs",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
