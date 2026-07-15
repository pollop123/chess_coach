"""Material and piece-square evaluation components."""

import chess

from .constants import (
    BISHOP_TABLE,
    KING_TABLE_ENDGAME,
    KING_TABLE_OPENING,
    KNIGHT_TABLE,
    PAWN_TABLE,
    PIECE_VALUES,
    QUEEN_TABLE,
    ROOK_TABLE,
)

_PIECE_SQUARE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
}


def get_piece_square_value(
    piece_type: chess.PieceType,
    square: chess.Square,
    color: chess.Color,
    endgame: bool,
) -> int:
    if color == chess.WHITE:
        square = chess.square_mirror(square)

    if piece_type == chess.KING:
        table = KING_TABLE_ENDGAME if endgame else KING_TABLE_OPENING
    else:
        table = _PIECE_SQUARE_TABLES.get(piece_type)
    return table[square] if table is not None else 0


def material_and_piece_square_scores(board: chess.Board, endgame: bool) -> tuple[int, int]:
    """Calculate both board-scan components without traversing pieces twice."""
    material = 0
    piece_square = 0
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        material += PIECE_VALUES[piece.piece_type] * sign
        piece_square += get_piece_square_value(
            piece.piece_type, square, piece.color, endgame
        ) * sign
    return material, piece_square


def material_score(board: chess.Board) -> int:
    return sum(
        PIECE_VALUES[piece.piece_type] * (1 if piece.color == chess.WHITE else -1)
        for piece in board.piece_map().values()
    )


def piece_square_score(board: chess.Board, endgame: bool) -> int:
    score = 0
    for square, piece in board.piece_map().items():
        value = get_piece_square_value(piece.piece_type, square, piece.color, endgame)
        score += value if piece.color == chess.WHITE else -value
    return score
