import multiprocessing
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

from scripts.adopt_alembic_baseline import (
    AdoptionError,
    adopt_database,
    postgres_id_is_generated,
)
from scripts.upgrade_database import (
    POSTGRES_MIGRATION_LOCK_ID,
    UpgradeSafetyError,
    acquire_postgres_migration_lock,
    upgrade_database,
)


BACKEND_DIR = Path(__file__).resolve().parent
ALEMBIC_CONFIG_PATH = BACKEND_DIR / "alembic.ini"


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_CONFIG_PATH))
    config.attributes["migration_database_url"] = database_url
    return config


def _create_legacy_database(
    path: Path,
    *,
    extra_column: bool = False,
    id_type: str = "INTEGER",
) -> None:
    engine = sa.create_engine(_sqlite_url(path))
    extra_sql = "                    notes TEXT,\n" if extra_column else ""
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE games (
                    id """
                + id_type
                + """ NOT NULL,
                    date DATETIME,
                    player_white VARCHAR,
                    player_black VARCHAR,
                    result VARCHAR,
                    pgn TEXT,
                    fen VARCHAR,
                """
                + extra_sql
                + """
                    PRIMARY KEY (id)
                )
                """
            )
            connection.exec_driver_sql("CREATE INDEX ix_games_id ON games (id)")
            connection.execute(
                sa.text(
                    """
                    INSERT INTO games
                        (id, date, player_white, player_black, result, pgn, fen)
                    VALUES
                        (:id, :date, :white, :black, :result, :pgn, :fen)
                    """
                ),
                {
                    "id": 7,
                    "date": "2026-07-31 12:00:00",
                    "white": "Human",
                    "black": "AI",
                    "result": "1-0",
                    "pgn": "1. e4 e5 2. Nf3",
                    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
                },
            )
    finally:
        engine.dispose()


def _version_and_rows(database_url: str) -> tuple[str, list[tuple]]:
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            version = connection.scalar(
                sa.text("SELECT version_num FROM alembic_version")
            )
            rows = list(
                connection.execute(
                    sa.text(
                        "SELECT id, date, player_white, player_black, result, pgn, fen "
                        "FROM games ORDER BY id"
                    )
                ).tuples()
            )
            return version, rows
    finally:
        engine.dispose()


def _concurrent_upgrade_worker(
    database_url: str,
    start_event,
    result_queue,
) -> None:
    start_event.wait()
    try:
        upgrade_database(database_url)
    except BaseException as exc:
        result_queue.put(f"{type(exc).__name__}: {exc}")
    else:
        result_queue.put(None)


class MigrationTests(unittest.TestCase):
    def test_concurrent_sqlite_upgrades_are_serialized_across_processes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "concurrent.db"
            database_url = _sqlite_url(database_path)
            context = multiprocessing.get_context("spawn")
            start_event = context.Event()
            result_queue = context.Queue()
            processes = [
                context.Process(
                    target=_concurrent_upgrade_worker,
                    args=(database_url, start_event, result_queue),
                )
                for _ in range(3)
            ]

            try:
                for process in processes:
                    process.start()
                start_event.set()
                for process in processes:
                    process.join(timeout=20)
                for process in processes:
                    self.assertFalse(process.is_alive(), "migration process timed out")
                    self.assertEqual(process.exitcode, 0)

                results = [result_queue.get(timeout=5) for _ in processes]
                self.assertEqual(results, [None, None, None])
            finally:
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                    process.join(timeout=5)
                result_queue.close()

            engine = sa.create_engine(database_url)
            try:
                with engine.connect() as connection:
                    self.assertEqual(
                        connection.scalar(
                            sa.text("SELECT version_num FROM alembic_version")
                        ),
                        "0002_review_jobs",
                    )
                self.assertEqual(
                    set(sa.inspect(engine).get_table_names()),
                    {"alembic_version", "games", "review_jobs", "review_moves"},
                )
            finally:
                engine.dispose()

    def test_postgres_upgrade_lock_is_transaction_scoped_and_stable(self):
        connection = Mock()

        acquire_postgres_migration_lock(connection)

        statement, parameters = connection.execute.call_args.args
        self.assertIn("pg_advisory_xact_lock", str(statement))
        self.assertEqual(parameters, {"lock_id": POSTGRES_MIGRATION_LOCK_ID})

    def test_safe_upgrade_allows_fresh_database(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "safe-fresh.db"
            database_url = _sqlite_url(database_path)

            upgrade_database(database_url)
            # A managed database is also safe and the second upgrade is a no-op.
            upgrade_database(database_url)

            engine = sa.create_engine(database_url)
            try:
                inspector = sa.inspect(engine)
                self.assertEqual(
                    set(inspector.get_table_names()),
                    {"alembic_version", "games", "review_jobs", "review_moves"},
                )
                with engine.connect() as connection:
                    self.assertEqual(
                        connection.scalar(
                            sa.text("SELECT version_num FROM alembic_version")
                        ),
                        "0002_review_jobs",
                    )
            finally:
                engine.dispose()

    def test_safe_upgrade_refuses_legacy_without_creating_version_table(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "safe-legacy.db"
            database_url = _sqlite_url(database_path)
            _create_legacy_database(database_path)

            with self.assertRaisesRegex(UpgradeSafetyError, "db-adopt"):
                upgrade_database(database_url)

            engine = sa.create_engine(database_url)
            try:
                inspector = sa.inspect(engine)
                self.assertNotIn("alembic_version", inspector.get_table_names())
                with engine.connect() as connection:
                    self.assertEqual(
                        connection.scalar(sa.text("SELECT COUNT(*) FROM games")),
                        1,
                    )
            finally:
                engine.dispose()

    def test_safe_upgrade_refuses_unknown_unmanaged_schema(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "unknown.db"
            database_url = _sqlite_url(database_path)
            engine = sa.create_engine(database_url)
            try:
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"
                    )
            finally:
                engine.dispose()

            with self.assertRaisesRegex(UpgradeSafetyError, "not empty"):
                upgrade_database(database_url)

            engine = sa.create_engine(database_url)
            try:
                self.assertEqual(
                    set(sa.inspect(engine).get_table_names()),
                    {"unrelated"},
                )
            finally:
                engine.dispose()

    def test_migrations_prefer_direct_migration_database_url(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            migration_path = directory / "direct.db"
            application_path = directory / "pooled.db"
            config = Config(str(ALEMBIC_CONFIG_PATH))

            with patch.dict(
                os.environ,
                {
                    "MIGRATION_DATABASE_URL": _sqlite_url(migration_path),
                    "DATABASE_URL": _sqlite_url(application_path),
                },
                clear=True,
            ):
                command.upgrade(config, "head")

            self.assertTrue(migration_path.exists())
            self.assertFalse(application_path.exists())

    def test_fresh_database_upgrades_to_head(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "fresh.db"
            database_url = _sqlite_url(database_path)

            alembic_config = _alembic_config(database_url)
            command.upgrade(alembic_config, "head")

            engine = sa.create_engine(database_url)
            try:
                inspector = sa.inspect(engine)
                self.assertEqual(
                    set(inspector.get_table_names()),
                    {"alembic_version", "games", "review_jobs", "review_moves"},
                )
                games_columns = {
                    column["name"]: column for column in inspector.get_columns("games")
                }
                self.assertEqual(
                    list(games_columns),
                    [
                        "id",
                        "date",
                        "player_white",
                        "player_black",
                        "result",
                        "pgn",
                        "fen",
                    ],
                )
                self.assertFalse(games_columns["id"]["nullable"])
                self.assertTrue(games_columns["date"]["nullable"])
                self.assertEqual(
                    {
                        index["name"]: index["column_names"]
                        for index in inspector.get_indexes("games")
                    },
                    {"ix_games_id": ["id"]},
                )
                with engine.connect() as connection:
                    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                    self.assertEqual(
                        connection.exec_driver_sql("PRAGMA foreign_keys").scalar(),
                        1,
                    )
                    self.assertEqual(
                        connection.scalar(
                            sa.text("SELECT version_num FROM alembic_version")
                        ),
                        "0002_review_jobs",
                    )
                    connection.execute(
                        sa.text("INSERT INTO games (id) VALUES (1)")
                    )
                    connection.execute(
                        sa.text(
                            """
                            INSERT INTO review_jobs
                                (id, game_id, request_hash, pgn, perspective, depth,
                                 progress_total)
                            VALUES
                                ('job-1', 1, :request_hash, '1. e4', 'white', 2, 1)
                            """
                        ),
                        {"request_hash": "a" * 64},
                    )
                    connection.execute(
                        sa.text(
                            """
                            INSERT INTO review_moves
                                (review_job_id, ply, fen, score_cp,
                                 score_for_perspective_cp, analysis_source)
                            VALUES
                                ('job-1', 0, :fen, 20, 20, 'custom')
                            """
                        ),
                        {"fen": "8/8/8/8/8/8/8/K6k w - - 0 1"},
                    )

                    connection.execute(sa.text("DELETE FROM games WHERE id = 1"))
                    self.assertIsNone(
                        connection.scalar(
                            sa.text(
                                "SELECT game_id FROM review_jobs WHERE id = 'job-1'"
                            )
                        )
                    )

                    connection.execute(
                        sa.text("DELETE FROM review_jobs WHERE id = 'job-1'")
                    )
                    self.assertEqual(
                        connection.scalar(
                            sa.text("SELECT COUNT(*) FROM review_moves")
                        ),
                        0,
                    )
                    connection.commit()
            finally:
                engine.dispose()

            # Keep the ORM metadata and committed migration head in lockstep.
            command.check(alembic_config)

    def test_legacy_adoption_preserves_rows_before_and_after_upgrade(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "legacy.db"
            database_url = _sqlite_url(database_path)
            _create_legacy_database(database_path)

            engine = sa.create_engine(database_url)
            try:
                with engine.connect() as connection:
                    original_rows = list(
                        connection.execute(
                            sa.text("SELECT * FROM games ORDER BY id")
                        ).tuples()
                    )
            finally:
                engine.dispose()

            adopt_database(database_url)
            adopted_version, adopted_rows = _version_and_rows(database_url)
            self.assertEqual(adopted_version, "0001_games_baseline")
            self.assertEqual(adopted_rows, original_rows)

            upgrade_database(database_url)
            upgraded_version, upgraded_rows = _version_and_rows(database_url)
            self.assertEqual(upgraded_version, "0002_review_jobs")
            self.assertEqual(upgraded_rows, original_rows)

    def test_adoption_refuses_unexpected_legacy_schema_without_stamping(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "unexpected.db"
            database_url = _sqlite_url(database_path)
            _create_legacy_database(database_path, extra_column=True)

            with self.assertRaisesRegex(AdoptionError, "columns do not match"):
                adopt_database(database_url)

            engine = sa.create_engine(database_url)
            try:
                inspector = sa.inspect(engine)
                self.assertNotIn("alembic_version", inspector.get_table_names())
                with engine.connect() as connection:
                    self.assertEqual(
                        connection.scalar(sa.text("SELECT COUNT(*) FROM games")),
                        1,
                    )
            finally:
                engine.dispose()

    def test_adoption_refuses_sqlite_int_primary_key_without_rowid_generation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "non-generating-id.db"
            database_url = _sqlite_url(database_path)
            _create_legacy_database(database_path, id_type="INT")

            with self.assertRaisesRegex(AdoptionError, "rowid alias"):
                adopt_database(database_url)

            engine = sa.create_engine(database_url)
            try:
                inspector = sa.inspect(engine)
                self.assertNotIn("alembic_version", inspector.get_table_names())
                with engine.connect() as connection:
                    with self.assertRaises(sa.exc.IntegrityError):
                        connection.execute(
                            sa.text(
                                """
                                INSERT INTO games
                                    (date, player_white, player_black, result, pgn, fen)
                                VALUES
                                    (NULL, 'Human', 'AI', '1-0', '1. e4', '8/8/8/8/8/8/8/K6k')
                                """
                            )
                        )
            finally:
                engine.dispose()

    def test_postgres_generated_id_detection(self):
        self.assertTrue(
            postgres_id_is_generated(
                {"default": "nextval('games_id_seq'::regclass)", "identity": None}
            )
        )
        self.assertTrue(
            postgres_id_is_generated(
                {"default": None, "identity": {"always": False}}
            )
        )
        self.assertFalse(
            postgres_id_is_generated({"default": None, "identity": None})
        )
        self.assertFalse(
            postgres_id_is_generated({"default": "1", "identity": None})
        )

    def test_adoption_requires_explicit_database_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(AdoptionError, "Set MIGRATION_DATABASE_URL"):
                adopt_database()


if __name__ == "__main__":
    unittest.main()
