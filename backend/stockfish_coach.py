"""Coach analysis from one Stockfish MultiPV search, in the shape the coach already consumes.

The built-in engine stays the opponent (it has difficulties and styles); for
explaining a position the coach should see the strongest evaluation available.
Reasons, themes and warnings still come from the same board heuristics, fed
with Stockfish's scores and move order.
"""
import os

import chess
import chess.engine

from chess_engine import (
    calculate_winning_chance,
    finalize_teaching_analysis,
    format_evaluation,
    teaching_candidate,
)
from evaluation.constants import MATE_SCORE


def engine_score(pov_score, board):
    """Stockfish's score in the built-in engine's white-perspective convention."""
    white = pov_score.white()
    mate = white.mate()
    if mate is None:
        return int(white.score())
    mating_side_to_move = (mate > 0) == (board.turn == chess.WHITE)
    plies = max(1, 2 * abs(mate) - (1 if mating_side_to_move else 0))
    return MATE_SCORE - plies if mate > 0 else -(MATE_SCORE - plies)


def coach_analysis(board, stockfish_path, candidate_count=5, nodes=None, time_limit=None):
    """Return (analysis, teaching_analysis) for a position that is not game over."""
    nodes = nodes or int(os.getenv("STOCKFISH_COACH_NODES", "300000"))
    time_limit = time_limit or float(os.getenv("STOCKFISH_COACH_SECONDS", "1.5"))
    wanted = min(candidate_count, board.legal_moves.count())
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path, timeout=10)
    try:
        engine.configure({"Threads": 1, "Hash": 64})
        infos = engine.analyse(
            board, chess.engine.Limit(nodes=nodes, time=time_limit), multipv=wanted, game=object(),
        )
    finally:
        engine.quit()
    infos = [info for info in infos if info.get("pv")]
    if not infos:
        raise RuntimeError("Stockfish returned no principal variation")

    best = infos[0]
    best_move = best["pv"][0]
    score = engine_score(best["score"], board)
    analysis = {
        "best_move": best_move,
        "score": score,
        "eval_display": format_evaluation(score),
        "winning_chance": calculate_winning_chance(score),
        "pv": [move.uci() for move in best["pv"][:10]],
        "book_line": [],
        "depth": best.get("depth"),
        "nodes": best.get("nodes"),
        "from_book": False,
        "analysis_source": "stockfish",
    }
    # MultiPV already lists moves best first, which finalize_teaching_analysis expects.
    candidates = [
        teaching_candidate(
            board, info["pv"][0], engine_score(info["score"], board),
            [move.uci() for move in info["pv"][:10]], best_move,
        )
        for info in infos
    ]
    teaching = finalize_teaching_analysis(board, candidates, wanted, len(candidates) == wanted)
    teaching["analysis_source"] = "stockfish"
    return analysis, teaching
