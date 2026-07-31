import unittest

import chess

from build_evaluation_corpus import position_topic, round_robin_sample, split_for_game


class EvaluationCorpusBuilderTests(unittest.TestCase):
    def test_game_split_is_stable_and_grouped(self):
        self.assertEqual([split_for_game(index) for index in range(14)], ["train"] * 14)
        self.assertEqual([split_for_game(index) for index in range(14, 17)], ["validation"] * 3)
        self.assertEqual([split_for_game(index) for index in range(17, 20)], ["test"] * 3)
        self.assertEqual(split_for_game(20), "train")

    def test_topic_classification_separates_opening_tactics_and_endgame(self):
        self.assertEqual(position_topic(chess.Board(), 0), "opening")
        checked = chess.Board()
        checked.remove_piece_at(chess.E2)
        checked.remove_piece_at(chess.E7)
        checked.remove_piece_at(chess.H1)
        checked.set_piece_at(chess.E2, chess.Piece(chess.ROOK, chess.WHITE))
        checked.turn = chess.BLACK
        self.assertEqual(position_topic(checked, 30), "tactics")
        endgame = chess.Board("8/8/4k3/8/4P3/4K3/8/8 w - - 0 1")
        self.assertEqual(position_topic(endgame, 40), "endgame")

    @staticmethod
    def _position(name: str, fen: str) -> dict:
        return {"name": name, "fen": fen}

    def test_round_robin_sample_preserves_game_diversity(self):
        games = [
            [self._position("a1", "fen-1 w - -"), self._position("a2", "fen-2 w - -")],
            [self._position("b1", "fen-3 w - -"), self._position("b2", "fen-4 w - -")],
            [self._position("c1", "fen-5 w - -")],
        ]
        self.assertEqual(
            [item["name"] for item in round_robin_sample(games, 4)],
            ["a1", "b1", "c1", "a2"],
        )

    def test_round_robin_sample_drops_transpositions_across_games(self):
        shared = "shared w - - 0 1"
        games = [
            [self._position("a1", shared), self._position("a2", "unique-a w - - 0 1")],
            [self._position("b1", shared), self._position("b2", "unique-b w - - 0 1")],
        ]
        selected = round_robin_sample(games, 4)
        self.assertEqual([item["name"] for item in selected], ["a1", "a2", "b2"])

    def test_round_robin_sample_ignores_move_counters_when_deduplicating(self):
        games = [
            [self._position("a1", "same w KQkq - 0 1")],
            [self._position("b1", "same w KQkq - 9 40")],
        ]
        self.assertEqual(
            [item["name"] for item in round_robin_sample(games, 2)], ["a1"]
        )


if __name__ == "__main__":
    unittest.main()
