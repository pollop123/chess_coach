import unittest
from unittest.mock import patch

import chess

import chess_engine


class TricksterSafetyTests(unittest.TestCase):
    def test_difficulty_profiles_choose_distinct_loss_bands(self):
        board = chess.Board()
        moves = {
            "best": board.parse_san("e4"),
            "intermediate": board.parse_san("d4"),
            "beginner": board.parse_san("Nf3"),
            "newbie": board.parse_san("c4"),
        }
        scores = {
            moves["best"]: 100,
            moves["intermediate"]: 40,
            moves["beginner"]: -40,
            moves["newbie"]: -120,
        }

        def fake_minimax(candidate_board, *_args, **_kwargs):
            return scores[candidate_board.peek()], None

        expected = {
            "newbie": moves["newbie"],
            "beginner": moves["beginner"],
            "intermediate": moves["intermediate"],
            "advanced": moves["best"],
        }

        with (
            patch("chess_engine.order_moves", return_value=list(moves.values())),
            patch("chess_engine.minimax", side_effect=fake_minimax),
            patch("chess_engine.major_piece_loss_after_move", return_value=False),
            patch("chess_engine.should_apply_difficulty_error", return_value=True),
        ):
            for difficulty, expected_move in expected.items():
                with self.subTest(difficulty=difficulty):
                    selected, _score, _bonus, _loss = chess_engine.select_difficulty_move(
                        board,
                        depth=1,
                        best_move=moves["best"],
                        best_score=100,
                        difficulty=difficulty,
                        style="balanced",
                    )
                    self.assertEqual(selected, expected_move)

    def test_partial_candidate_results_survive_timeout(self):
        board = chess.Board()
        best_move = board.parse_san("e4")
        target_move = board.parse_san("d4")
        unfinished_move = board.parse_san("Nf3")

        with (
            patch(
                "chess_engine.order_moves",
                return_value=[best_move, target_move, unfinished_move],
            ),
            patch(
                "chess_engine.minimax",
                side_effect=[(100, None), (40, None), chess_engine.SearchTimeout()],
            ),
            patch("chess_engine.major_piece_loss_after_move", return_value=False),
            patch("chess_engine.should_apply_difficulty_error", return_value=True),
        ):
            selected, _score, _bonus, loss = chess_engine.select_difficulty_move(
                board,
                depth=2,
                best_move=best_move,
                best_score=100,
                difficulty="intermediate",
                style="balanced",
            )

        self.assertEqual(selected, target_move)
        self.assertEqual(loss, 60)

    def test_rejects_candidate_that_hangs_queen_for_pawn(self):
        board = chess.Board("7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1")
        self.assertTrue(board.is_valid())
        blunder = board.parse_san("Qxh7")

        self.assertTrue(chess_engine.major_piece_loss_after_move(board, blunder))

    def test_allows_forced_mate(self):
        board = chess.Board(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        )
        mate = board.parse_san("Qxf7#")

        self.assertFalse(chess_engine.major_piece_loss_after_move(board, mate))

    def test_style_bonus_cannot_select_hanging_queen(self):
        board = chess.Board("7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1")
        self.assertTrue(board.is_valid())
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
