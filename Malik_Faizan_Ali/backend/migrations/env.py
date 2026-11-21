"""Alembic environment. One linear history shared by both members (DATABASE_SCHEMA.md section 4)."""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import app.models_registry  # noqa: F401  registers every model
from app.core.config import settings
from app.core.database import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

# Dev helper used only when *generating* a migration for a subset of tables.
_ONLY = {t for t in os.environ.get("ALEMBIC_ONLY_TABLES", "").split(",") if t}


def include_object(obj, name, type_, reflected, compare_to):
    if _ONLY and type_ == "table":
        return name in _ONLY
    return True


def _url() -> str:
    # `-x dburl=...` or ALEMBIC_DATABASE_URL override (tests use this), else DATABASE_URL.
    return context.get_x_argument(as_dictionary=True).get("dburl") or os.environ.get("ALEMBIC_DATABASE_URL") or settings.DATABASE_URL


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          include_object=include_object, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
