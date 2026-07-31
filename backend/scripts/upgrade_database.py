"""Upgrade a database without accidentally half-adopting a legacy schema.

Calling Alembic directly against the pre-migration ``games`` table can create an
empty ``alembic_version`` table before revision 0001 fails on ``games`` already
existing.  This wrapper inspects first and refuses that state before Alembic is
allowed to execute any DDL.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
import sqlalchemy as sa  # noqa: E402
from sqlalchemy import inspect, pool  # noqa: E402
from sqlalchemy.engine import Connection  # noqa: E402

from database import SQLALCHEMY_DATABASE_URL  # noqa: E402


DEFAULT_ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"
# A fixed, project-specific signed bigint for pg_advisory_xact_lock().
POSTGRES_MIGRATION_LOCK_ID = 0x434845535341494D


class UpgradeSafetyError(RuntimeError):
    """Raised when automatic upgrade cannot safely identify the DB state."""


def configured_database_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    return (
        os.getenv("MIGRATION_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or SQLALCHEMY_DATABASE_URL
    )


def validate_upgrade_state(connection: Connection) -> None:
    """Allow only a genuinely fresh or already Alembic-managed database."""

    table_names = set(inspect(connection).get_table_names())
    has_version_table = "alembic_version" in table_names

    if not has_version_table:
        if "games" in table_names:
            raise UpgradeSafetyError(
                "Legacy games table exists without Alembic metadata. Back up the "
                "database, run 'make db-adopt' (or scripts/adopt_alembic_baseline.py), "
                "then retry the upgrade."
            )
        if table_names:
            raise UpgradeSafetyError(
                "Database is not empty and has no Alembic metadata; refusing to "
                f"guess its migration state. Existing tables: {sorted(table_names)}"
            )
        return

    version_rows = list(
        connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalars()
    )
    unmanaged_tables = table_names - {"alembic_version"}
    if not version_rows and unmanaged_tables:
        raise UpgradeSafetyError(
            "alembic_version is empty while application tables already exist. "
            "This may be a previous failed direct upgrade; verify the database "
            "before adopting or migrating it."
        )


def acquire_postgres_migration_lock(connection: Connection) -> None:
    """Serialize inspection and migration for the life of the transaction."""

    connection.execute(
        sa.text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": POSTGRES_MIGRATION_LOCK_ID},
    )


def _run_upgrade(connection: Connection, revision: str, config_path: Path) -> None:
    validate_upgrade_state(connection)

    alembic_config = Config(str(config_path))
    # Alembic detects the caller-owned transaction on this supplied connection
    # and does not commit it.  The serialization lock therefore spans both the
    # preflight inspection and all migration DDL.
    alembic_config.attributes["connection"] = connection
    command.upgrade(alembic_config, revision)


def upgrade_database(
    database_url: str | None = None,
    *,
    revision: str = "head",
    config_path: Path = DEFAULT_ALEMBIC_CONFIG,
) -> None:
    resolved_url = configured_database_url(database_url)
    connect_args = {"timeout": 30} if resolved_url.startswith("sqlite") else {}
    engine = sa.create_engine(
        resolved_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
    )

    try:
        if engine.dialect.name == "sqlite":
            with engine.connect() as connection:
                # Acquire SQLite's write reservation before inspecting. Other
                # processes wait (up to the configured 30-second busy timeout),
                # then inspect the post-migration state instead of racing us.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    _run_upgrade(connection, revision, config_path)
                except BaseException:
                    connection.rollback()
                    raise
                else:
                    connection.commit()
        elif engine.dialect.name == "postgresql":
            with engine.begin() as connection:
                acquire_postgres_migration_lock(connection)
                _run_upgrade(connection, revision, config_path)
        else:
            raise UpgradeSafetyError(
                f"Unsupported database dialect {engine.dialect.name!r}; automatic "
                "upgrade locking is implemented only for SQLite and Postgres."
            )
    finally:
        engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely upgrade a fresh or Alembic-managed database."
    )
    parser.add_argument(
        "--database-url",
        help=(
            "Database URL. Defaults to MIGRATION_DATABASE_URL, then DATABASE_URL, "
            "then the backend's normal local SQLite URL."
        ),
    )
    parser.add_argument(
        "--revision",
        default="head",
        help="Alembic revision to upgrade to (default: head).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        upgrade_database(args.database_url, revision=args.revision)
    except UpgradeSafetyError as exc:
        print(f"Refusing automatic database upgrade: {exc}", file=sys.stderr)
        return 2

    print(f"Database upgraded to {args.revision}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
