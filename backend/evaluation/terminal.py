"""Terminal-position scoring."""

import chess

from .constants import MATE_SCORE


def terminal_score(board: chess.Board, ply_from_root: int = 0) -> int | None:
    if board.is_checkmate():
        score = MATE_SCORE - ply_from_root
        return -score if board.turn == chess.WHITE else score
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    return None
