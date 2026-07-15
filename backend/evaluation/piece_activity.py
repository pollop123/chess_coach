"""Minor-piece and queen activity features."""

import chess


MOBILITY_WEIGHTS = {
    chess.KNIGHT: 3,
    chess.BISHOP: 2,
    chess.QUEEN: 1,
}
BISHOP_PAIR_BONUS = 24
KNIGHT_OUTPOST_BONUS = 16


def _mobility(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    return len(board.attacks(square) & ~board.occupied_co[color])


def _is_knight_outpost(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    rank = chess.square_rank(square)
    if (color == chess.WHITE and rank < 4) or (color == chess.BLACK and rank > 3):
        return False

    friendly_pawns = board.pieces(chess.PAWN, color)
    if not (board.attackers(color, square) & friendly_pawns):
        return False

    file_index = chess.square_file(square)
    for enemy_pawn in board.pieces(chess.PAWN, not color):
        if abs(chess.square_file(enemy_pawn) - file_index) != 1:
            continue
        enemy_rank = chess.square_rank(enemy_pawn)
        if (color == chess.WHITE and enemy_rank > rank) or (
            color == chess.BLACK and enemy_rank < rank
        ):
            return False
    return True


def piece_activity_for_color(board: chess.Board, color: chess.Color) -> int:
    score = 0
    for piece_type, weight in MOBILITY_WEIGHTS.items():
        for square in board.pieces(piece_type, color):
            score += _mobility(board, square, color) * weight
            if piece_type == chess.KNIGHT and _is_knight_outpost(
                board, square, color
            ):
                score += KNIGHT_OUTPOST_BONUS

    if len(board.pieces(chess.BISHOP, color)) >= 2:
        score += BISHOP_PAIR_BONUS
    return score


def piece_activity_score(board: chess.Board) -> int:
    """Return white's minor/queen activity minus black's activity."""
    return piece_activity_for_color(
        board, chess.WHITE
    ) - piece_activity_for_color(board, chess.BLACK)
