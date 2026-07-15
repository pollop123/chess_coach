"""Game-phase classification used by the legacy-compatible evaluator."""

import chess


def is_endgame(board: chess.Board) -> bool:
    """Preserve the original evaluator's binary endgame boundary."""
    queen_count = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(
        board.pieces(chess.QUEEN, chess.BLACK)
    )
    minor_count = sum(
        len(board.pieces(piece_type, color))
        for piece_type in (chess.KNIGHT, chess.BISHOP)
        for color in (chess.WHITE, chess.BLACK)
    )
    return queen_count == 0 or minor_count <= 2


def phase_name(board: chess.Board) -> str:
    return "endgame" if is_endgame(board) else "middlegame"
