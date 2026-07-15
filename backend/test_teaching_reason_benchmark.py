import unittest
from unittest.mock import patch

import teaching_reason_benchmark


class TeachingReasonBenchmarkTests(unittest.TestCase):
    def test_positive_and_false_positive_fixtures_pass_for_both_sides(self):
        report = teaching_reason_benchmark.run()

        self.assertEqual(report["positions"], len(teaching_reason_benchmark.CASES) * 2)
        self.assertEqual(report["failed"], 0)
        self.assertEqual({item["perspective"] for item in report["results"]}, {"white", "black"})

    def test_forbidden_extra_theme_fails_the_benchmark(self):
        case = next(
            case for case in teaching_reason_benchmark.CASES
            if case.name == "defended_rook_capture"
        )
        original = teaching_reason_benchmark.chess_engine._move_themes

        with patch.object(
            teaching_reason_benchmark.chess_engine,
            "_move_themes",
            side_effect=lambda board, move, reason: [*original(board, move, reason), "tactics"],
        ):
            result = teaching_reason_benchmark.evaluate_case(case, "white")

        self.assertFalse(result["passed"])
        self.assertIn("forbidden theme tactics", result["failures"])


if __name__ == "__main__":
    unittest.main()
