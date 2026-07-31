import unittest
from unittest.mock import patch

import chess

import chess_engine
from evaluation import (
    CALIBRATED_FEATURE_WEIGHTS,
    EvaluationResult,
    PositionEvaluator,
    endgame_weight_percent,
    get_piece_square_value,
    is_endgame,
    strategic_weight_percent,
)
from evaluation.endgame import mop_up_score
from evaluation.king_activity import king_activity_score
from evaluation.king_safety import (
    contextual_pawn_shelter_for_color,
    contextual_pawn_shelter_score,
    graded_king_safety_for_color,
    graded_king_safety_score,
    king_safety_score,
)
from evaluation.pawn_structure import (
    is_candidate_passed_pawn,
    pawn_structure_for_color,
    pawn_structure_score,
)
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
            "7k/8/5KQ1/8/8/8/8/8 w - - 0 1": 1242,
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
                "piece_square": 60,
                "king_safety": 0,
                "pawn_structure": 0,
                "piece_activity": 0,
                "rook_activity": 0,
                "king_activity": 0,
                "endgame_mop_up": 282,
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

    def test_candidate_passer_requires_enough_neighbor_support(self):
        candidate = chess.Board("7k/8/4p3/2PP4/8/8/8/7K w - - 0 1")
        unsupported = chess.Board("7k/8/2p1p3/3P4/8/8/8/7K w - - 0 1")

        self.assertTrue(is_candidate_passed_pawn(candidate, chess.D5, chess.WHITE))
        self.assertFalse(is_candidate_passed_pawn(unsupported, chess.D5, chess.WHITE))

    def test_blocked_passer_scores_below_free_passer(self):
        free = chess.Board("7k/8/8/4P3/8/8/8/7K w - - 0 1")
        blocked = chess.Board("7k/8/4n3/4P3/8/8/8/7K w - - 0 1")

        self.assertGreater(
            pawn_structure_for_color(free, chess.WHITE),
            pawn_structure_for_color(blocked, chess.WHITE),
        )

    def test_connected_passers_score_above_separated_passers(self):
        connected = chess.Board("7k/8/8/3PP3/8/8/8/7K w - - 0 1")
        separated = chess.Board("7k/8/8/2P2P2/8/8/8/7K w - - 0 1")

        self.assertGreater(
            pawn_structure_for_color(connected, chess.WHITE),
            pawn_structure_for_color(separated, chess.WHITE),
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

    def test_phase_progresses_monotonically_with_material_trades(self):
        board = chess.Board()
        weights = [endgame_weight_percent(board)]

        for square in (chess.D1, chess.D8):
            board.remove_piece_at(square)
        weights.append(endgame_weight_percent(board))
        for square in (chess.A1, chess.H1, chess.A8, chess.H8):
            board.remove_piece_at(square)
        weights.append(endgame_weight_percent(board))
        for square in (
            chess.B1,
            chess.C1,
            chess.F1,
            chess.G1,
            chess.B8,
            chess.C8,
            chess.F8,
            chess.G8,
        ):
            board.remove_piece_at(square)
        weights.append(endgame_weight_percent(board))

        self.assertEqual(weights, [0, 33, 67, 100])

    def test_queenless_full_armies_do_not_cross_an_endgame_cliff(self):
        board = chess.Board()
        board.remove_piece_at(chess.D1)
        board.remove_piece_at(chess.D8)

        self.assertEqual(endgame_weight_percent(board), 33)
        self.assertFalse(is_endgame(board))

    def test_king_piece_square_value_interpolates_at_midphase(self):
        opening = get_piece_square_value(chess.KING, chess.E4, chess.WHITE, 0)
        midpoint = get_piece_square_value(chess.KING, chess.E4, chess.WHITE, 50)
        endgame = get_piece_square_value(chess.KING, chess.E4, chess.WHITE, 100)

        self.assertEqual(midpoint, round((opening + endgame) / 2))

    def test_king_safety_and_mop_up_taper_in_opposite_directions(self):
        exposed_king = chess.Board(
            "rnbqkbnr/pppppppp/8/8/4K3/8/PPPPPPPP/RNBQ1BNR b kq - 0 1"
        )
        raw_safety = king_safety_score(exposed_king, 0)
        self.assertEqual(king_safety_score(exposed_king, 50), round(raw_safety / 2))
        self.assertEqual(king_safety_score(exposed_king, 100), 0)

        winning_endgame = chess.Board("7k/8/5KQ1/8/8/8/8/8 w - - 0 1")
        raw_mop_up = mop_up_score(winning_endgame, 900, 100)
        self.assertEqual(mop_up_score(winning_endgame, 900, 50), round(raw_mop_up / 2))
        self.assertEqual(mop_up_score(winning_endgame, 900, 0), 0)

    def test_only_benchmarked_features_are_enabled_by_default(self):
        self.assertEqual(
            dict(CALIBRATED_FEATURE_WEIGHTS),
            {
                "pawn_structure": 0,
                "piece_activity": 0,
                "rook_activity": 0,
                "king_activity": 100,
                "king_safety_blend": 0,
                "quiet_pawn_shelter": 0,
            },
        )

    def test_experimental_feature_can_be_enabled_without_engine_rewrite(self):
        board = chess.Board("7k/8/8/3N4/2P5/8/8/7K w - - 0 1")
        evaluator = PositionEvaluator({"piece_activity": 100})

        result = evaluator.evaluate(board)

        self.assertGreater(result.components["piece_activity"], 0)
        self.assertEqual(sum(result.components.values()), result.score)

    def test_middlegame_activity_is_not_zeroed_by_endgame_phase(self):
        board = chess.Board()
        board.remove_piece_at(chess.B1)
        board.remove_piece_at(chess.C1)
        board.set_piece_at(chess.D5, chess.Piece(chess.KNIGHT, chess.WHITE))
        board.set_piece_at(chess.G5, chess.Piece(chess.BISHOP, chess.WHITE))
        self.assertEqual(endgame_weight_percent(board), 0)

        result = PositionEvaluator({"piece_activity": 100}).evaluate(board)

        self.assertNotEqual(result.components["piece_activity"], 0)

    def test_strategic_features_have_distinct_continuous_phase_profiles(self):
        opening_board = chess.Board()
        developed_board = chess.Board()
        for square in (
            chess.B1, chess.G1, chess.C1, chess.F1,
            chess.B8, chess.G8, chess.C8, chess.F8,
        ):
            developed_board.remove_piece_at(square)
        opening = PositionEvaluator._feature_phase_weights(opening_board, 0)
        developed = PositionEvaluator._feature_phase_weights(developed_board, 0)
        endgame = PositionEvaluator._feature_phase_weights(developed_board, 100)

        self.assertEqual(opening, {
            "pawn_structure": 100,
            "piece_activity": 0,
            "rook_activity": 50,
            "king_activity": 0,
            "king_safety_blend": 0,
        })
        self.assertEqual(developed, {
            "pawn_structure": 100,
            "piece_activity": 100,
            "rook_activity": 50,
            "king_activity": 0,
            "king_safety_blend": 100,
        })
        self.assertEqual(endgame, {
            "pawn_structure": 100,
            "piece_activity": 50,
            "rook_activity": 100,
            "king_activity": 100,
            "king_safety_blend": 0,
        })

    def test_zero_weight_features_are_not_computed_in_search(self):
        board = chess.Board("8/8/4k3/8/4P3/4K3/8/8 w - - 0 1")

        with (
            patch(
                "evaluation.evaluator.piece_activity_score",
                side_effect=AssertionError("disabled piece feature was evaluated"),
            ),
            patch(
                "evaluation.evaluator.pawn_structure_score",
                side_effect=AssertionError("disabled pawn feature was evaluated"),
            ),
            patch(
                "evaluation.evaluator.rook_activity_score",
                side_effect=AssertionError("disabled rook feature was evaluated"),
            ),
        ):
            result = self.evaluator.evaluate(board)

        self.assertNotEqual(result.components["king_activity"], 0)

    def test_graded_king_safety_values_pawn_shield_and_closed_files(self):
        shielded = chess.Board()
        exposed = shielded.copy(stack=False)
        exposed.remove_piece_at(chess.F2)
        exposed.remove_piece_at(chess.G2)
        exposed.remove_piece_at(chess.H2)

        self.assertGreater(
            graded_king_safety_for_color(shielded, chess.WHITE),
            graded_king_safety_for_color(exposed, chess.WHITE),
        )

    def test_graded_king_exposure_changes_gradually(self):
        home = chess.Board()
        second_rank = home.copy(stack=False)
        second_rank.remove_piece_at(chess.E1)
        second_rank.remove_piece_at(chess.E2)
        second_rank.set_piece_at(chess.E2, chess.Piece(chess.KING, chess.WHITE))
        third_rank = second_rank.copy(stack=False)
        third_rank.remove_piece_at(chess.E2)
        third_rank.set_piece_at(chess.E3, chess.Piece(chess.KING, chess.WHITE))

        scores = [
            graded_king_safety_for_color(board, chess.WHITE)
            for board in (home, second_rank, third_rank)
        ]
        self.assertGreater(scores[0], scores[1])
        self.assertGreater(scores[1], scores[2])
        self.assertLess(scores[0] - scores[1], 180)

    def test_graded_king_safety_is_color_symmetric_and_tapered(self):
        board = chess.Board(
            "r3k2r/ppp2ppp/2n5/3qp3/8/2N2N2/PPP2PPP/R3K2R w KQkq - 0 1"
        )
        mirrored = board.mirror()

        self.assertEqual(
            graded_king_safety_score(board, 25),
            -graded_king_safety_score(mirrored, 25),
        )
        self.assertEqual(graded_king_safety_score(board, 100), 0)

    def test_contextual_shelter_scales_with_enemy_heavy_pieces(self):
        exposed = chess.Board(
            "3q1rk1/ppp2ppp/8/8/8/8/PPP5/3Q1RK1 w - - 0 1"
        )
        no_heavy_pieces = chess.Board(
            "6k1/ppp2ppp/8/8/8/8/PPP5/6K1 w - - 0 1"
        )

        self.assertLess(
            contextual_pawn_shelter_for_color(exposed, chess.WHITE),
            contextual_pawn_shelter_for_color(exposed, chess.BLACK),
        )
        self.assertEqual(
            contextual_pawn_shelter_score(no_heavy_pieces, 0),
            0,
        )
        self.assertEqual(contextual_pawn_shelter_score(exposed, 100), 0)

    def test_contextual_shelter_is_only_added_to_quiet_leaf_score(self):
        board = chess.Board(
            "3q1rk1/ppp2ppp/8/8/8/8/PPP5/3Q1RK1 w - - 0 1"
        )
        evaluator = PositionEvaluator({"quiet_pawn_shelter": 100})

        ordinary = evaluator.score_nonterminal(board)
        quiet = evaluator.score_quiet_nonterminal(board)

        self.assertLess(quiet, ordinary)
        self.assertEqual(evaluator.evaluate(board).score, ordinary)



if __name__ == "__main__":
    unittest.main()
