import os
import shutil
import tempfile
from pathlib import Path

import pytest

# ── Session‑scoped temporary directories ─────────────────────────────────
@pytest.fixture(scope="session")
def temp_dirs():
    """Create temporary directories for artifacts, features, and set env vars.
    Must be done before importing the app module so that its globals pick them up.
    """
    tmp_root = tempfile.mkdtemp(prefix="openbioops_test_")
    artifacts_dir = os.path.join(tmp_root, "artifacts_ml")
    features_dir = os.path.join(tmp_root, "artifacts_features")
    os.makedirs(artifacts_dir, exist_ok=True)
    os.makedirs(features_dir, exist_ok=True)

    os.environ["ARTIFACTS_DIR"] = artifacts_dir
    os.environ["FEATURES_DIR"] = features_dir

    repo_root = Path(__file__).resolve().parents[3]  # tests -> api -> services -> biotech
    checkpoint = repo_root / "ml" / "pbmc3k_model.pt"
    if not checkpoint.exists():
        checkpoint = repo_root / "ml" / "model.pt"
    os.environ["MODEL_CHECKPOINT"] = str(checkpoint)

    yield artifacts_dir, features_dir

    # Teardown: clean up the entire tmp_root
    shutil.rmtree(tmp_root, ignore_errors=True)


@pytest.fixture(scope="session")
def app_with_env(temp_dirs):
    """Import the FastAPI app after env vars are set."""
    from app.main import app
    return app


@pytest.fixture()
def client(app_with_env, tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from fastapi.testclient import TestClient
    from app.db import Base, get_db

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

    app_with_env.dependency_overrides[get_db] = override_get_db
    with TestClient(app_with_env) as c:
        yield c
    app_with_env.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client):
    resp = client.post("/token", json={"username": "test-user"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}