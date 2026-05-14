import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from config.settings import Config
from model.database import Base
import model.fase2  # noqa: F401

target_metadata = Base.metadata


def _database_url() -> str:
    configured = os.getenv("DB_ESTADOS_URL", Config.DB_ESTADOS_URL).strip()
    if not configured:
        raise RuntimeError("DB_ESTADOS_URL no puede estar vacia para Alembic")
    return configured


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = context.config.get_section(context.config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
