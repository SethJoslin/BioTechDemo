"""
Database configuration and models for OpenBioOps API.

Uses SQLAlchemy 2.0 patterns. Database schema is managed by Alembic migrations.
Run `alembic upgrade head` to apply migrations.
"""
from __future__ import annotations
import os
import uuid
from typing import Generator

from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.sql import func

from .config import settings


def get_database_url() -> str:
    """Get database URL from environment or settings."""
    return os.environ.get("DATABASE_URL", settings.database_url)


# Create engine - connection pool settings appropriate for web app
db_url = get_database_url()
is_sqlite = "sqlite" in db_url

# Connection pool configuration (only for non-SQLite databases)
pool_config = {}
if not is_sqlite:
    pool_config = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),  # Core connections
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),  # Extra connections under load
        "pool_recycle": 3600,  # Recycle connections after 1 hour (handles DB connection timeouts)
        "pool_pre_ping": True,  # Verify connections before use
    }

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    **pool_config
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class RunModel(Base):
    """
    Represents a bioinformatics analysis run.

    Stores metadata, QC status, and metrics for each run processed
    through the pipeline.
    """
    __tablename__ = "runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=True, doc="Human-readable run name")
    metadata_ = Column("metadata", Text, default="{}", doc="JSON-encoded run metadata")
    qc_status = Column(String, default="unknown", doc="QC status: unknown, processing, passed, failed")
    qc_metrics_ = Column("qc_metrics", Text, default="{}", doc="JSON-encoded QC metrics")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Timestamp when run was created",
    )

    def __repr__(self) -> str:
        return f"<Run(id={self.id!r}, name={self.name!r}, status={self.qc_status!r})>"


class PredictionLog(Base):
    """
    Logs predictions for model performance monitoring.

    Tracks all predictions made by the model for drift detection,
    performance monitoring, and debugging.
    """
    __tablename__ = "prediction_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=True, doc="Associated run ID")
    model_version = Column(String, nullable=False, doc="Model version used for prediction")
    input_features = Column(Text, nullable=False, doc="JSON-encoded input features")
    prediction = Column(Text, nullable=False, doc="JSON-encoded prediction output")
    confidence = Column(Float, nullable=True, doc="Prediction confidence score (0-1)")
    latency_ms = Column(Float, nullable=False, doc="Inference latency in milliseconds")
    endpoint = Column(String, nullable=False, doc="API endpoint that generated prediction")
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Timestamp when prediction was made",
    )

    def __repr__(self) -> str:
        return f"<PredictionLog(id={self.id!r}, model_version={self.model_version!r})>"


class WorkflowRun(Base):
    """
    Tracks execution of multi-stage analysis workflows.

    Stores state, progress, and timing for Prefect-orchestrated pipelines.
    Enables UI progress tracking and workflow resumption.
    """
    __tablename__ = "workflow_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id = Column(String, ForeignKey("runs.id"), nullable=False, doc="Associated analysis run ID")
    flow_run_id = Column(String, nullable=True, doc="Prefect flow run ID")

    # Overall workflow status
    status = Column(
        String,
        default="pending",
        doc="Workflow status: pending, running, completed, failed, cancelled"
    )

    # Current stage tracking (1-4)
    current_stage = Column(String, nullable=True, doc="Currently executing stage (1, 2, 3, or 4)")

    # Individual stage statuses
    stage_1_status = Column(String, default="pending", doc="Stage 1 status: pending, running, completed, failed")
    stage_2_status = Column(String, default="pending", doc="Stage 2 status")
    stage_3_status = Column(String, default="pending", doc="Stage 3 status")
    stage_4_status = Column(String, default="pending", doc="Stage 4 status")

    # Pipeline parameters (JSON-encoded)
    parameters = Column(Text, default="{}", doc="JSON-encoded pipeline parameters")

    # Stage timing and results (JSON-encoded)
    stage_results = Column(Text, default="{}", doc="JSON-encoded results from each stage")

    # Error tracking
    error_message = Column(Text, nullable=True, doc="Error message if workflow failed")
    failed_stage = Column(String, nullable=True, doc="Stage that caused failure (1-4)")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="When workflow was created"
    )
    started_at = Column(DateTime(timezone=True), nullable=True, doc="When workflow started executing")
    completed_at = Column(DateTime(timezone=True), nullable=True, doc="When workflow finished")

    def __repr__(self) -> str:
        return f"<WorkflowRun(id={self.id!r}, run_id={self.run_id!r}, status={self.status!r})>"


def get_db() -> Generator[Session, None, None]:
    """
    Dependency that provides a database session.

    Yields a session and ensures it's closed after use.
    Use with FastAPI's Depends():

        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.

    NOTE: In production, use Alembic migrations instead:
        alembic upgrade head

    This function is only for development/testing convenience.
    """
    Base.metadata.create_all(bind=engine)