import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import chess

from stockfish_calibration import (
    CalibrationConfig,
    POSITIONS,
    limit_positions_per_phase,
    load_corpus_positions,
    move_loss_metrics,
    override_configs,
    parse_feature_weights,
)


class StockfishCalibrationTests(unittest.TestCase):
    def test_all_calibration_positions_are_valid_and_playable(self):
        self.assertGreaterEqual(len(POSITIONS), 12)
        for position in POSITIONS:
            with self.subTest(position=position.name):
                board = chess.Board(position.fen)
                self.assertTrue(board.is_valid())
                self.assertFalse(board.is_game_over())

    def test_same_played_move_as_stockfish_best_has_no_loss(self):
        move = chess.Move.from_uci("g5f7")

        metrics = move_loss_metrics(
            best_move=move,
            played_move=move,
            best_score=78,
            played_score=7,
            best_expectation=0.74,
            played_expectation=0.48,
        )

        self.assertEqual(metrics["loss_cp"], 0)
        self.assertEqual(metrics["expectation_loss"], 0)

    def test_external_corpus_can_be_filtered_by_game_split(self):
        payload = {
            "schema_version": 1,
            "positions": [
                {
                    "name": "train",
                    "fen": chess.STARTING_FEN,
                    "topic": "opening",
                    "split": "train",
                },
                {
                    "name": "test",
                    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                    "topic": "opening",
                    "split": "test",
                },
            ],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            positions = load_corpus_positions(path, ["test"])

        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].name, "test")

    def test_phase_limit_is_balanced_and_validated(self):
        limited = limit_positions_per_phase(POSITIONS, 2)
        counts = {}
        for position in limited:
            counts[position.phase] = counts.get(position.phase, 0) + 1
        self.assertTrue(all(count <= 2 for count in counts.values()))
        with self.assertRaises(ValueError):
            limit_positions_per_phase(POSITIONS, 0)

    def test_config_overrides_are_explicit_and_validated(self):
        overridden = override_configs(
            (CalibrationConfig("advanced", 5, 1.5, True, True),),
            depth=6,
            time_limit=3.0,
        )
        self.assertEqual(overridden[0].depth, 6)
        self.assertEqual(overridden[0].time_limit, 3.0)
        with self.assertRaises(ValueError):
            override_configs((), depth=0)

    def test_feature_weight_overrides_are_explicit_and_validated(self):
        self.assertEqual(
            parse_feature_weights(["quiet_pawn_shelter=100"]),
            {"quiet_pawn_shelter": 100},
        )
        with self.assertRaises(ValueError):
            parse_feature_weights(["unknown=100"])
        with self.assertRaises(ValueError):
            parse_feature_weights(["quiet_pawn_shelter=201"])

if __name__ == "__main__":
    unittest.main()
