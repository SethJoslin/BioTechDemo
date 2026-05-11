import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
    test_engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    """Get a valid JWT and return headers dict."""
    resp = client.post("/token", json={"username": "test-user"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_token_endpoint(client):
    resp = client.post("/token", json={"username": "seth"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_protected_route_without_token(client):
    resp = client.get("/runs")
    assert resp.status_code == 401


def test_protected_route_with_bad_token(client):
    resp = client.get("/runs", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_create_run(client, auth_headers):
    resp = client.post("/runs", json={"name": "demo-run"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo-run"


def test_list_runs(client, auth_headers):
    client.post("/runs", json={"name": "a"}, headers=auth_headers)
    client.post("/runs", json={"name": "b"}, headers=auth_headers)
    assert len(client.get("/runs", headers=auth_headers).json()) == 2


def test_get_run(client, auth_headers):
    run_id = client.post("/runs", json={"name": "x"}, headers=auth_headers).json()["run_id"]
    r = client.get(f"/runs/{run_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == run_id


def test_get_run_not_found(client, auth_headers):
    import uuid
    assert client.get(f"/runs/{uuid.uuid4()}", headers=auth_headers).status_code == 404


def test_invalid_uuid(client, auth_headers):
    assert client.get("/runs/not-a-uuid", headers=auth_headers).status_code == 400


def test_similarity_before_vector(client, auth_headers):
    run_id = client.post("/runs", json={}, headers=auth_headers).json()["run_id"]
    assert client.get(f"/similarity/{run_id}", headers=auth_headers).status_code == 404
