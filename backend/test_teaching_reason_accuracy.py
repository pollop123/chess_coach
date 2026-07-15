import unittest

import chess

import chess_engine


class TeachingReasonAccuracyTests(unittest.TestCase):
    @staticmethod
    def mirrored_move(board, move):
        mirrored_board = board.mirror()
        mirrored_move = chess.Move(
            chess.square_mirror(move.from_square),
            chess.square_mirror(move.to_square),
            promotion=move.promotion,
        )
        return mirrored_board, mirrored_move

    def reason_and_themes(self, fen, san):
        board = chess.Board(fen)
        move = board.parse_san(san)
        reason = chess_engine._move_reason(board, move, [])
        return reason, chess_engine._move_themes(board, move, reason)

    def test_ordinary_queen_move_is_not_labeled_as_avoiding_major_loss(self):
        reason, _themes = self.reason_and_themes(
            "4k3/8/8/8/8/3Q4/8/4K3 w - - 0 1", "Qd2"
        )
        self.assertNotEqual(reason, "avoids_major_piece_loss")

    def test_attacked_queen_move_can_receive_supported_rescue_reason(self):
        reason, _themes = self.reason_and_themes(
            "k6r/8/8/7Q/8/8/8/4K3 w - - 0 1", "Qg5"
        )
        self.assertEqual(reason, "avoids_major_piece_loss")
        self.assertEqual(chess_engine._reason_evidence(reason), "supported")

    def test_defended_rook_capture_is_not_claimed_as_material_win_or_tactic(self):
        reason, themes = self.reason_and_themes(
            "6k1/3r4/8/5b2/8/8/8/3Q2K1 w - - 0 1", "Qxd7"
        )
        self.assertNotEqual(reason, "wins_material")
        self.assertNotIn("tactics", themes)

    def test_undefended_rook_capture_is_supported_material_win(self):
        reason, themes = self.reason_and_themes(
            "6k1/3r4/8/8/8/8/8/3Q2K1 w - - 0 1", "Qxd7"
        )
        self.assertEqual(reason, "wins_material")
        self.assertIn("tactics", themes)
        self.assertEqual(chess_engine._reason_evidence(reason), "supported")

    def test_pawn_leaving_center_without_controlling_it_is_not_center_control(self):
        reason, themes = self.reason_and_themes(
            "4k3/8/8/8/3P4/8/8/4K3 w - - 0 1", "d5"
        )
        self.assertNotEqual(reason, "controls_center")
        self.assertNotIn("center_control", themes)

    def test_attack_on_enemy_king_is_not_mislabeled_as_own_king_safety(self):
        reason, themes = self.reason_and_themes(
            "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
            "Qxf7#",
        )
        self.assertEqual(reason, "checkmate")
        self.assertIn("king_attack", themes)
        self.assertNotIn("king_safety", themes)

    def test_two_knights_nxf7_is_explained_as_a_verified_fork(self):
        reason, themes = self.reason_and_themes(
            "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
            "Nxf7",
        )

        self.assertEqual(reason, "creates_valuable_piece_fork")
        self.assertEqual(chess_engine._reason_evidence(reason), "verified")
        self.assertIn("tactics", themes)
        self.assertNotIn("center_control", themes)

        board = chess.Board(
            "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6"
        )
        teaching = chess_engine.get_teaching_analysis(
            board,
            {"best_move": board.parse_san("Nxf7"), "score": 0, "depth": 2},
            candidate_count=8,
            depth=2,
        )
        self.assertEqual(teaching["best_move_reason"], "creates_valuable_piece_fork")
        self.assertIn("tactics", teaching["position_themes"])
        self.assertNotIn("center_control", teaching["position_themes"])
        self.assertIn("center_control", teaching["candidate_themes"])

    def test_attacking_only_one_valuable_piece_is_not_called_a_fork(self):
        board = chess.Board("3qk3/8/8/6N1/8/8/8/4K3 w - - 0 1")
        move = board.parse_san("Nf7")
        mirrored_board, mirrored_move = self.mirrored_move(board, move)

        for perspective, test_board, test_move in (
            ("white", board, move),
            ("black", mirrored_board, mirrored_move),
        ):
            with self.subTest(perspective=perspective):
                self.assertFalse(
                    chess_engine._move_creates_valuable_piece_fork(test_board, test_move)
                )
                self.assertNotEqual(
                    chess_engine._move_reason(test_board, test_move, []),
                    "creates_valuable_piece_fork",
                )

    def test_queenless_full_armies_are_not_called_endgame(self):
        board = chess.Board()
        board.remove_piece_at(chess.D1)
        board.remove_piece_at(chess.D8)
        self.assertFalse(chess_engine._is_teaching_endgame(board))

    def test_endgame_material_family_themes_are_explicit(self):
        cases = (
            ("7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "Qg7#", "queen_endgame"),
            ("8/5pk1/6p1/3R4/7P/6P1/5PK1/r7 w - - 0 1", "Rd7", "rook_endgame"),
            ("8/8/4k3/8/2B1P3/4K3/8/8 w - - 0 1", "Bd3", "minor_piece_endgame"),
            ("8/8/4k3/8/4P3/4K3/8/8 w - - 0 1", "Kd3", "pawn_endgame"),
        )
        for fen, san, expected_theme in cases:
            with self.subTest(theme=expected_theme):
                reason, themes = self.reason_and_themes(fen, san)
                self.assertIn("endgame", themes)
                self.assertIn(expected_theme, themes)
                self.assertEqual(
                    chess_engine._theme_evidence(expected_theme, reason), "verified"
                )

    def test_fen_only_middlegame_is_not_called_opening(self):
        board = chess.Board(
            "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P4/2P1PN2/PP1NBPPP/R2Q1RK1 w - - 0 22"
        )
        move = board.parse_san("dxc5")
        reason = chess_engine._move_reason(board, move, [])

        self.assertNotIn("opening_principle", chess_engine._move_themes(board, move, reason))

    def test_normal_fourth_move_position_is_still_opening(self):
        board = chess.Board()
        for san in ("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"):
            board.push_san(san)
        move = board.parse_san("d3")
        reason = chess_engine._move_reason(board, move, [])

        self.assertEqual(chess_engine.detect_game_phase(board), "opening")
        self.assertIn("opening_principle", chess_engine._move_themes(board, move, reason))

    def test_pinned_attacker_is_not_a_legal_major_piece_threat(self):
        board = chess.Board("4k3/4n3/8/5Q2/8/8/8/K3R3 w - - 0 1")
        move = board.parse_san("Qg4")

        self.assertNotEqual(
            chess_engine._move_reason(board, move, []),
            "avoids_major_piece_loss",
        )

    def test_every_reason_has_white_and_black_positive_examples(self):
        cases = (
            ("checkmate", "7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "Qg7#"),
            ("check", "4k3/8/8/8/8/8/8/R3K3 w - - 0 1", "Ra8+"),
            ("castle", "4k3/8/8/8/8/8/8/4K2R w K - 0 1", "O-O"),
            ("resolves_check", "4r1k1/8/8/8/8/8/8/4K3 w - - 0 1", "Kf2"),
            ("promotes_or_supports_promotion", "k7/4P3/8/8/8/8/8/4K3 w - - 0 1", "e8=Q"),
            ("wins_material", "6k1/3r4/8/8/8/8/8/3Q2K1 w - - 0 1", "Qxd7"),
            ("avoids_major_piece_loss", "k6r/8/8/7Q/8/8/8/4K3 w - - 0 1", "Qg5"),
            (
                "creates_valuable_piece_fork",
                "3qk2r/8/8/6N1/8/8/8/4K3 w - - 0 1",
                "Nf7",
            ),
            ("develops_piece", chess.STARTING_FEN, "Nf3"),
            ("controls_center", "4k3/8/8/8/8/8/2P5/4K3 w - - 0 1", "c4"),
            ("improves_king_safety", "4k3/8/8/2b5/8/8/8/4K3 w - - 0 1", "Kd1"),
            ("attacks_enemy_king", "6k1/8/8/8/8/8/8/R3K3 w - - 0 1", "Ra7"),
            ("best_engine_score", "4k3/8/8/8/8/8/P7/4K3 w - - 0 1", "a3"),
        )
        for expected, fen, san in cases:
            board = chess.Board(fen)
            move = board.parse_san(san)
            mirrored_board, mirrored_move = self.mirrored_move(board, move)
            for perspective, test_board, test_move in (
                ("white", board, move),
                ("black", mirrored_board, mirrored_move),
            ):
                with self.subTest(reason=expected, perspective=perspective):
                    self.assertTrue(test_board.is_valid())
                    self.assertIn(test_move, test_board.legal_moves)
                    self.assertEqual(
                        chess_engine._move_reason(test_board, test_move, []), expected
                    )

    def test_quiet_move_is_a_white_and_black_negative_for_specific_reasons(self):
        board = chess.Board("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")
        move = board.parse_san("a3")
        mirrored_board, mirrored_move = self.mirrored_move(board, move)
        excluded = set(chess_engine.REASON_EVIDENCE) - {"best_engine_score"}

        for perspective, test_board, test_move in (
            ("white", board, move),
            ("black", mirrored_board, mirrored_move),
        ):
            reason = chess_engine._move_reason(test_board, test_move, [])
            with self.subTest(perspective=perspective):
                self.assertEqual(reason, "best_engine_score")
                self.assertNotIn(reason, excluded)

    def test_false_positive_fixtures_hold_for_white_and_black(self):
        cases = (
            (
                "defended_capture",
                "6k1/3r4/8/5b2/8/8/8/3Q2K1 w - - 0 1",
                "Qxd7",
                "wins_material",
                "tactics",
            ),
            (
                "pinned_attacker",
                "4k3/4n3/8/5Q2/8/8/8/K3R3 w - - 0 1",
                "Qg4",
                "avoids_major_piece_loss",
                None,
            ),
            (
                "leaves_center",
                "4k3/8/8/8/3P4/8/8/4K3 w - - 0 1",
                "d5",
                "controls_center",
                "center_control",
            ),
            (
                "enemy_king_attack",
                "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
                "Qxf7#",
                None,
                "king_safety",
            ),
        )
        for name, fen, san, forbidden_reason, forbidden_theme in cases:
            board = chess.Board(fen)
            move = board.parse_san(san)
            mirrored_board, mirrored_move = self.mirrored_move(board, move)
            for perspective, test_board, test_move in (
                ("white", board, move),
                ("black", mirrored_board, mirrored_move),
            ):
                reason = chess_engine._move_reason(test_board, test_move, [])
                themes = chess_engine._move_themes(test_board, test_move, reason)
                with self.subTest(case=name, perspective=perspective):
                    if forbidden_reason:
                        self.assertNotEqual(reason, forbidden_reason)
                    if forbidden_theme:
                        self.assertNotIn(forbidden_theme, themes)

    def test_evidence_levels_are_exposed_on_candidates(self):
        board = chess.Board()
        teaching = chess_engine.get_teaching_analysis(
            board,
            {"best_move": board.parse_san("Nf3"), "score": 20, "depth": 2},
            candidate_count=3,
            depth=1,
        )
        for candidate in teaching["candidates"]:
            self.assertIn(candidate["reason_evidence"], {"verified", "supported", "heuristic"})
            self.assertEqual(set(candidate["themes"]), set(candidate["theme_evidence"]))
        self.assertIn(teaching["best_move_evidence"], {"verified", "supported", "heuristic"})


if __name__ == "__main__":
    unittest.main()
