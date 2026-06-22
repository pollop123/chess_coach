import math
import time
import unittest

import chess

import chess_engine


class TranspositionTableTests(unittest.TestCase):
    def setUp(self):
        chess_engine.reset_transposition_table()
        chess_engine.begin_search_generation()

    def test_deeper_exact_entry_answers_shallower_search(self):
        board = chess.Board()
        deep_score, deep_move = chess_engine.minimax(
            board, 2, -math.inf, math.inf, True
        )
        nodes_after_deep_search = chess_engine.search_stats["nodes"]

        shallow_score, shallow_move = chess_engine.minimax(
            board, 1, -math.inf, math.inf, True
        )

        self.assertEqual(shallow_score, deep_score)
        self.assertEqual(shallow_move, deep_move)
        self.assertEqual(chess_engine.search_stats["nodes"], nodes_after_deep_search + 1)
        self.assertGreater(chess_engine.search_stats["tt_cutoffs"], 0)

    def test_bound_entry_is_not_treated_as_exact(self):
        board = chess.Board()
        chess_engine.minimax(board, 2, -10, 10, True)

        cached_score, cached_move = chess_engine.minimax(
            board, 2, -math.inf, math.inf, True
        )

        chess_engine.reset_transposition_table()
        chess_engine.begin_search_generation()
        fresh_score, fresh_move = chess_engine.minimax(
            board, 2, -math.inf, math.inf, True
        )

        self.assertEqual((cached_score, cached_move), (fresh_score, fresh_move))

    def test_mate_scores_are_normalized_across_root_ply(self):
        score = chess_engine.MATE_SCORE - 5

        stored = chess_engine.score_to_tt(score, ply_from_root=3)

        self.assertEqual(chess_engine.score_from_tt(stored, ply_from_root=7), score - 4)

    def test_timeout_restores_board_after_recursive_push(self):
        board = chess.Board()
        original_fen = board.fen()
        chess_engine.search_stats["nodes"] = 62
        chess_engine.search_runtime.deadline = 0

        with self.assertRaises(chess_engine.SearchTimeout):
            chess_engine.minimax(board, 3, -math.inf, math.inf, True)

        self.assertEqual(board.fen(), original_fen)

    def test_timed_search_returns_last_complete_iteration(self):
        board = chess.Board()
        original_fen = board.fen()
        started = time.perf_counter()

        result = chess_engine.get_analysis(
            board,
            depth=8,
            time_limit=0.05,
            use_book=False,
            adaptive_depth=False,
            difficulty="advanced",
        )

        self.assertLess(time.perf_counter() - started, 0.25)
        self.assertIn(result["best_move"], board.legal_moves)
        self.assertEqual(board.fen(), original_fen)


if __name__ == "__main__":
    unittest.main()
