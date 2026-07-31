from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from database import Base, SQLALCHEMY_DATABASE_URL


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _migration_database_url() -> str:
    """Use a direct migration URL when one is configured.

    Neon and similar hosted Postgres providers expose both pooled and direct
    connections.  Schema migrations should use the direct connection while the
    application remains free to use DATABASE_URL for its normal pooled traffic.
    """

    configured_url = config.attributes.get("migration_database_url")
    if configured_url:
        return str(configured_url)
    return (
        os.getenv("MIGRATION_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or SQLALCHEMY_DATABASE_URL
    )


def _configure_context(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=connection.dialect.name == "sqlite",
        transaction_per_migration=True,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _configure_context(supplied_connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    database_url = _migration_database_url()
    connect_args = {"timeout": 30} if database_url.startswith("sqlite") else {}
    connectable = create_engine(
        database_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            _configure_context(connection)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
