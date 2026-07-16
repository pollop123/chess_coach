import unittest
from unittest.mock import patch

import chess

import chess_engine
from evaluation import (
    CALIBRATED_FEATURE_WEIGHTS,
    EvaluationResult,
    PositionEvaluator,
    strategic_weight_percent,
)
from evaluation.king_activity import king_activity_score
from evaluation.pawn_structure import pawn_structure_for_color, pawn_structure_score
from evaluation.piece_activity import piece_activity_for_color, piece_activity_score
from evaluation.rook_activity import rook_activity_for_color, rook_activity_score


class PositionEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = PositionEvaluator()

    def test_enriched_score_snapshots_are_stable(self):
        positions = {
            chess.STARTING_FEN: 0,
            "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 w kq - 4 5": -55,
            "rnbqkbnr/pppppppp/8/8/4K3/8/PPPPPPPP/RNBQ1BNR b kq - 0 1": -320,
            "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1": 123,
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
                "pawn_structure": 0,
                "piece_activity": 0,
                "rook_activity": 0,
                "king_activity": 0,
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

    def test_doubled_and_isolated_pawns_score_below_connected_pawns(self):
        healthy = chess.Board("7k/pp6/8/8/8/8/2PP4/7K w - - 0 1")
        damaged = chess.Board("7k/pp6/8/8/8/2P5/2P5/7K w - - 0 1")

        self.assertEqual(pawn_structure_for_color(healthy, chess.WHITE), 0)
        self.assertLess(
            pawn_structure_for_color(damaged, chess.WHITE),
            pawn_structure_for_color(healthy, chess.WHITE),
        )

    def test_supported_knight_outpost_receives_activity_bonus(self):
        outpost = chess.Board("7k/8/8/3N4/2P5/8/8/7K w - - 0 1")
        challengeable = chess.Board("7k/8/4p3/3N4/2P5/8/8/7K w - - 0 1")

        self.assertEqual(piece_activity_for_color(outpost, chess.WHITE), 40)
        self.assertEqual(piece_activity_for_color(challengeable, chess.WHITE), 24)

    def test_rook_prefers_open_file_to_own_pawn_blockage(self):
        open_file = chess.Board("7k/7p/8/8/8/8/8/R6K w - - 0 1")
        blocked_file = chess.Board("7k/7p/8/8/8/8/P7/R6K w - - 0 1")

        self.assertGreater(
            rook_activity_for_color(open_file, chess.WHITE),
            rook_activity_for_color(blocked_file, chess.WHITE),
        )

    def test_direct_opposition_favors_side_not_to_move(self):
        white_to_move = chess.Board("8/8/4k3/8/4K3/8/P7/8 w - - 0 1")
        black_to_move = chess.Board("8/8/4k3/8/4K3/8/P7/8 b - - 0 1")

        self.assertLess(king_activity_score(white_to_move, True), 0)
        self.assertGreater(king_activity_score(black_to_move, True), 0)

    def test_pawn_between_kings_is_not_direct_opposition(self):
        white_to_move = chess.Board("8/8/4k3/4P3/4K3/8/8/8 w - - 0 1")
        black_to_move = chess.Board("8/8/4k3/4P3/4K3/8/8/8 b - - 0 1")

        self.assertEqual(
            king_activity_score(white_to_move, True),
            king_activity_score(black_to_move, True),
        )

    def test_strategic_components_negate_when_colors_are_mirrored(self):
        board = chess.Board(
            "4k2r/pp3ppp/2n5/3pP3/3P4/2N5/PP3PPP/R3K3 w Qk - 0 1"
        )
        mirrored = board.mirror()
        scorers = (
            pawn_structure_score,
            piece_activity_score,
            rook_activity_score,
            lambda position: king_activity_score(position, True),
        )

        for scorer in scorers:
            with self.subTest(scorer=scorer):
                self.assertEqual(scorer(board), -scorer(mirrored))

    def test_strategic_terms_taper_in_as_material_leaves_board(self):
        opening = chess.Board()
        endgame = chess.Board("8/8/4k3/8/4P3/4K3/8/8 w - - 0 1")

        self.assertEqual(strategic_weight_percent(opening), 0)
        self.assertEqual(strategic_weight_percent(endgame), 100)

    def test_only_benchmarked_feature_is_enabled_by_default(self):
        self.assertEqual(
            dict(CALIBRATED_FEATURE_WEIGHTS),
            {
                "pawn_structure": 0,
                "piece_activity": 0,
                "rook_activity": 0,
                "king_activity": 100,
            },
        )

    def test_experimental_feature_can_be_enabled_without_engine_rewrite(self):
        board = chess.Board("7k/8/8/3N4/2P5/8/8/7K w - - 0 1")
        evaluator = PositionEvaluator({"piece_activity": 100})

        result = evaluator.evaluate(board)

        self.assertGreater(result.components["piece_activity"], 0)
        self.assertEqual(sum(result.components.values()), result.score)

    def test_zero_weight_features_are_not_computed_in_search(self):
        board = chess.Board("8/8/4k3/8/4P3/4K3/8/8 w - - 0 1")

        with (
            patch(
                "evaluation.evaluator.pawn_structure_score",
                side_effect=AssertionError("disabled pawn feature was evaluated"),
            ),
            patch(
                "evaluation.evaluator.piece_activity_score",
                side_effect=AssertionError("disabled piece feature was evaluated"),
            ),
            patch(
                "evaluation.evaluator.rook_activity_score",
                side_effect=AssertionError("disabled rook feature was evaluated"),
            ),
        ):
            result = self.evaluator.evaluate(board)

        self.assertNotEqual(result.components["king_activity"], 0)


if __name__ == "__main__":
    unittest.main()
