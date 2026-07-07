import unittest

import chess

import chess_engine


class TeachingAnalysisTests(unittest.TestCase):
    def setUp(self):
        chess_engine.reset_transposition_table()

    def test_candidates_include_best_move_with_zero_loss(self):
        board = chess.Board()
        best_move = chess.Move.from_uci("e2e4")
        base_analysis = {
            "best_move": best_move,
            "score": 25,
            "depth": 2,
        }

        teaching = chess_engine.get_teaching_analysis(
            board,
            base_analysis,
            candidate_count=4,
            depth=1,
        )

        self.assertGreaterEqual(len(teaching["candidates"]), 1)
        self.assertEqual(teaching["candidates"][0]["move"], best_move.uci())
        self.assertEqual(teaching["candidates"][0]["san"], "e4")
        self.assertEqual(teaching["candidates"][0]["loss_cp"], 0)

    def test_teaching_analysis_does_not_mutate_board(self):
        board = chess.Board()
        original_fen = board.fen()
        base_analysis = {
            "best_move": chess.Move.from_uci("e2e4"),
            "score": 25,
            "depth": 2,
        }

        chess_engine.get_teaching_analysis(board, base_analysis, depth=1)

        self.assertEqual(board.fen(), original_fen)

    def test_hanging_major_piece_candidate_gets_warning(self):
        board = chess.Board("7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1")
        base_analysis = {
            "best_move": board.parse_san("Qh3"),
            "score": 0,
            "depth": 1,
        }

        teaching = chess_engine.get_teaching_analysis(
            board,
            base_analysis,
            candidate_count=40,
            depth=1,
        )

        hanging = next(item for item in teaching["candidates"] if item["san"].startswith("Qxh7"))
        self.assertIn("hangs_major_piece", hanging["warnings"])
        self.assertIn("large_eval_drop", hanging["warnings"])

    def test_mate_in_one_gets_checkmate_reason_and_tactics_theme(self):
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        base_analysis = {
            "best_move": board.parse_san("Qxf7#"),
            "score": chess_engine.MATE_SCORE - 1,
            "depth": 2,
        }

        teaching = chess_engine.get_teaching_analysis(
            board,
            base_analysis,
            candidate_count=5,
            depth=1,
        )

        self.assertEqual(teaching["best_move_reason"], "checkmate")
        self.assertIn("tactics", teaching["position_themes"])
        self.assertIn("only_move", teaching["position_themes"])
        self.assertEqual(teaching["criticality"], "only_move")

    def test_opening_development_move_gets_development_theme(self):
        board = chess.Board()
        base_analysis = {
            "best_move": chess.Move.from_uci("g1f3"),
            "score": 20,
            "depth": 1,
        }

        teaching = chess_engine.get_teaching_analysis(
            board,
            base_analysis,
            candidate_count=4,
            depth=1,
        )

        best = teaching["candidates"][0]
        self.assertIn("opening_principle", best["themes"])
        self.assertIn("development", best["themes"])
        self.assertIn("development", teaching["position_themes"])


if __name__ == "__main__":
    unittest.main()
