# services/api/tests/test_runs.py
import json
from fastapi.testclient import TestClient
from app.main import app, DATA_DIR, RUNS_FILE

client = TestClient(app)

def test_create_and_list_run(tmp_path, monkeypatch):
    # isolate data dir
    monkeypatch.setenv("PYTEST_TMPDIR", str(tmp_path))
    # create run
    resp = client.post("/runs", json={"name": "demo-run"})
    assert resp.status_code == 200
    body = resp.json()
    assert "run_id" in body
    run_id = body["run_id"]

    # list runs
    r = client.get("/runs")
    assert r.status_code == 200
    runs = r.json()
    assert any(x["id"] == run_id for x in runs)
