"""King-safety component for non-endgame positions."""

import chess


def middlegame_king_exposure_penalty(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return 0

    total_pieces = len(board.piece_map())
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


def king_safety_score(board: chess.Board, endgame: bool) -> int:
    if endgame:
        return 0

    score = 0
    if board.has_castling_rights(chess.WHITE):
        score += 20
    if board.has_castling_rights(chess.BLACK):
        score -= 20
    score -= middlegame_king_exposure_penalty(board, chess.WHITE)
    score += middlegame_king_exposure_penalty(board, chess.BLACK)
    return score
