"""Safely adopt a database created by the legacy ``create_all`` startup.

The script validates the complete legacy schema before stamping revision 0001.
It never runs migrations and never guesses that a similar-looking schema is
compatible. Run ``scripts/upgrade_database.py`` as a separate, explicit step
after a successful stamp.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Type

from alembic import command
from alembic.config import Config
import sqlalchemy as sa
from sqlalchemy import inspect, pool
from sqlalchemy.engine import Connection


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"
BASELINE_REVISION = "0001_games_baseline"


class AdoptionError(RuntimeError):
    """Raised when an existing database is not the exact legacy baseline."""


EXPECTED_COLUMNS: dict[str, tuple[Type[sa.types.TypeEngine], bool]] = {
    "id": (sa.Integer, False),
    "date": (sa.DateTime, True),
    "player_white": (sa.String, True),
    "player_black": (sa.String, True),
    "result": (sa.String, True),
    "pgn": (sa.Text, True),
    "fen": (sa.String, True),
}


def configured_database_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url

    database_url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise AdoptionError(
            "Set MIGRATION_DATABASE_URL (preferred) or DATABASE_URL explicitly; "
            "refusing to stamp the default local games.db by accident."
        )
    return database_url


def _type_matches(actual_type: sa.types.TypeEngine, expected_type: type) -> bool:
    if not isinstance(actual_type, expected_type):
        return False

    if expected_type is sa.String and not isinstance(actual_type, sa.Text):
        return getattr(actual_type, "length", None) is None
    if expected_type is sa.DateTime:
        return not bool(getattr(actual_type, "timezone", False))
    return True


def postgres_id_is_generated(column: dict) -> bool:
    """Return whether a reflected Postgres id has sequence/identity generation.

    SQLAlchemy reflects ``SERIAL`` as a ``nextval(...)`` default and modern
    identity columns through the ``identity`` mapping.  An INTEGER primary key
    without either property does not satisfy the ORM's implicit-id contract.
    """

    if column.get("identity") is not None:
        return True

    default = column.get("default")
    return bool(
        isinstance(default, str)
        and re.match(r"^\s*nextval\s*\(", default, flags=re.IGNORECASE)
    )


def _validate_sqlite_generated_id(connection: Connection, column: dict) -> None:
    pragma_columns = {
        row["name"]: row
        for row in connection.exec_driver_sql("PRAGMA table_info('games')").mappings()
    }
    declared_id = pragma_columns.get("id")
    declared_type = str((declared_id or {}).get("type") or "").strip().upper()

    # SQLite only aliases a single-column primary key to rowid when its declared
    # type name is exactly INTEGER.  INT has the same reflected SQLAlchemy type
    # affinity but does not auto-generate an omitted id.
    if declared_type != "INTEGER":
        raise AdoptionError(
            "SQLite games.id must be declared exactly INTEGER to be a rowid alias; "
            f"got {declared_type or '<empty>'}."
        )
    if column.get("default") is not None:
        raise AdoptionError("SQLite games.id must not define a database default.")

    table_sql = connection.scalar(
        sa.text(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'games'"
        )
    )
    if not isinstance(table_sql, str) or re.search(
        r"\bWITHOUT\s+ROWID\b",
        table_sql,
        flags=re.IGNORECASE,
    ):
        raise AdoptionError("SQLite games must be a rowid table.")

    # A true INTEGER PRIMARY KEY rowid alias has no separate primary-key index.
    # This also rejects the historical SQLite edge case PRIMARY KEY DESC.
    index_rows = connection.exec_driver_sql("PRAGMA index_list('games')").mappings()
    if any(row.get("origin") == "pk" for row in index_rows):
        raise AdoptionError(
            "SQLite games.id primary key is not an auto-generated rowid alias."
        )


def _validate_generated_id(connection: Connection, column: dict) -> None:
    dialect_name = connection.dialect.name
    if dialect_name == "sqlite":
        _validate_sqlite_generated_id(connection, column)
        return
    if dialect_name == "postgresql":
        if not postgres_id_is_generated(column):
            raise AdoptionError(
                "Postgres games.id must use SERIAL/sequence or IDENTITY generation."
            )
        return

    raise AdoptionError(
        f"Unsupported database dialect {dialect_name!r}; only SQLite and Postgres "
        "legacy schemas can be adopted safely."
    )


def validate_legacy_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    table_names = set(inspector.get_table_names())

    if "alembic_version" in table_names:
        raise AdoptionError("Database is already managed by Alembic; refusing to stamp it.")
    if "games" not in table_names:
        raise AdoptionError(
            "Legacy games table is absent; use scripts/upgrade_database.py for a "
            "fresh database."
        )

    unexpected_tables = table_names - {"games"}
    if unexpected_tables:
        names = ", ".join(sorted(unexpected_tables))
        raise AdoptionError(f"Unexpected legacy tables present: {names}")

    columns = {column["name"]: column for column in inspector.get_columns("games")}
    actual_names = set(columns)
    expected_names = set(EXPECTED_COLUMNS)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise AdoptionError(
            f"games columns do not match baseline; missing={missing}, unexpected={unexpected}"
        )

    primary_key = inspector.get_pk_constraint("games")
    primary_key_columns = primary_key.get("constrained_columns") or []
    if primary_key_columns != ["id"]:
        raise AdoptionError(
            f"games primary key must be exactly ['id']; got {primary_key_columns!r}"
        )

    for name, (expected_type, expected_nullable) in EXPECTED_COLUMNS.items():
        column = columns[name]
        if not _type_matches(column["type"], expected_type):
            raise AdoptionError(
                f"games.{name} has incompatible type {column['type']!r}; "
                f"expected {expected_type.__name__}"
            )
        if bool(column.get("nullable")) != expected_nullable:
            raise AdoptionError(
                f"games.{name} nullable={column.get('nullable')!r}; "
                f"expected {expected_nullable}"
            )
        if name != "id" and column.get("default") is not None:
            raise AdoptionError(
                f"games.{name} unexpectedly defines database default "
                f"{column.get('default')!r}"
            )

    _validate_generated_id(connection, columns["id"])

    indexes = {index["name"]: index for index in inspector.get_indexes("games")}
    expected_index = indexes.get("ix_games_id")
    if expected_index is None:
        raise AdoptionError("Required legacy index ix_games_id is absent.")
    if expected_index.get("column_names") != ["id"] or bool(expected_index.get("unique")):
        raise AdoptionError("ix_games_id must be a non-unique index on games(id).")
    if set(indexes) != {"ix_games_id"}:
        raise AdoptionError(
            f"Unexpected games indexes present: {sorted(set(indexes) - {'ix_games_id'})}"
        )

    if inspector.get_foreign_keys("games"):
        raise AdoptionError("Legacy games table must not contain foreign keys.")
    if inspector.get_unique_constraints("games"):
        raise AdoptionError("Legacy games table must not contain unique constraints.")
    if inspector.get_check_constraints("games"):
        raise AdoptionError("Legacy games table must not contain check constraints.")


def adopt_database(
    database_url: str | None = None,
    *,
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
        with engine.begin() as connection:
            validate_legacy_schema(connection)

            alembic_config = Config(str(config_path))
            # Reuse the already-validated connection so validation and stamping
            # cannot accidentally target different URLs.
            alembic_config.attributes["connection"] = connection
            command.stamp(alembic_config, BASELINE_REVISION)
    finally:
        engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and stamp an exact legacy games database at revision 0001."
    )
    parser.add_argument(
        "--database-url",
        help=(
            "Database URL to adopt. Defaults to MIGRATION_DATABASE_URL, then "
            "DATABASE_URL; there is intentionally no implicit local-file fallback."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        adopt_database(args.database_url)
    except AdoptionError as exc:
        print(f"Refusing baseline adoption: {exc}", file=sys.stderr)
        return 2

    print(
        "Legacy schema validated and stamped at 0001_games_baseline. "
        "Run scripts/upgrade_database.py next."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
