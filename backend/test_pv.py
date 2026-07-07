import unittest

import chess

import chess_engine


class PrincipalVariationTests(unittest.TestCase):
    def test_analysis_returns_legal_principal_variation(self):
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")

        analysis = chess_engine.get_analysis(board, depth=5)
        pv_line = analysis["pv"]

        self.assertIn(analysis["best_move"], board.legal_moves)
        self.assertGreaterEqual(len(pv_line), 1)
        self.assertEqual(chess.Move.from_uci(pv_line[0]), analysis["best_move"])

        temp_board = board.copy()
        for uci_move in pv_line:
            move = chess.Move.from_uci(uci_move)
            self.assertIn(move, temp_board.legal_moves)
            temp_board.push(move)


if __name__ == "__main__":
    unittest.main()
