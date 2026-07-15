import unittest

import chess

import chess_engine


class EngineUpgradeTests(unittest.TestCase):
    def test_opening_position_returns_move_and_evaluation(self):
        board = chess.Board()
        board.push_san("e4")
        board.push_san("e5")
        board.push_san("Nf3")

        analysis = chess_engine.get_analysis(board, depth=5)

        self.assertIn(analysis["best_move"], board.legal_moves)
        self.assertIsInstance(analysis["score"], int)
        self.assertRegex(analysis["eval_display"], r"^(?:[+-]?\d+\.\d{2}|-?M\d+)$")
        self.assertGreaterEqual(analysis["winning_chance"], 0)
        self.assertLessEqual(analysis["winning_chance"], 100)
        self.assertGreaterEqual(analysis["depth"], 0)
        self.assertIsInstance(analysis["pv"], list)

    def test_endgame_position_searches_deeper_than_requested_depth(self):
        board = chess.Board("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1")

        analysis = chess_engine.get_analysis(board, depth=5)

        self.assertIn(analysis["best_move"], board.legal_moves)
        self.assertGreaterEqual(analysis["depth"], 8)
        self.assertGreater(analysis["score"], 0)

    def test_mate_position_is_formatted_as_mate(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")

        analysis = chess_engine.get_analysis(board, depth=5)

        self.assertEqual(analysis["best_move"], chess.Move.from_uci("a1a8"))
        self.assertEqual(analysis["eval_display"], "M1")
        self.assertEqual(analysis["winning_chance"], 100.0)

    def test_advanced_search_prefers_active_two_knights_tactic(self):
        board = chess.Board("r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6")

        analysis = chess_engine.get_analysis(
            board,
            depth=5,
            time_limit=1.5,
            use_book=False,
            adaptive_depth=True,
            difficulty="advanced",
        )

        self.assertIn(board.san(analysis["best_move"]), {"Nxf7", "d4"})

    def test_evaluation_formatting_and_win_probability(self):
        self.assertEqual(chess_engine.format_evaluation(150), "+1.50")
        self.assertEqual(chess_engine.format_evaluation(-80), "-0.80")
        self.assertEqual(chess_engine.format_evaluation(20000), "M1")
        self.assertEqual(chess_engine.format_evaluation(-19995), "-M3")
        self.assertGreater(chess_engine.calculate_winning_chance(500), 50)
        self.assertLess(chess_engine.calculate_winning_chance(-500), 50)

    def test_game_phase_detection(self):
        self.assertEqual(chess_engine.detect_game_phase(chess.Board()), "opening")
        self.assertEqual(
            chess_engine.detect_game_phase(chess.Board("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1")),
            "endgame",
        )
        self.assertEqual(
            chess_engine.detect_game_phase(
                chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
            ),
            "opening",
        )


if __name__ == "__main__":
    unittest.main()
