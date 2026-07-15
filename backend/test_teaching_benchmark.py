import unittest
from unittest.mock import patch

import chess

import teaching_benchmark


class TeachingBenchmarkTests(unittest.TestCase):
    def test_benchmark_positions_are_valid_and_cover_core_topics(self):
        self.assertGreaterEqual(len(teaching_benchmark.POSITIONS), 8)
        topics = {position.topic for position in teaching_benchmark.POSITIONS}
        self.assertIn("opening", topics)
        self.assertIn("tactics", topics)
        self.assertIn("endgame", topics)
        self.assertIn("mistake_warning", topics)

        for position in teaching_benchmark.POSITIONS:
            with self.subTest(position=position.name):
                board = chess.Board(position.fen)
                self.assertTrue(board.is_valid())
                self.assertFalse(board.is_game_over())

    def test_expected_san_moves_are_legal_and_canonical(self):
        for position in teaching_benchmark.POSITIONS:
            board = chess.Board(position.fen)
            with self.subTest(position=position.name):
                legal_sans = {board.san(move) for move in board.legal_moves}
                self.assertTrue(
                    set(position.expected_best_san).intersection(legal_sans),
                    f"{position.expected_best_san} should contain at least one legal SAN",
                )

    def test_run_position_returns_teaching_expectation_results(self):
        position = teaching_benchmark.POSITIONS_BY_NAME["opening_development"]

        result = teaching_benchmark.run_position(position)

        self.assertEqual(result["name"], "opening_development")
        self.assertTrue(result["structure_valid"])
        self.assertIn("opening_principle", result["position_themes"])
        self.assertIn("development", result["position_themes"])
        self.assertTrue(result["passed"])

    def test_warning_position_detects_hanging_major_piece(self):
        position = teaching_benchmark.POSITIONS_BY_NAME["queen_hang_warning"]

        result = teaching_benchmark.run_position(position)

        self.assertTrue(result["passed"])
        self.assertIn("hangs_major_piece", result["warnings_found"])
        self.assertIn("large_eval_drop", result["warnings_found"])

    def test_run_summary_reports_pass_rate_and_failures(self):
        report = teaching_benchmark.run()

        self.assertEqual(report["positions"], len(teaching_benchmark.POSITIONS))
        self.assertEqual(report["mode"], "structure")
        self.assertIn("pass_rate", report)
        self.assertEqual(report["passed"], report["positions"])
        self.assertIsInstance(report["failures"], list)

    def test_structure_benchmark_rejects_partial_candidate_subset(self):
        position = teaching_benchmark.POSITIONS_BY_NAME["opening_development"]
        partial = {
            "candidates": [{
                "rank": 1,
                "san": "Nf3",
                "score_status": "complete",
                "score_type": "centipawn",
                "loss_cp": 0,
                "warnings": [],
            }],
            "analysis_complete": False,
            "evaluated_candidate_count": 1,
            "requested_candidate_count": 8,
            "position_themes": [],
            "mistake_warnings": [],
            "criticality": "partial",
        }
        with (
            patch.object(teaching_benchmark.chess_engine, "get_analysis", return_value={}),
            patch.object(teaching_benchmark.chess_engine, "get_teaching_analysis", return_value=partial),
        ):
            result = teaching_benchmark.run_position(position)

        self.assertFalse(result["structure_valid"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
