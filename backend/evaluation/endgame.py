"""Endgame-specific evaluation components."""

import chess


def mop_up_score(board: chess.Board, base_score: int, endgame: bool) -> int:
    if not endgame:
        return 0

    if base_score > 200:
        winning_side = chess.WHITE
    elif base_score < -200:
        winning_side = chess.BLACK
    else:
        return 0

    losing_king = board.king(not winning_side)
    winning_king = board.king(winning_side)
    if losing_king is None or winning_king is None:
        return 0

    losing_rank = chess.square_rank(losing_king)
    losing_file = chess.square_file(losing_king)
    distance_from_center = max(3 - losing_rank, losing_rank - 4) + max(
        3 - losing_file, losing_file - 4
    )
    winning_rank = chess.square_rank(winning_king)
    winning_file = chess.square_file(winning_king)
    king_distance = abs(losing_rank - winning_rank) + abs(losing_file - winning_file)
    score = ((4 * distance_from_center) + (14 - king_distance)) * 10
    return score if winning_side == chess.WHITE else -score
