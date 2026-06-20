import unittest
from unittest.mock import patch

import chess

import chess_engine


class TricksterSafetyTests(unittest.TestCase):
    def test_rejects_candidate_that_hangs_queen_for_pawn(self):
        board = chess.Board("4k2r/7p/8/7Q/8/8/8/4K3 w - - 0 1")
        blunder = board.parse_san("Qxh7")

        self.assertTrue(chess_engine.major_piece_loss_after_move(board, blunder))

    def test_allows_forced_mate(self):
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        mate = board.parse_san("Qxf7#")

        self.assertFalse(chess_engine.major_piece_loss_after_move(board, mate))

    def test_style_bonus_cannot_select_hanging_queen(self):
        board = chess.Board("4k2r/7p/8/7Q/8/8/8/4K3 w - - 0 1")
        blunder = board.parse_san("Qxh7")
        safe_move = board.parse_san("Qh3")

        with (
            patch("chess_engine.order_moves", return_value=[blunder, safe_move]),
            patch("chess_engine.minimax", return_value=(0, None)),
            patch(
                "chess_engine.score_trickster_move",
                side_effect=lambda _board, move: 500 if move == blunder else 0,
            ),
        ):
            selected, _score, _bonus = chess_engine.select_trickster_move(
                board,
                depth=1,
                best_move=safe_move,
                best_score=0,
            )

        self.assertEqual(selected, safe_move)

    def test_baseline_best_move_is_always_a_style_candidate(self):
        board = chess.Board()
        best_move = board.parse_san("e4")
        ordered_without_best = [move for move in board.legal_moves if move != best_move][:12]

        def fake_minimax(candidate_board, *_args, **_kwargs):
            return (100 if candidate_board.peek() == best_move else 0), None

        with (
            patch("chess_engine.order_moves", return_value=ordered_without_best),
            patch("chess_engine.minimax", side_effect=fake_minimax),
            patch("chess_engine.score_trickster_move", return_value=0),
        ):
            selected, _score, _bonus = chess_engine.select_trickster_move(
                board,
                depth=1,
                best_move=best_move,
                best_score=0,
            )

        self.assertEqual(selected, best_move)


if __name__ == "__main__":
    unittest.main()
