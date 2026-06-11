# Snowflake Integration

## Setup

```bash
pip install snowflake-connector-python sqlalchemy
```

Set credentials as environment variables (or add to `.env`):

```bash
export SNOWFLAKE_ACCOUNT=yourorg-youraccount
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_WAREHOUSE=COMPUTE_WH
export SNOWFLAKE_DATABASE=OPENBIOOPS
export SNOWFLAKE_SCHEMA=BIOOPS
```

## Apply the schema

```bash
snowsql -a $SNOWFLAKE_ACCOUNT -u $SNOWFLAKE_USER -f snowflake/schema.sql
```

## Sync data

```bash
# Sync all runs from local SQLite
python snowflake/loader.py runs

# Sync QC for a specific run
python snowflake/loader.py qc <run_id> /tmp/pbmc3k_qc/qc_summary.json

# Sync embeddings
python snowflake/loader.py embeddings <run_id> ml/data/pbmc3k_embeddings.parquet

# Sync per-cell QC (batched)
python snowflake/loader.py cell-qc <run_id> /tmp/pbmc3k_qc/cell_qc.parquet
```

## Schema overview

| Table | Description |
|-------|-------------|
| `RUNS` | Run registry — mirrors the API SQLite store |
| `RUN_QC` | Dataset-level QC metrics (mito%, doublets, gene complexity) |
| `CELL_QC` | Per-cell QC metrics, clustered by `RUN_ID` |
| `RUN_EMBEDDINGS` | Mean embedding vector per run, stored as `VARIANT` |
| `PIPELINE_RUNS` | Nextflow/WDL pipeline execution records |
| `RUN_SUMMARY` | View joining all tables for quick dashboarding |
