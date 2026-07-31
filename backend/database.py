import os
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATABASE_PATH = os.path.join(BASE_DIR, "games.db")
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE_PATH}")

# 建立資料庫引擎
is_sqlite = SQLALCHEMY_DATABASE_URL.startswith("sqlite")
connect_args = (
    {"check_same_thread": False, "timeout": 30}
    if is_sqlite
    else {}
)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 定義 "Game" 資料表
class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    player_white = Column(String, default="Human")
    player_black = Column(String, default="AI")
    result = Column(String)  # 例如 "1-0", "0-1", "1/2-1/2"
    pgn = Column(Text)       # 完整的棋譜文字
    fen = Column(String)     # 最後局面的 FEN


class ReviewJob(Base):
    __tablename__ = "review_jobs"
    __table_args__ = (
        CheckConstraint(
            "perspective IN ('white', 'black')",
            name="ck_review_jobs_perspective",
        ),
        CheckConstraint(
            "depth BETWEEN 1 AND 6",
            name="ck_review_jobs_depth",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_review_jobs_status",
        ),
        UniqueConstraint(
            "idempotency_key",
            name="uq_review_jobs_idempotency_key",
        ),
        Index("ix_review_jobs_status_created", "status", "created_at"),
        Index("ix_review_jobs_status_lease", "status", "lease_expires_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id = Column(
        Integer,
        ForeignKey("games.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    idempotency_key = Column(String(128), nullable=True)
    request_hash = Column(String(64), nullable=False, index=True)
    pgn = Column(Text, nullable=False)
    perspective = Column(String(5), nullable=False)
    depth = Column(Integer, nullable=False)
    requested_engine = Column(String(16), nullable=False, default="auto")
    analysis_source = Column(String(16), nullable=True)
    engine_version = Column(String(64), nullable=True)
    stockfish_nodes = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="queued")
    progress_current = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False)
    cancel_requested = Column(Boolean, nullable=False, default=False)
    attempt_count = Column(Integer, nullable=False, default=0)
    worker_id = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class ReviewMove(Base):
    __tablename__ = "review_moves"
    __table_args__ = (
        CheckConstraint("ply >= 0", name="ck_review_moves_ply"),
        CheckConstraint(
            "mover_color IS NULL OR mover_color IN ('white', 'black')",
            name="ck_review_moves_mover_color",
        ),
        CheckConstraint(
            "classification IS NULL OR classification IN "
            "('good', 'inaccuracy', 'mistake', 'blunder')",
            name="ck_review_moves_classification",
        ),
        UniqueConstraint(
            "review_job_id",
            "ply",
            name="uq_review_moves_job_ply",
        ),
    )

    id = Column(Integer, primary_key=True)
    review_job_id = Column(
        String(36),
        ForeignKey("review_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ply = Column(Integer, nullable=False)
    mover_color = Column(String(5), nullable=True)
    move_uci = Column(String(5), nullable=True)
    best_move_uci = Column(String(5), nullable=True)
    fen = Column(String(120), nullable=False)
    score_cp = Column(Integer, nullable=False)
    score_for_perspective_cp = Column(Integer, nullable=False)
    best_eval_for_perspective_cp = Column(Integer, nullable=True)
    raw_cp_loss = Column(Integer, nullable=True)
    cp_loss = Column(Integer, nullable=True)
    classification = Column(String(16), nullable=True)
    mate_threat = Column(Boolean, nullable=False, default=False)
    is_checkmate = Column(Boolean, nullable=False, default=False)
    wdl = Column(JSON, nullable=True)
    themes = Column(JSON, nullable=True)
    analysis_source = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
