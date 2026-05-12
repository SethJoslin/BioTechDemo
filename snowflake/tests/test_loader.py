"""
Tests for loader.py — uses mocks so no real Snowflake connection needed.
"""
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from loader import sync_runs, sync_qc, sync_embeddings, sync_cell_qc

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture()
def mock_sf():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    with patch("loader.get_connection", return_value=mock_conn):
        yield mock_conn, mock_cur


@pytest.fixture()
def sqlite_db(tmp_path):
    db = tmp_path / "runs.db"
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE runs (
            id TEXT PRIMARY KEY, name TEXT,
            metadata TEXT DEFAULT \'{}\',
            qc_status TEXT DEFAULT \'unknown\',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO runs (id, name, metadata, qc_status) VALUES
        (\'run-aaa\', \'sample-A\', \'{"tissue": "lung"}\', \'pass\'),
        (\'run-bbb\', \'sample-B\', \'{"tissue": "brain"}\', \'unknown\')
    """)
    conn.commit()
    conn.close()
    return str(db)


def test_sync_runs_calls_merge(mock_sf, sqlite_db):
    mock_conn, mock_cur = mock_sf
    count = sync_runs(sqlite_db)
    assert count == 2
    assert mock_cur.execute.call_count == 2
    assert mock_conn.commit.called


def test_sync_runs_empty_db(mock_sf, tmp_path):
    mock_conn, mock_cur = mock_sf
    db = tmp_path / "empty.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE runs "
        "(id TEXT, name TEXT, metadata TEXT, qc_status TEXT, created_at TEXT)"
    )
    conn.commit()
    conn.close()
    count = sync_runs(str(db))
    assert count == 0
    mock_cur.execute.assert_not_called()


def test_sync_qc_calls_merge(mock_sf):
    mock_conn, mock_cur = mock_sf
    summary = {
        "n_cells": 2700, "n_genes": 32738, "n_mt_genes": 13,
        "median_genes_per_cell": 817.0, "median_counts_per_cell": 2197.0,
        "median_pct_mt": 2.03, "cells_high_mt_pct": 1, "cells_low_genes": 0,
        "n_predicted_doublets": 35, "pct_predicted_doublets": 1.3,
        "qc_status": "pass",
    }
    sync_qc("run-aaa", summary)
    assert mock_cur.execute.called
    assert mock_conn.commit.called


def test_sync_qc_missing_optional_fields(mock_sf):
    mock_conn, mock_cur = mock_sf
    summary = {
        "n_cells": 500, "n_genes": 20000, "n_mt_genes": 10,
        "median_genes_per_cell": 600.0, "median_counts_per_cell": 1500.0,
        "median_pct_mt": 3.1, "qc_status": "pass",
    }
    sync_qc("run-bbb", summary)
    assert mock_cur.execute.called


def test_sync_embeddings(mock_sf, tmp_path):
    mock_conn, mock_cur = mock_sf
    df = pd.DataFrame(np.random.randn(50, 64), columns=[f"emb_{i}" for i in range(64)])
    p = tmp_path / "embeddings.parquet"
    df.to_parquet(p)
    sync_embeddings("run-aaa", str(p), model_version="v1")
    assert mock_cur.execute.called
    call_args = mock_cur.execute.call_args[0][1]
    vec = json.loads(call_args[2])
    assert len(vec) == 64


def test_sync_cell_qc_batches(mock_sf, tmp_path):
    mock_conn, mock_cur = mock_sf
    n = 250
    df = pd.DataFrame({
        "n_genes_by_counts": np.random.randint(200, 2000, n),
        "total_counts": np.random.uniform(500, 5000, n),
        "pct_counts_mt": np.random.uniform(0, 5, n),
        "doublet_score": np.random.uniform(0, 0.3, n),
        "predicted_doublet": np.random.choice([True, False], n),
    }, index=[f"CELL_{i}" for i in range(n)])
    p = tmp_path / "cell_qc.parquet"
    df.to_parquet(p)
    total = sync_cell_qc("run-aaa", str(p), batch_size=100)
    assert total == 250
    # 250 cells / batch_size=100 = 3 batches
    assert mock_cur.executemany.call_count == 3
