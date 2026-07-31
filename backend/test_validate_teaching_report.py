import unittest

from validate_teaching_report import validate_report


class TeachingReportValidatorTests(unittest.TestCase):
    def setUp(self):
        self.gate = {
            "equals": {"stockfish_signature": "name=Stockfish 18"},
            "minimum": {"positions": 8, "score": 0.5},
            "maximum": {"error": 100},
            "topic_minimum": {"positional": {"recall_rate": 0.5}},
        }
        self.report = {
            "stockfish_signature": "name=Stockfish 18",
            "positions": 8,
            "score": 0.5,
            "error": 100,
            "by_topic": {"positional": {"recall_rate": 0.5}},
        }

    def test_accepts_metrics_at_the_gate(self):
        self.assertEqual(validate_report(self.report, self.gate), [])

    def test_reports_minimum_and_maximum_regressions(self):
        self.report["score"] = 0.49
        self.report["error"] = 101

        failures = validate_report(self.report, self.gate)

        self.assertEqual(len(failures), 2)
        self.assertIn("score", failures[0])
        self.assertIn("error", failures[1])

    def test_reports_missing_topic_metrics(self):
        self.report["by_topic"] = {}

        failures = validate_report(self.report, self.gate)

        self.assertEqual(
            failures,
            ["by_topic.positional: missing topic metrics"],
        )

    def test_rejects_a_different_stockfish_oracle(self):
        self.report["stockfish_signature"] = "name=Stockfish 19"

        failures = validate_report(self.report, self.gate)

        self.assertEqual(
            failures,
            [
                "stockfish_signature: expected 'name=Stockfish 18', "
                "got 'name=Stockfish 19'"
            ],
        )


if __name__ == "__main__":
    unittest.main()
