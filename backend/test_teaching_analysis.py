import unittest
from unittest.mock import patch

import chess

import chess_engine


class TeachingAnalysisTests(unittest.TestCase):
    def setUp(self):
        chess_engine.reset_transposition_table()

    def test_candidates_include_and_mark_base_engine_choice(self):
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
        base_candidate = next(item for item in teaching["candidates"] if item["base_engine_choice"])
        self.assertEqual(base_candidate["move"], best_move.uci())
        self.assertEqual(base_candidate["san"], "e4")
        self.assertEqual(teaching["candidates"][0]["loss_cp"], 0)
        self.assertTrue(teaching["analysis_complete"])

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

    def test_rook_and_pawn_endgame_is_classified_as_endgame_not_opening(self):
        board = chess.Board("8/5pk1/6p1/3R4/7P/6P1/5PK1/3r4 w - - 0 1")
        base_analysis = {
            "best_move": board.parse_san("Rd7"),
            "score": 0,
            "depth": 1,
        }

        teaching = chess_engine.get_teaching_analysis(
            board,
            base_analysis,
            candidate_count=8,
            depth=1,
        )

        self.assertIn("endgame", teaching["position_themes"])
        self.assertNotIn("opening_principle", teaching["position_themes"])

    def test_candidates_are_ranked_by_comparable_score_not_base_choice(self):
        board = chess.Board()
        moves = [board.parse_san(san) for san in ("a3", "e4", "d4")]
        scores = {moves[0]: 0, moves[1]: 100, moves[2]: 50}

        with (
            patch.object(chess_engine, "_candidate_moves", return_value=moves),
            patch.object(chess_engine, "_candidate_score", side_effect=lambda child, _depth: scores[child.peek()]),
        ):
            teaching = chess_engine.get_teaching_analysis(
                board, {"best_move": moves[0], "score": 0, "depth": 2}, depth=1
            )

        self.assertEqual([item["san"] for item in teaching["candidates"]], ["e4", "d4", "a3"])
        self.assertEqual([item["loss_cp"] for item in teaching["candidates"]], [0, 50, 100])
        self.assertFalse(teaching["candidates"][0]["base_engine_choice"])
        self.assertTrue(teaching["candidates"][2]["base_engine_choice"])

    def test_black_candidates_use_black_perspective_for_ranking(self):
        board = chess.Board()
        board.push_san("e4")
        moves = [board.parse_san(san) for san in ("a6", "e5", "d5")]
        white_scores = {moves[0]: 100, moves[1]: -100, moves[2]: 0}

        with (
            patch.object(chess_engine, "_candidate_moves", return_value=moves),
            patch.object(chess_engine, "_candidate_score", side_effect=lambda child, _depth: white_scores[child.peek()]),
        ):
            teaching = chess_engine.get_teaching_analysis(
                board, {"best_move": moves[0], "score": 100, "depth": 2}, depth=1
            )

        self.assertEqual([item["san"] for item in teaching["candidates"]], ["e5", "d5", "a6"])
        self.assertEqual([item["loss_cp"] for item in teaching["candidates"]], [0, 100, 200])

    def test_timeout_marks_partial_candidate_comparison(self):
        board = chess.Board()
        moves = [board.parse_san(san) for san in ("e4", "d4")]

        with (
            patch.object(chess_engine, "_candidate_moves", return_value=moves),
            patch.object(chess_engine, "_candidate_score", side_effect=[20, chess_engine.SearchTimeout()]),
        ):
            teaching = chess_engine.get_teaching_analysis(
                board, {"best_move": moves[0], "score": 20, "depth": 2}, depth=1
            )

        self.assertFalse(teaching["analysis_complete"])
        self.assertEqual(teaching["evaluated_candidate_count"], 1)
        self.assertEqual(teaching["requested_candidate_count"], 2)
        self.assertEqual(teaching["candidates"][0]["score_status"], "complete")
        self.assertEqual(teaching["criticality"], "partial")
        self.assertNotIn("only_move", teaching["position_themes"])

    def test_mate_scores_are_not_reported_as_centipawn_loss(self):
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        mate = board.parse_san("Qxf7#")
        quiet = board.parse_san("Qd1")
        scores = {mate: chess_engine.MATE_SCORE - 1, quiet: 0}

        with (
            patch.object(chess_engine, "_candidate_moves", return_value=[quiet, mate]),
            patch.object(chess_engine, "_candidate_score", side_effect=lambda child, _depth: scores[child.peek()]),
        ):
            teaching = chess_engine.get_teaching_analysis(
                board, {"best_move": quiet, "score": 0, "depth": 2}, depth=1
            )

        self.assertEqual(teaching["candidates"][0]["san"], "Qxf7#")
        self.assertEqual(teaching["candidates"][0]["score_type"], "mate")
        self.assertIsNone(teaching["candidates"][0]["loss_cp"])
        self.assertIsNone(teaching["candidates"][1]["loss_cp"])

    def test_timeout_before_first_score_reports_base_only_as_unevaluated(self):
        board = chess.Board()
        base = board.parse_san("e4")
        with (
            patch.object(chess_engine, "_candidate_moves", return_value=[base]),
            patch.object(chess_engine, "_candidate_score", side_effect=chess_engine.SearchTimeout()),
        ):
            teaching = chess_engine.get_teaching_analysis(
                board, {"best_move": base, "score": 20, "depth": 2}, depth=1
            )

        self.assertFalse(teaching["analysis_complete"])
        self.assertEqual(teaching["evaluated_candidate_count"], 0)
        self.assertEqual(teaching["returned_candidate_count"], 1)
        self.assertEqual(teaching["candidates"][0]["score_status"], "base_only")

    def test_equal_non_top_candidate_has_zero_loss_and_near_equal_evidence(self):
        board = chess.Board()
        moves = [board.parse_san(san) for san in ("e4", "d4", "c4")]
        scores = {moves[0]: 50, moves[1]: 50, moves[2]: 0}
        with (
            patch.object(chess_engine, "_candidate_moves", return_value=moves),
            patch.object(chess_engine, "_candidate_score", side_effect=lambda child, _depth: scores[child.peek()]),
        ):
            teaching = chess_engine.get_teaching_analysis(
                board, {"best_move": moves[0], "score": 50, "depth": 2}, depth=1
            )

        self.assertEqual(teaching["candidates"][1]["loss_cp"], 0)
        self.assertTrue(teaching["candidates"][1]["near_equal"])


if __name__ == "__main__":
    unittest.main()
