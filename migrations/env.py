"""Alembic environment — pulls the DB URL from app settings and the target
metadata from our models (imported so they register on Base.metadata)."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.db.base import Base
from app.db.session import normalize_db_url

# Import every model so all tables register on Base.metadata (single source: app.models.all).
import app.models.all  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if settings.database_url:
    # Same psycopg-3 scheme fix as the app engine — a bare postgres:// URL (Render's raw form)
    # would otherwise make alembic reach for psycopg2 and crash the preDeploy migration.
    config.set_main_option("sqlalchemy.url", normalize_db_url(settings.database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
