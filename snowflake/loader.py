"""
loader.py — sync OpenBioOps data into Snowflake.

Usage:
    python loader.py runs          # sync all runs from SQLite
    python loader.py qc <run_id>   # sync QC metrics for a run
    python loader.py embeddings <run_id> <parquet_path>

Credentials via environment variables:
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
    SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA
"""
from __future__ import annotations
import json
import os
import sys
from typing import Any

import pandas as pd


from contextlib import contextmanager
import snowflake.connector

@contextmanager
def sf_conn():
    conn = snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "OPENBIOOPS"),
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "BIOOPS"),
    )
    try:
        yield conn
    finally:
        conn.close()

# ── loaders ───────────────────────────────────────────────────────────────────

def sync_runs(sqlite_db: str) -> int:
    """Read all runs from SQLite and upsert into Snowflake RUNS table."""
    from sqlalchemy import create_engine, text
    engine = create_engine(f"sqlite:///{sqlite_db}")
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, name, metadata, qc_status, created_at FROM runs")
            ).fetchall()

    if not rows:
        print("No runs found in SQLite.")
        return 0

    conn_sf = get_connection()
    cur = conn_sf.cursor()
    count = 0
    for run_id, name, metadata, qc_status, created_at in rows:
        _exec(cur, """
            MERGE INTO RUNS t USING (
                SELECT %s AS RUN_ID, %s AS NAME, PARSE_JSON(%s) AS METADATA,
                       %s AS QC_STATUS
            ) s ON t.RUN_ID = s.RUN_ID
            WHEN MATCHED THEN UPDATE SET
                NAME = s.NAME, METADATA = s.METADATA, QC_STATUS = s.QC_STATUS
            WHEN NOT MATCHED THEN INSERT (RUN_ID, NAME, METADATA, QC_STATUS)
                VALUES (s.RUN_ID, s.NAME, s.METADATA, s.QC_STATUS)
        """, (run_id, name, metadata or '{}', qc_status))
        count += 1

    conn_sf.commit()
    cur.close()
    conn_sf.close()
    print(f"Synced {count} runs to Snowflake.")
    return count


def sync_qc(run_id: str, qc_summary: dict) -> None:
    """Upsert QC summary for a run into RUN_QC."""
    conn_sf = get_connection()
    cur = conn_sf.cursor()
    _exec(cur, """
        MERGE INTO RUN_QC t USING (
            SELECT %s AS RUN_ID
        ) s ON t.RUN_ID = s.RUN_ID
        WHEN MATCHED THEN UPDATE SET
            N_CELLS=%s, N_GENES=%s, N_MT_GENES=%s,
            MEDIAN_GENES_PER_CELL=%s, MEDIAN_COUNTS_PER_CELL=%s,
            MEDIAN_PCT_MT=%s, CELLS_HIGH_MT_PCT=%s, CELLS_LOW_GENES=%s,
            N_PREDICTED_DOUBLETS=%s, PCT_PREDICTED_DOUBLETS=%s,
            QC_STATUS=%s
        WHEN NOT MATCHED THEN INSERT (
            RUN_ID, N_CELLS, N_GENES, N_MT_GENES,
            MEDIAN_GENES_PER_CELL, MEDIAN_COUNTS_PER_CELL, MEDIAN_PCT_MT,
            CELLS_HIGH_MT_PCT, CELLS_LOW_GENES,
            N_PREDICTED_DOUBLETS, PCT_PREDICTED_DOUBLETS, QC_STATUS
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        run_id,
        qc_summary.get("n_cells"), qc_summary.get("n_genes"),
        qc_summary.get("n_mt_genes"),
        qc_summary.get("median_genes_per_cell"),
        qc_summary.get("median_counts_per_cell"),
        qc_summary.get("median_pct_mt"),
        qc_summary.get("cells_high_mt_pct", 0),
        qc_summary.get("cells_low_genes", 0),
        qc_summary.get("n_predicted_doublets"),
        qc_summary.get("pct_predicted_doublets"),
        qc_summary.get("qc_status", "unknown"),
        run_id,
        qc_summary.get("n_cells"), qc_summary.get("n_genes"),
        qc_summary.get("n_mt_genes"),
        qc_summary.get("median_genes_per_cell"),
        qc_summary.get("median_counts_per_cell"),
        qc_summary.get("median_pct_mt"),
        qc_summary.get("cells_high_mt_pct", 0),
        qc_summary.get("cells_low_genes", 0),
        qc_summary.get("n_predicted_doublets"),
        qc_summary.get("pct_predicted_doublets"),
        qc_summary.get("qc_status", "unknown"),
    ))
    conn_sf.commit()
    cur.close()
    conn_sf.close()
    print(f"Synced QC for run {run_id}")


def sync_embeddings(run_id: str, parquet_path: str, model_version: str = "v1") -> None:
    """Write mean embedding vector for a run into RUN_EMBEDDINGS."""
    df = pd.read_parquet(parquet_path)
    mean_vec = df.mean(axis=0).tolist()
    vec_str = ', '.join(str(v) for v in mean_vec)
    with sf_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO RUN_EMBEDDINGS (RUN_ID, EMBEDDING_DIM, EMBEDDING, MODEL_VERSION)
            VALUES (%s, %s, ARRAY[{}], %s)
        """.format(vec_str), (run_id, len(mean_vec), model_version))
        conn.commit()


def sync_cell_qc(run_id: str, cell_qc_parquet: str, batch_size: int = 5000) -> None:
    """Batch-insert per-cell QC metrics into CELL_QC."""
    df = pd.read_parquet(cell_qc_parquet)
    df['RUN_ID'] = run_id
    with sf_conn() as conn:
        from snowflake.connector.pandas_tools import write_pandas
        success, nchunks, nrows, _ = write_pandas(
            conn, df, "CELL_QC", quote_identifiers=False,
            chunk_size=batch_size, auto_create_table=False
        )
        print(f"Synced {nrows} rows to CELL_QC")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None

    if cmd == "runs":
        db = sys.argv[2] if len(sys.argv) > 2 else "services/api/app/data/runs.db"
        sync_runs(db)

    elif cmd == "qc":
        run_id = sys.argv[2]
        qc_json = sys.argv[3]
        with open(qc_json) as f:
            summary = json.load(f)
        sync_qc(run_id, summary)

    elif cmd == "embeddings":
        run_id, parquet = sys.argv[2], sys.argv[3]
        version = sys.argv[4] if len(sys.argv) > 4 else "v1"
        sync_embeddings(run_id, parquet, version)

    elif cmd == "cell-qc":
        run_id, parquet = sys.argv[2], sys.argv[3]
        sync_cell_qc(run_id, parquet)

    else:
        print(__doc__)
        sys.exit(1)
