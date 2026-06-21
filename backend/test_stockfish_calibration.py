import unittest

import chess

from stockfish_calibration import POSITIONS


class StockfishCalibrationTests(unittest.TestCase):
    def test_all_calibration_positions_are_valid_and_playable(self):
        self.assertGreaterEqual(len(POSITIONS), 12)
        for position in POSITIONS:
            with self.subTest(position=position.name):
                board = chess.Board(position.fen)
                self.assertTrue(board.is_valid())
                self.assertFalse(board.is_game_over())

if __name__ == "__main__":
    unittest.main()
