import unittest

import chess

import chess_engine
from evaluation import EvaluationResult, PositionEvaluator


class PositionEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = PositionEvaluator()

    def test_legacy_score_snapshots_are_preserved(self):
        positions = {
            chess.STARTING_FEN: 0,
            "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w kq - 4 5": -55,
            "rnbqkbnr/pppppppp/8/8/4K3/8/PPPPPPPP/RNBQ1BNR b kq - 0 1": -320,
            "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1": 120,
            "7k/8/5KQ1/8/8/8/8/8 w - - 0 1": 1310,
        }

        for fen, expected in positions.items():
            with self.subTest(fen=fen):
                board = chess.Board(fen)
                self.assertEqual(self.evaluator.score(board), expected)
                self.assertEqual(chess_engine.evaluate_board(board), expected)

    def test_result_exposes_additive_components(self):
        board = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")

        result = self.evaluator.evaluate(board)

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.phase, "endgame")
        self.assertFalse(result.terminal)
        self.assertEqual(
            dict(result.components),
            {
                "material": 900,
                "piece_square": 70,
                "king_safety": 0,
                "endgame_mop_up": 340,
            },
        )
        self.assertEqual(sum(result.components.values()), result.score)

    def test_terminal_scores_preserve_mate_distance(self):
        checkmate = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
        stalemate = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

        mate_result = self.evaluator.evaluate(checkmate, ply_from_root=3)
        draw_result = self.evaluator.evaluate(stalemate)

        self.assertTrue(mate_result.terminal)
        self.assertEqual(mate_result.phase, "terminal")
        self.assertEqual(mate_result.score, chess_engine.MATE_SCORE - 3)
        self.assertEqual(dict(mate_result.components), {"terminal": mate_result.score})
        self.assertTrue(draw_result.terminal)
        self.assertEqual(draw_result.score, 0)

    def test_repetition_policy_remains_visible_and_score_preserving(self):
        board = chess.Board()
        board.remove_piece_at(chess.D8)
        for san in ("Nf3", "Nf6", "Ng1", "Ng8"):
            board.push_san(san)

        result = self.evaluator.evaluate(board)

        self.assertTrue(board.is_repetition(2))
        self.assertEqual(result.score, -1000)
        self.assertIn("repetition_policy", result.components)
        self.assertEqual(sum(result.components.values()), result.score)

    def test_engine_compatibility_entrypoint_returns_breakdown(self):
        board = chess.Board()

        result = chess_engine.evaluate_position(board)

        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.score, chess_engine.evaluate_board(board))


if __name__ == "__main__":
    unittest.main()
