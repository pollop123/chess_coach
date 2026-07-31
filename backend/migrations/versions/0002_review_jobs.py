"""Add durable review jobs and per-position results.

Revision ID: 0002_review_jobs
Revises: 0001_games_baseline
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_review_jobs"
down_revision: Union[str, None] = "0001_games_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("pgn", sa.Text(), nullable=False),
        sa.Column("perspective", sa.String(length=5), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column(
            "requested_engine",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'auto'"),
        ),
        sa.Column("analysis_source", sa.String(length=16), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=True),
        sa.Column("stockfish_nodes", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'queued'"),
        ),
        sa.Column(
            "progress_current",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("worker_id", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "perspective IN ('white', 'black')",
            name="ck_review_jobs_perspective",
        ),
        sa.CheckConstraint(
            "depth BETWEEN 1 AND 6",
            name="ck_review_jobs_depth",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_review_jobs_status",
        ),
        sa.ForeignKeyConstraint(
            ["game_id"],
            ["games.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_review_jobs_idempotency_key",
        ),
    )
    op.create_index(
        "ix_review_jobs_game_id",
        "review_jobs",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        "ix_review_jobs_request_hash",
        "review_jobs",
        ["request_hash"],
        unique=False,
    )
    op.create_index(
        "ix_review_jobs_status_created",
        "review_jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_review_jobs_status_lease",
        "review_jobs",
        ["status", "lease_expires_at"],
        unique=False,
    )

    op.create_table(
        "review_moves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_job_id", sa.String(length=36), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("mover_color", sa.String(length=5), nullable=True),
        sa.Column("move_uci", sa.String(length=5), nullable=True),
        sa.Column("best_move_uci", sa.String(length=5), nullable=True),
        sa.Column("fen", sa.String(length=120), nullable=False),
        sa.Column("score_cp", sa.Integer(), nullable=False),
        sa.Column("score_for_perspective_cp", sa.Integer(), nullable=False),
        sa.Column("best_eval_for_perspective_cp", sa.Integer(), nullable=True),
        sa.Column("raw_cp_loss", sa.Integer(), nullable=True),
        sa.Column("cp_loss", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=True),
        sa.Column(
            "mate_threat",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_checkmate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("wdl", sa.JSON(), nullable=True),
        sa.Column("themes", sa.JSON(), nullable=True),
        sa.Column("analysis_source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("ply >= 0", name="ck_review_moves_ply"),
        sa.CheckConstraint(
            "mover_color IS NULL OR mover_color IN ('white', 'black')",
            name="ck_review_moves_mover_color",
        ),
        sa.CheckConstraint(
            "classification IS NULL OR classification IN "
            "('good', 'inaccuracy', 'mistake', 'blunder')",
            name="ck_review_moves_classification",
        ),
        sa.ForeignKeyConstraint(
            ["review_job_id"],
            ["review_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_job_id",
            "ply",
            name="uq_review_moves_job_ply",
        ),
    )
    op.create_index(
        "ix_review_moves_review_job_id",
        "review_moves",
        ["review_job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_review_moves_review_job_id", table_name="review_moves")
    op.drop_table("review_moves")

    op.drop_index("ix_review_jobs_status_lease", table_name="review_jobs")
    op.drop_index("ix_review_jobs_status_created", table_name="review_jobs")
    op.drop_index("ix_review_jobs_request_hash", table_name="review_jobs")
    op.drop_index("ix_review_jobs_game_id", table_name="review_jobs")
    op.drop_table("review_jobs")
