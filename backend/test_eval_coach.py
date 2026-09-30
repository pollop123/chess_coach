import unittest

import chess

from eval_coach import wrong_side_avoid


def fen_after(moves):
    board = chess.Board()
    for san in moves.split():
        board.push_san(san)
    return board.fen()


class WrongSideAvoidTests(unittest.TestCase):
    def test_flags_only_opponent_moves_told_to_the_student(self):
        fen = fen_after("e4 e5 Nf3 Qh4 d3")  # Black to move, student is White
        for text in ("在選擇走法時，應避免像 Qg4 這樣會損失較多評分的選擇。", "你應避免 Qg4。"):
            self.assertTrue(wrong_side_avoid(text, fen, "white"), text)
        for text in ("黑方應避免 Qg4，因為會丟分。", "對手應避免 Qg4。", "對手若走 Qg4 會吃虧。", "應避免 Nxh4 以外的走法。"):
            self.assertFalse(wrong_side_avoid(text, fen, "white"), text)

    def test_student_to_move_is_never_flagged(self):
        self.assertFalse(wrong_side_avoid("應避免像 Qg4 這樣的走法。", fen_after("e4 e5 Nf3 Qh4 d3"), "black"))


if __name__ == "__main__":
    unittest.main()
