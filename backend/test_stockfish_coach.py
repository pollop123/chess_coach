import os
import shutil
import unittest
from unittest.mock import patch

import chess
import chess.engine

import api
import stockfish_coach
from evaluation.constants import MATE_SCORE

STOCKFISH = shutil.which("stockfish") or (os.getenv("STOCKFISH_PATH") if os.path.exists(os.getenv("STOCKFISH_PATH", "")) else None)
FOOLS_MATE_FEN = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"


class EngineScoreTests(unittest.TestCase):
    def test_centipawns_and_mates_use_the_builtin_convention(self):
        white_to_move = chess.Board()
        pov = lambda score: chess.engine.PovScore(score, chess.WHITE)
        self.assertEqual(stockfish_coach.engine_score(pov(chess.engine.Cp(35)), white_to_move), 35)
        # White to move and mating in 1 move is 1 ply away.
        self.assertEqual(stockfish_coach.engine_score(pov(chess.engine.Mate(1)), white_to_move), MATE_SCORE - 1)
        # White to move and getting mated in 1 move: Black mates on ply 2.
        self.assertEqual(stockfish_coach.engine_score(pov(chess.engine.Mate(-1)), white_to_move), -(MATE_SCORE - 2))
        black_to_move = chess.Board(FOOLS_MATE_FEN)
        self.assertEqual(stockfish_coach.engine_score(pov(chess.engine.Mate(-1)), black_to_move), -(MATE_SCORE - 1))


class CoachEngineSelectionTests(unittest.TestCase):
    def test_stockfish_is_preferred_and_failures_fall_back_to_the_builtin_engine(self):
        board = chess.Board()
        builtin = ({"best_move": chess.Move.from_uci("e2e4"), "score": 20}, {"analysis_complete": True})
        with patch("api._find_stockfish_path", return_value="/fake/stockfish"), \
                patch("stockfish_coach.coach_analysis", return_value=("sf", "sf-teaching")) as coach, \
                patch.object(api.chess_engine.EngineSession, "analyze", side_effect=AssertionError("must not run")):
            self.assertEqual(api.coach_engine_analysis(board, 5, 4.0, 0.8), ("sf", "sf-teaching"))
            coach.assert_called_once()

        with patch("api._find_stockfish_path", return_value="/fake/stockfish"), \
                patch("stockfish_coach.coach_analysis", side_effect=OSError("broken binary")), \
                patch.object(api.chess_engine.EngineSession, "analyze", return_value=builtin[0]), \
                patch.object(api.chess_engine.EngineSession, "teaching_analysis", return_value=builtin[1]):
            self.assertEqual(api.coach_engine_analysis(board, 5, 4.0, 0.8), builtin)

    def test_builtin_can_be_forced(self):
        with patch.dict(os.environ, {"COACH_ENGINE": "builtin"}), \
                patch("api._find_stockfish_path", side_effect=AssertionError("must not look for Stockfish")), \
                patch.object(api.chess_engine.EngineSession, "analyze", return_value={"best_move": None}), \
                patch.object(api.chess_engine.EngineSession, "teaching_analysis", return_value={}):
            self.assertEqual(api.coach_engine_analysis(chess.Board(), 5, 4.0, 0.8), ({"best_move": None}, {}))


@unittest.skipUnless(STOCKFISH, "Stockfish is not installed")
class RealStockfishTests(unittest.TestCase):
    def test_mate_in_one_is_found_ranked_and_complete(self):
        board = chess.Board(FOOLS_MATE_FEN)
        analysis, teaching = stockfish_coach.coach_analysis(board, STOCKFISH, nodes=50_000, time_limit=2)
        self.assertEqual(board.san(analysis["best_move"]), "Qh4#")
        self.assertEqual(analysis["eval_display"], "-M1")
        self.assertTrue(teaching["analysis_complete"])
        self.assertEqual(teaching["best_move_reason"], "checkmate")
        self.assertEqual(teaching["candidates"][0]["san"], "Qh4#")
        self.assertEqual(len(teaching["candidates"]), 5)
        self.assertIn("misses_mate", teaching["candidates"][1]["warnings"])

    def test_hanging_queen_is_not_recommended_and_capture_is(self):
        board = chess.Board()
        for san in "e4 e5 Nf3 Qh4 d3".split():
            board.push_san(san)
        before = board.fen()
        analysis, teaching = stockfish_coach.coach_analysis(board, STOCKFISH, nodes=50_000, time_limit=2)
        self.assertEqual(board.fen(), before)
        self.assertNotEqual(analysis["best_move"].to_square, chess.H4)  # the queen must move away
        self.assertTrue(all(item["score_status"] == "complete" for item in teaching["candidates"]))


if __name__ == "__main__":
    unittest.main()
