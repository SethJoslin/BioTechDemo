import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
    # Spin up a fresh in-memory SQLite DB for each test
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


def test_create_run(client):
    resp = client.post("/runs", json={"name": "demo-run"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo-run"


def test_list_runs(client):
    client.post("/runs", json={"name": "a"})
    client.post("/runs", json={"name": "b"})
    assert len(client.get("/runs").json()) == 2


def test_get_run(client):
    run_id = client.post("/runs", json={"name": "x"}).json()["run_id"]
    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["id"] == run_id


def test_get_run_not_found(client):
    import uuid
    assert client.get(f"/runs/{uuid.uuid4()}").status_code == 404


def test_invalid_uuid(client):
    assert client.get("/runs/not-a-uuid").status_code == 400


def test_similarity_before_vector(client):
    run_id = client.post("/runs", json={}).json()["run_id"]
    assert client.get(f"/similarity/{run_id}").status_code == 404