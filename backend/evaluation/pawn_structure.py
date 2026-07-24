"""Pawn-structure features that are not captured by piece-square tables."""

import chess


DOUBLED_PAWN_PENALTY = 14
ISOLATED_PAWN_PENALTY = 12
CONNECTED_PAWN_BONUS = 6
PROTECTED_PASSED_PAWN_BONUS = 8
PASSED_PAWN_BONUS = (0, 0, 4, 10, 22, 40, 70, 0)
CANDIDATE_PASSED_PAWN_BONUS = (0, 0, 2, 5, 10, 18, 30, 0)
CONNECTED_PASSED_PAWN_BONUS = 8
BLOCKED_PASSER_PERCENT = 45


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


def is_candidate_passed_pawn(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    """Return whether supporting pawn exchanges can plausibly create a passer."""
    if is_passed_pawn(board, square, color):
        return False
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    advance = _advance(square, color)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    friendly_pawns = board.pieces(chess.PAWN, color)

    enemy_adjacent_ahead = 0
    for enemy in enemy_pawns:
        enemy_file = chess.square_file(enemy)
        enemy_rank = chess.square_rank(enemy)
        is_ahead = enemy_rank > rank if color == chess.WHITE else enemy_rank < rank
        if not is_ahead:
            continue
        if enemy_file == file_index:
            return False
        if abs(enemy_file - file_index) == 1:
            enemy_adjacent_ahead += 1

    if enemy_adjacent_ahead == 0:
        return False
    friendly_support = sum(
        abs(chess.square_file(pawn) - file_index) == 1
        and _advance(pawn, color) >= advance - 1
        for pawn in friendly_pawns
        if pawn != square
    )
    return friendly_support >= enemy_adjacent_ahead


def _is_blocked(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    next_rank = chess.square_rank(square) + (1 if color == chess.WHITE else -1)
    if not 0 <= next_rank <= 7:
        return False
    blocker = board.piece_at(chess.square(chess.square_file(square), next_rank))
    return blocker is not None and blocker.color != color


def _has_connected_passer(
    board: chess.Board, square: chess.Square, color: chess.Color
) -> bool:
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    return any(
        abs(chess.square_file(other) - file_index) == 1
        and abs(chess.square_rank(other) - rank) <= 1
        and is_passed_pawn(board, other, color)
        for other in board.pieces(chess.PAWN, color)
        if other != square
    )


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
            passed_bonus = PASSED_PAWN_BONUS[_advance(square, color)]
            if _is_blocked(board, square, color):
                passed_bonus = round(passed_bonus * BLOCKED_PASSER_PERCENT / 100)
            score += passed_bonus
            if pawn_defenders:
                score += PROTECTED_PASSED_PAWN_BONUS
            if _has_connected_passer(board, square, color):
                score += CONNECTED_PASSED_PAWN_BONUS
        elif is_candidate_passed_pawn(board, square, color):
            score += CANDIDATE_PASSED_PAWN_BONUS[_advance(square, color)]

    return score


def pawn_structure_score(board: chess.Board) -> int:
    """Return a white-centric structural pawn score."""
    return pawn_structure_for_color(
        board, chess.WHITE
    ) - pawn_structure_for_color(board, chess.BLACK)
