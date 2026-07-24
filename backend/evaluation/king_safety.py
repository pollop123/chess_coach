"""King-safety component for non-endgame positions."""

import chess


CASTLING_RIGHTS_BONUS = 12
PAWN_SHIELD_BONUS = 10
KING_FILE_PENALTY = 12
ADJACENT_FILE_PENALTY = 6
FULLY_OPEN_FILE_PENALTY = 4
KING_ADVANCE_PENALTY = 14
ATTACKED_ZONE_PENALTY = 10
ATTACKER_PENALTY = 6
DEFENDER_BONUS = 3
UNCASTLED_CENTER_PENALTY = 24
MISSING_SHELTER_PAWN_PENALTY = 12


def middlegame_king_exposure_penalty(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return 0

    # ``occupied`` already contains one bit per piece.  Counting those bits is
    # equivalent to building ``piece_map()`` and taking its length, but this
    # function runs twice at every evaluated leaf, so avoiding the temporary
    # dictionary is material to search throughput.
    total_pieces = chess.popcount(board.occupied)
    if total_pieces < 14:
        return 0

    home_rank = 0 if color == chess.WHITE else 7
    if chess.square_rank(king_square) == home_rank:
        return 0

    king_zone = [king_square, *chess.SquareSet(chess.BB_KING_ATTACKS[king_square])]
    attacked_zone = sum(
        1 for square in king_zone if board.is_attacked_by(not color, square)
    )
    return 180 + min(120, (total_pieces - 14) * 8) + attacked_zone * 20


def _danger_scale_percent(board: chess.Board, color: chess.Color) -> int:
    if board.pieces_mask(chess.QUEEN, not color):
        return 100
    if board.pieces_mask(chess.ROOK, not color):
        return 70
    return 40


def _heavy_piece_danger_percent(board: chess.Board, color: chess.Color) -> int:
    """Scale shelter value by the enemy heavy pieces that can exploit files."""
    enemy = not color
    queens = chess.popcount(board.pieces_mask(chess.QUEEN, enemy))
    rooks = chess.popcount(board.pieces_mask(chess.ROOK, enemy))
    return min(100, queens * 60 + rooks * 20)


def _pawn_shield_count(
    board: chess.Board, king_square: chess.Square, color: chess.Color
) -> int:
    direction = 1 if color == chess.WHITE else -1
    king_rank = chess.square_rank(king_square)
    king_file = chess.square_file(king_square)
    friendly_pawns = board.pieces_mask(chess.PAWN, color)
    shield = 0
    for file_index in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        for distance in (1, 2):
            rank = king_rank + direction * distance
            if (
                0 <= rank <= 7
                and friendly_pawns & chess.BB_SQUARES[chess.square(file_index, rank)]
            ):
                shield += 1
                break
    return shield


def contextual_pawn_shelter_for_color(
    board: chess.Board, color: chess.Color
) -> int:
    """Return a cheap, non-positive shelter score for a flank king.

    Central kings are deliberately excluded: ordinary opening pawn moves must
    not look like king-safety damage before the king commits to a wing.
    """
    king_square = board.king(color)
    if king_square is None:
        return 0
    king_file = chess.square_file(king_square)
    if king_file in {3, 4}:
        return 0
    danger_percent = _heavy_piece_danger_percent(board, color)
    if danger_percent == 0:
        return 0
    shield_count = min(3, _pawn_shield_count(board, king_square, color))
    missing_pawns = 3 - shield_count
    return -round(
        missing_pawns * MISSING_SHELTER_PAWN_PENALTY * danger_percent / 100
    )


def contextual_pawn_shelter_score(
    board: chess.Board, endgame_weight: int | bool
) -> int:
    """Return a white-centric shelter score tapered out with heavy material."""
    weight = 100 if endgame_weight is True else int(endgame_weight)
    if weight >= 100:
        return 0
    raw = contextual_pawn_shelter_for_color(
        board, chess.WHITE
    ) - contextual_pawn_shelter_for_color(board, chess.BLACK)
    return round(raw * (100 - weight) / 100)


def graded_king_safety_for_color(board: chess.Board, color: chess.Color) -> int:
    """Return a positive-is-safe score using local, continuous king features."""
    king_square = board.king(color)
    if king_square is None:
        return 0

    danger_scale = _danger_scale_percent(board, color)
    king_rank = chess.square_rank(king_square)
    king_file = chess.square_file(king_square)
    home_rank = 0 if color == chess.WHITE else 7
    home_distance = abs(king_rank - home_rank)
    friendly_pawns = board.pieces_mask(chess.PAWN, color)
    all_pawns = board.pawns
    open_file_penalty = 0
    for file_index in range(max(0, king_file - 1), min(7, king_file + 1) + 1):
        file_mask = chess.BB_FILES[file_index]
        if friendly_pawns & file_mask:
            continue
        open_file_penalty += (
            KING_FILE_PENALTY if file_index == king_file else ADJACENT_FILE_PENALTY
        )
        if not all_pawns & file_mask:
            open_file_penalty += FULLY_OPEN_FILE_PENALTY

    score = _pawn_shield_count(board, king_square, color) * PAWN_SHIELD_BONUS
    if board.has_castling_rights(color):
        score += CASTLING_RIGHTS_BONUS
    uncastled_center = (
        king_file in {3, 4}
        and not board.has_castling_rights(color)
    )
    danger = (
        home_distance * KING_ADVANCE_PENALTY
        + open_file_penalty
        + (UNCASTLED_CENTER_PENALTY if uncastled_center else 0)
    )
    return score - round(danger * danger_scale / 100)


def graded_king_safety_score(board: chess.Board, endgame_weight: int | bool) -> int:
    weight = 100 if endgame_weight is True else int(endgame_weight)
    if weight >= 100:
        return 0
    raw = graded_king_safety_for_color(
        board, chess.WHITE
    ) - graded_king_safety_for_color(board, chess.BLACK)
    return round(raw * (100 - weight) / 100)


def king_safety_score(board: chess.Board, endgame_weight: int | bool) -> int:
    weight = 100 if endgame_weight is True else int(endgame_weight)
    if weight >= 100:
        return 0

    score = 0
    if board.has_castling_rights(chess.WHITE):
        score += 20
    if board.has_castling_rights(chess.BLACK):
        score -= 20
    score -= middlegame_king_exposure_penalty(board, chess.WHITE)
    score += middlegame_king_exposure_penalty(board, chess.BLACK)
    return round(score * (100 - weight) / 100)
