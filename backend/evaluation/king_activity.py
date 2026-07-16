"""King activity for low-material endgames."""

import chess

from .constants import PIECE_VALUES


OPPOSITION_BONUS = 18
PAWN_PROXIMITY_WEIGHT = 3
MAX_NON_PAWN_MATERIAL = 1_400


def _manhattan(first: chess.Square, second: chess.Square) -> int:
    return abs(chess.square_file(first) - chess.square_file(second)) + abs(
        chess.square_rank(first) - chess.square_rank(second)
    )


def _non_pawn_material(board: chess.Board) -> int:
    return (
        PIECE_VALUES[chess.KNIGHT] * chess.popcount(board.knights)
        + PIECE_VALUES[chess.BISHOP] * chess.popcount(board.bishops)
        + PIECE_VALUES[chess.ROOK] * chess.popcount(board.rooks)
        + PIECE_VALUES[chess.QUEEN] * chess.popcount(board.queens)
    )


def _pawn_proximity(
    board: chess.Board,
    color: chess.Color,
    pawns: int,
) -> int:
    king = board.king(color)
    if king is None or not pawns:
        return 0
    distance = min(_manhattan(king, pawn) for pawn in chess.scan_forward(pawns))
    return max(0, 7 - distance) * PAWN_PROXIMITY_WEIGHT


def _opposition_score(board: chess.Board, pawns: int) -> int:
    non_king_pieces = board.occupied & ~(board.kings | pawns)
    if non_king_pieces:
        return 0

    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king is None or black_king is None:
        return 0

    same_file = chess.square_file(white_king) == chess.square_file(black_king)
    same_rank = chess.square_rank(white_king) == chess.square_rank(black_king)
    if not (same_file or same_rank) or _manhattan(white_king, black_king) != 2:
        return 0

    middle_file = (chess.square_file(white_king) + chess.square_file(black_king)) // 2
    middle_rank = (chess.square_rank(white_king) + chess.square_rank(black_king)) // 2
    if board.piece_at(chess.square(middle_file, middle_rank)) is not None:
        return 0

    return OPPOSITION_BONUS if board.turn == chess.BLACK else -OPPOSITION_BONUS


def king_activity_score(board: chess.Board, endgame: bool) -> int:
    """Reward useful king proximity and direct opposition in true endgames."""
    if not endgame or _non_pawn_material(board) > MAX_NON_PAWN_MATERIAL:
        return 0
    pawns = board.pawns
    return (
        _pawn_proximity(board, chess.WHITE, pawns)
        - _pawn_proximity(board, chess.BLACK, pawns)
        + _opposition_score(board, pawns)
    )
