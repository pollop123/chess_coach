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


def strategic_weight_percent(board: chess.Board) -> int:
    """Taper new strategic terms in as forcing material leaves the board."""
    phase_units = (
        chess.popcount(board.knights | board.bishops)
        + 2 * chess.popcount(board.rooks)
        + 4 * chess.popcount(board.queens)
    )
    maximum_phase_units = 24
    remaining = min(maximum_phase_units, phase_units)
    removed = maximum_phase_units - remaining
    # At shallow search depth, switching on strategic terms during an opening
    # tactic can distort the leaf comparison. The existing PST already covers
    # early development, so wait until both queens' worth of phase has left the
    # board before gradually emphasizing the richer strategic terms.
    warmup_units = 8
    effective_removed = max(0, removed - warmup_units)
    return round(
        effective_removed * 100 / (maximum_phase_units - warmup_units)
    )
