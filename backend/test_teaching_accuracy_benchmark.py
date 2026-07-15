import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import chess

import teaching_accuracy_benchmark
from teaching_accuracy_benchmark import (
    DEFAULT_RELEASE_NODES,
    DEFAULT_SMOKE_NODES,
    POSITIONS,
    PROFILE_RELEASE,
    PROFILE_SMOKE,
    StockfishOracleCache,
    accuracy_gate,
    candidate_consistency,
    inversion_rate,
    profile_search_settings,
    select_positions,
)


class TeachingAccuracyBenchmarkTests(unittest.TestCase):
    @staticmethod
    def gate(**overrides):
        values = {
            "top3_rate": 1.0,
            "recall_rate": 1.0,
            "inversion": 0.0,
            "completion_rate": 1.0,
            "mean_loss_error_cp": 0,
            "mate_type_rate": 1.0,
            "only_move_precision": 1.0,
            "only_move_recall": 1.0,
            "loss_field_rate": 1.0,
            "max_position_loss_mae_cp": 0,
            "position_count": 20,
            "min_topic_top3_rate": 1.0,
            "min_topic_recall_rate": 1.0,
        }
        values.update(overrides)
        return accuracy_gate(**values)

    def test_inversion_rate_ignores_near_equal_scores(self):
        self.assertEqual(inversion_rate([100, 90, 80]), 0)

    def test_inversion_rate_counts_later_materially_better_scores(self):
        self.assertAlmostEqual(inversion_rate([0, 100, 50], tolerance_cp=20), 2 / 3)

    def test_release_corpus_is_broad_valid_and_balanced(self):
        self.assertGreaterEqual(len(POSITIONS), 20)
        topic_counts = {}
        for position in POSITIONS:
            board = chess.Board(position.fen)
            self.assertTrue(board.is_valid(), position.name)
            self.assertFalse(board.is_game_over(), position.name)
            topic_counts[position.topic] = topic_counts.get(position.topic, 0) + 1
        self.assertEqual(set(topic_counts), {"opening", "tactics", "positional", "endgame"})
        self.assertTrue(all(count >= 5 for count in topic_counts.values()))

    def test_smoke_profile_is_balanced_and_reduces_search_work(self):
        positions = select_positions(PROFILE_SMOKE)

        self.assertEqual(len(positions), 8)
        self.assertEqual(
            {position.topic for position in positions},
            {"opening", "tactics", "positional", "endgame"},
        )
        for position in positions:
            settings = profile_search_settings(position, PROFILE_SMOKE)
            self.assertLessEqual(settings["depth"], 2)
            self.assertLessEqual(settings["candidate_count"], 3)
            self.assertFalse(settings["adaptive_depth"])

    def test_topic_filter_keeps_all_positions_in_requested_topic(self):
        selected = select_positions(PROFILE_SMOKE, ["positional"])

        self.assertEqual(
            selected,
            tuple(position for position in POSITIONS if position.topic == "positional"),
        )

    def test_oracle_cache_round_trip_and_query_invalidation(self):
        query = {
            "engine": "Stockfish 18",
            "fen": chess.STARTING_FEN,
            "nodes": 10_000,
            "kind": "forced_move",
            "multipv": None,
            "move": "e2e4",
            "score_perspective": "side_to_move",
            "mate_score": 100_000,
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.json"
            cache = StockfishOracleCache(path)
            self.assertIsNone(cache.get(query))
            cache.set(query, 32)
            cache.save()

            reloaded = StockfishOracleCache(path)
            self.assertEqual(reloaded.get(query), 32)
            changed_nodes = {**query, "nodes": 50_000}
            self.assertIsNone(reloaded.get(changed_nodes))
            changed_engine = {**query, "engine": "Stockfish 19"}
            self.assertIsNone(reloaded.get(changed_engine))
            changed_fen = {
                **query,
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            }
            self.assertIsNone(reloaded.get(changed_fen))
            changed_move = {**query, "move": "d2d4"}
            self.assertIsNone(reloaded.get(changed_move))

    def test_refresh_cache_bypasses_existing_entry(self):
        query = {"kind": "top_lines", "nodes": 10_000}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "oracle.json"
            cache = StockfishOracleCache(path)
            cache.set(query, {"moves": ["e2e4"], "scores": [20]})
            cache.save()

            refreshed = StockfishOracleCache(path, refresh=True)
            self.assertIsNone(refreshed.get(query))
            self.assertEqual(refreshed.stats()["misses"], 1)

    def test_accuracy_gate_rejects_partial_candidate_analysis(self):
        self.assertFalse(self.gate(completion_rate=0.99))
        self.assertTrue(self.gate())

    def test_accuracy_gate_rejects_bogus_loss_type_and_criticality(self):
        self.assertFalse(self.gate(mean_loss_error_cp=101))
        self.assertFalse(self.gate(mate_type_rate=0.99))
        self.assertFalse(self.gate(only_move_precision=0.94))
        self.assertFalse(self.gate(only_move_recall=0.89))
        self.assertFalse(self.gate(max_position_loss_mae_cp=201))

    def test_release_gate_requires_broad_and_balanced_coverage(self):
        self.assertFalse(self.gate(position_count=19))
        self.assertFalse(self.gate(top3_rate=0.89))
        self.assertFalse(self.gate(recall_rate=0.89))
        self.assertFalse(self.gate(min_topic_top3_rate=0.79))
        self.assertFalse(self.gate(min_topic_recall_rate=0.79))
        self.assertFalse(self.gate(inversion=0.151))

    def test_cli_only_fails_when_release_gate_is_explicitly_required(self):
        report = {"release_ready": False, "passed": False}
        with (
            patch.object(teaching_accuracy_benchmark, "find_stockfish", return_value="/fake/stockfish"),
            patch.object(teaching_accuracy_benchmark, "run", return_value=report),
            patch("sys.argv", ["benchmark", "--json"]),
        ):
            self.assertEqual(teaching_accuracy_benchmark.main(), 0)
        with (
            patch.object(teaching_accuracy_benchmark, "find_stockfish", return_value="/fake/stockfish"),
            patch.object(teaching_accuracy_benchmark, "run", return_value=report),
            patch("sys.argv", ["benchmark", "--json", "--require-release-ready"]),
        ):
            self.assertEqual(teaching_accuracy_benchmark.main(), 1)

    def test_cli_profile_selects_default_node_budget(self):
        report = {"release_ready": False, "passed": False}
        with (
            patch.object(teaching_accuracy_benchmark, "find_stockfish", return_value="/fake/stockfish"),
            patch.object(teaching_accuracy_benchmark, "run", return_value=report) as run,
            patch("sys.argv", ["benchmark", "--profile", "smoke", "--json"]),
        ):
            self.assertEqual(teaching_accuracy_benchmark.main(), 0)
        self.assertEqual(run.call_args.kwargs["nodes"], DEFAULT_SMOKE_NODES)
        self.assertEqual(run.call_args.kwargs["profile"], PROFILE_SMOKE)

        with (
            patch.object(teaching_accuracy_benchmark, "find_stockfish", return_value="/fake/stockfish"),
            patch.object(teaching_accuracy_benchmark, "run", return_value=report) as run,
            patch("sys.argv", ["benchmark", "--json"]),
        ):
            self.assertEqual(teaching_accuracy_benchmark.main(), 0)
        self.assertEqual(run.call_args.kwargs["nodes"], DEFAULT_RELEASE_NODES)
        self.assertEqual(run.call_args.kwargs["profile"], PROFILE_RELEASE)

    def test_candidate_consistency_rejects_missing_cp_loss_and_non_top_fake_mate(self):
        missing = candidate_consistency(
            [{"score_type": "centipawn", "loss_cp": None}] * 3,
            [100, 50, 0],
        )
        self.assertFalse(missing["loss_fields_complete"])
        fake_mate = candidate_consistency(
            [
                {"score_type": "centipawn", "loss_cp": 0},
                {"score_type": "mate", "loss_cp": None},
            ],
            [100, 0],
        )
        self.assertFalse(fake_mate["type_matches"])


if __name__ == "__main__":
    unittest.main()
