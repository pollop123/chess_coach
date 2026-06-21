import unittest
from unittest.mock import patch

import chess

from api import MakeMoveRequest, make_move


class DifficultyApiTests(unittest.TestCase):
    def test_make_move_passes_selected_difficulty_to_engine(self):
        selected_move = chess.Move.from_uci("e2e4")
        analysis = {
            "best_move": selected_move,
            "depth": 1,
            "from_book": False,
            "style_bonus": 0,
            "difficulty_loss": 180,
        }

        with patch("api.chess_engine.get_analysis", return_value=analysis) as get_analysis:
            response = make_move(
                MakeMoveRequest(
                    fen=chess.STARTING_FEN,
                    difficulty="newbie",
                    bot_style="balanced",
                )
            )

        self.assertEqual(get_analysis.call_args.kwargs["difficulty"], "newbie")
        self.assertEqual(response["difficulty_loss"], 180)
        self.assertEqual(response["difficulty_label"], "新手")

    def test_unknown_difficulty_falls_back_consistently(self):
        analysis = {
            "best_move": chess.Move.from_uci("e2e4"),
            "depth": 1,
            "from_book": False,
            "style_bonus": 0,
            "difficulty_loss": 0,
        }

        with patch("api.chess_engine.get_analysis", return_value=analysis) as get_analysis:
            response = make_move(
                MakeMoveRequest(
                    fen=chess.STARTING_FEN,
                    difficulty="typo",
                    bot_style="balanced",
                )
            )

        self.assertEqual(get_analysis.call_args.kwargs["difficulty"], "intermediate")
        self.assertEqual(response["difficulty"], "intermediate")
        self.assertEqual(response["difficulty_label"], "中階")


if __name__ == "__main__":
    unittest.main()
