"""Pawn-structure features that are not captured by piece-square tables."""

import chess


DOUBLED_PAWN_PENALTY = 14
ISOLATED_PAWN_PENALTY = 12
CONNECTED_PAWN_BONUS = 6
PROTECTED_PASSED_PAWN_BONUS = 8
PASSED_PAWN_BONUS = (0, 0, 4, 10, 22, 40, 70, 0)


def _advance(square: chess.Square, color: chess.Color) -> int:
    rank = chess.square_rank(square)
    return rank if color == chess.WHITE else 7 - rank


def is_passed_pawn(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    """Return whether no enemy pawn can block or challenge this pawn ahead."""
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    enemy_pawns = board.pieces(chess.PAWN, not color)

    for enemy_square in enemy_pawns:
        enemy_file = chess.square_file(enemy_square)
        if abs(enemy_file - file_index) > 1:
            continue
        enemy_rank = chess.square_rank(enemy_square)
        if (color == chess.WHITE and enemy_rank > rank) or (
            color == chess.BLACK and enemy_rank < rank
        ):
            return False
    return True


def pawn_structure_for_color(board: chess.Board, color: chess.Color) -> int:
    pawns = board.pieces(chess.PAWN, color)
    if not pawns:
        return 0

    file_counts = [0] * 8
    for square in pawns:
        file_counts[chess.square_file(square)] += 1

    score = -sum(
        max(0, count - 1) * DOUBLED_PAWN_PENALTY for count in file_counts
    )
    for square in pawns:
        file_index = chess.square_file(square)
        has_neighbor = (
            (file_index > 0 and file_counts[file_index - 1] > 0)
            or (file_index < 7 and file_counts[file_index + 1] > 0)
        )
        if not has_neighbor:
            score -= ISOLATED_PAWN_PENALTY

        pawn_defenders = board.attackers(color, square) & pawns
        if pawn_defenders:
            score += CONNECTED_PAWN_BONUS

        if is_passed_pawn(board, square, color):
            score += PASSED_PAWN_BONUS[_advance(square, color)]
            if pawn_defenders:
                score += PROTECTED_PASSED_PAWN_BONUS

    return score


def pawn_structure_score(board: chess.Board) -> int:
    """Return a white-centric structural pawn score."""
    return pawn_structure_for_color(
        board, chess.WHITE
    ) - pawn_structure_for_color(board, chess.BLACK)
