from __future__ import annotations
import uuid
from pathlib import Path

from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.sql import func

DB_PATH = Path(__file__).parent / "data" / "runs.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class RunModel(Base):
    __tablename__ = "runs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=True)
    metadata_ = Column("metadata", Text, default="{}")
    qc_status = Column(String, default="unknown")
    qc_metrics_ = Column("qc_metrics", Text, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
