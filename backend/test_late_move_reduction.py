import math
import unittest

import chess

import chess_engine


class LateMoveReductionTests(unittest.TestCase):
    FEN = "r1bqk2r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 5 5"

    def _search(self, use_lmr):
        board = chess.Board(self.FEN)
        chess_engine.reset_transposition_table()
        chess_engine.begin_search_generation()
        result = chess_engine.minimax(
            board,
            4,
            -math.inf,
            math.inf,
            board.turn == chess.WHITE,
            repetition_counts=chess_engine.build_repetition_counts(board),
            use_lmr=use_lmr,
        )
        return result, dict(chess_engine.search_stats)

    def test_conservative_lmr_preserves_result_and_reduces_nodes(self):
        baseline, baseline_stats = self._search(False)
        reduced, reduced_stats = self._search(True)

        self.assertEqual(reduced, baseline)
        self.assertGreater(reduced_stats["lmr_reductions"], 0)
        self.assertLess(reduced_stats["nodes"], baseline_stats["nodes"])

    def test_tactical_and_early_moves_are_not_reduced(self):
        board = chess.Board()
        early_quiet = chess.Move.from_uci("g1f3")
        self.assertFalse(chess_engine.can_late_move_reduce(board, early_quiet, 4, 3))

        tactical_board = chess.Board(
            "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
        )
        capture = chess.Move.from_uci("e8f7")
        self.assertTrue(tactical_board.is_capture(capture))
        self.assertFalse(chess_engine.can_late_move_reduce(tactical_board, capture, 4, 5))


if __name__ == "__main__":
    unittest.main()
