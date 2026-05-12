-- =============================================================================
-- OpenBioOps — Snowflake Schema
-- Database: OPENBIOOPS
-- Schema:   BIOOPS
-- =============================================================================

CREATE DATABASE IF NOT EXISTS OPENBIOOPS;
CREATE SCHEMA IF NOT EXISTS OPENBIOOPS.BIOOPS;

USE SCHEMA OPENBIOOPS.BIOOPS;

-- -----------------------------------------------------------------------------
-- RUNS
-- Core run registry. Mirrors the SQLite runs table in the API service.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RUNS (
    RUN_ID       VARCHAR(36)   NOT NULL PRIMARY KEY,
    NAME         VARCHAR(255),
    METADATA     VARIANT,                              -- arbitrary JSON
    QC_STATUS    VARCHAR(20)   DEFAULT 'unknown',
    CREATED_AT   TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP()
);

-- -----------------------------------------------------------------------------
-- RUN_QC
-- Dataset-level QC summary per run, produced by qc_metrics.py
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RUN_QC (
    QC_ID                    VARCHAR(36)  DEFAULT UUID_STRING() PRIMARY KEY,
    RUN_ID                   VARCHAR(36)  NOT NULL REFERENCES RUNS(RUN_ID),
    N_CELLS                  INTEGER,
    N_GENES                  INTEGER,
    N_MT_GENES               INTEGER,
    MEDIAN_GENES_PER_CELL    FLOAT,
    MEDIAN_COUNTS_PER_CELL   FLOAT,
    MEDIAN_PCT_MT            FLOAT,
    CELLS_HIGH_MT_PCT        INTEGER,
    CELLS_LOW_GENES          INTEGER,
    N_PREDICTED_DOUBLETS     INTEGER,
    PCT_PREDICTED_DOUBLETS   FLOAT,
    QC_STATUS                VARCHAR(20),
    CREATED_AT               TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
);

-- -----------------------------------------------------------------------------
-- CELL_QC
-- Per-cell QC metrics. One row per cell per run.
-- Clustered on RUN_ID for efficient per-run scans.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CELL_QC (
    CELL_BARCODE         VARCHAR(64)   NOT NULL,
    RUN_ID               VARCHAR(36)   NOT NULL REFERENCES RUNS(RUN_ID),
    N_GENES_BY_COUNTS    INTEGER,
    TOTAL_COUNTS         FLOAT,
    PCT_COUNTS_MT        FLOAT,
    DOUBLET_SCORE        FLOAT,
    PREDICTED_DOUBLET    BOOLEAN,
    CREATED_AT           TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY (RUN_ID);

-- -----------------------------------------------------------------------------
-- RUN_EMBEDDINGS
-- Run-level mean embedding vectors produced by inference.py.
-- Vector stored as a JSON array for compatibility; use Snowflake ML
-- vector functions for ANN search in production.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS RUN_EMBEDDINGS (
    RUN_ID          VARCHAR(36)   NOT NULL REFERENCES RUNS(RUN_ID),
    EMBEDDING_DIM   INTEGER,
    EMBEDDING       VARIANT,       -- ARRAY of FLOAT, e.g. [0.12, -0.34, ...]
    MODEL_VERSION   VARCHAR(100),
    CREATED_AT      TIMESTAMP_TZ  DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (RUN_ID, MODEL_VERSION)
);

-- -----------------------------------------------------------------------------
-- PIPELINE_RUNS
-- Nextflow / WDL pipeline execution records.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS PIPELINE_RUNS (
    PIPELINE_RUN_ID  VARCHAR(36)   DEFAULT UUID_STRING() PRIMARY KEY,
    RUN_ID           VARCHAR(36)   REFERENCES RUNS(RUN_ID),
    PIPELINE_NAME    VARCHAR(100),
    PIPELINE_VERSION VARCHAR(50),
    STATUS           VARCHAR(20)   DEFAULT 'pending',
    STARTED_AT       TIMESTAMP_TZ,
    COMPLETED_AT     TIMESTAMP_TZ,
    ERROR_MESSAGE    VARCHAR,
    PARAMS           VARIANT
);

-- -----------------------------------------------------------------------------
-- Useful views
-- -----------------------------------------------------------------------------

CREATE OR REPLACE VIEW RUN_SUMMARY AS
SELECT
    r.RUN_ID,
    r.NAME,
    r.QC_STATUS,
    r.CREATED_AT,
    q.N_CELLS,
    q.N_GENES,
    q.MEDIAN_GENES_PER_CELL,
    q.MEDIAN_PCT_MT,
    q.N_PREDICTED_DOUBLETS,
    e.EMBEDDING_DIM,
    e.MODEL_VERSION
FROM RUNS r
LEFT JOIN RUN_QC q ON r.RUN_ID = q.RUN_ID
LEFT JOIN RUN_EMBEDDINGS e ON r.RUN_ID = e.RUN_ID;
