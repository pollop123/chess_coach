"""Rook-specific file, rank, connection, and mobility features."""

import chess


OPEN_FILE_BONUS = 10
SEMI_OPEN_FILE_BONUS = 6
SEVENTH_RANK_BONUS = 12
CONNECTED_ROOKS_BONUS = 8
ROOK_MOBILITY_WEIGHT = 1


def rook_activity_for_color(board: chess.Board, color: chess.Color) -> int:
    rooks = list(board.pieces(chess.ROOK, color))
    if not rooks:
        return 0

    friendly_pawns = board.pieces(chess.PAWN, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    score = 0

    for square in rooks:
        file_mask = chess.BB_FILES[chess.square_file(square)]
        has_friendly_pawn = bool(friendly_pawns & file_mask)
        has_enemy_pawn = bool(enemy_pawns & file_mask)
        if not has_friendly_pawn and not has_enemy_pawn:
            score += OPEN_FILE_BONUS
        elif not has_friendly_pawn:
            score += SEMI_OPEN_FILE_BONUS

        rank = chess.square_rank(square)
        if (color == chess.WHITE and rank == 6) or (
            color == chess.BLACK and rank == 1
        ):
            score += SEVENTH_RANK_BONUS

        score += len(
            board.attacks(square) & ~board.occupied_co[color]
        ) * ROOK_MOBILITY_WEIGHT

    for index, square in enumerate(rooks):
        attacked = board.attacks(square)
        for other_square in rooks[index + 1 :]:
            if other_square in attacked:
                score += CONNECTED_ROOKS_BONUS

    return score


def rook_activity_score(board: chess.Board) -> int:
    """Return a white-centric rook-activity score."""
    return rook_activity_for_color(
        board, chess.WHITE
    ) - rook_activity_for_color(board, chess.BLACK)
