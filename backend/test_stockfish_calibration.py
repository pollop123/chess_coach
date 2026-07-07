import unittest

import chess

from stockfish_calibration import POSITIONS, move_loss_metrics


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

if __name__ == "__main__":
    unittest.main()
