"""
Alembic migration environment configuration.

This file is run by Alembic to perform migrations. It imports the
SQLAlchemy models and configures the migration context.

Note: Run Alembic from the services/api directory:
    cd services/api && alembic upgrade head
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure services/api is in the path for imports
# (Alembic runs from services/api, this adds that directory to sys.path)
api_dir = Path(__file__).parent.parent.resolve()
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.db import Base  # noqa: E402
from app.config import settings  # noqa: E402

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy MetaData for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from settings or environment."""
    return os.environ.get("DATABASE_URL", settings.database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
