"""Continuous game-phase weights shared by every evaluation component."""

import chess


MAXIMUM_PHASE_UNITS = 24
ENDGAME_LABEL_THRESHOLD = 50


def endgame_weight_percent(board: chess.Board) -> int:
    """Return a 0-100 endgame weight based on remaining non-pawn material.

    Knights and bishops are worth one phase unit, rooks two, and queens four.
    A normal starting position therefore has 24 units.  Trading material moves
    the score smoothly toward the endgame instead of crossing a queen/minor
    piece cliff.
    """
    remaining = min(
        MAXIMUM_PHASE_UNITS,
        chess.popcount(board.knights | board.bishops)
        + 2 * chess.popcount(board.rooks)
        + 4 * chess.popcount(board.queens),
    )
    return round((MAXIMUM_PHASE_UNITS - remaining) * 100 / MAXIMUM_PHASE_UNITS)


def middlegame_weight_percent(board: chess.Board) -> int:
    return 100 - endgame_weight_percent(board)


def is_endgame(board: chess.Board) -> bool:
    """Classify labels from the same phase value used by evaluation."""
    return endgame_weight_percent(board) >= ENDGAME_LABEL_THRESHOLD


def phase_name(board: chess.Board) -> str:
    return "endgame" if is_endgame(board) else "middlegame"


def strategic_weight_percent(board: chess.Board) -> int:
    """Use the shared continuous phase for strategic endgame features."""
    return endgame_weight_percent(board)
