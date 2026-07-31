"""Create the legacy games table baseline.

Revision ID: 0001_games_baseline
Revises:
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_games_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This intentionally mirrors the table historically produced by
    # Base.metadata.create_all().  Tightening nullable columns or adding server
    # defaults here would make adopting an existing database unsafe.
    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("player_white", sa.String(), nullable=True),
        sa.Column("player_black", sa.String(), nullable=True),
        sa.Column("result", sa.String(), nullable=True),
        sa.Column("pgn", sa.Text(), nullable=True),
        sa.Column("fen", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_games_id", "games", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_games_id", table_name="games")
    op.drop_table("games")
