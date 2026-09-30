import os
import unittest
from unittest.mock import patch

import chess
from fastapi.testclient import TestClient

from api import app
from coach_facts import last_move_source, loose_pieces, move_fact_summary, replay_history, threat_hint_source, threat_source
from coach_generation import chess_atoms
from rag import ChessRAG

FOOLS_MATE_FEN = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
FOOLS_MATE_PGN = "1. f3 e5 2. g4"


def board_after(pgn_moves):
    board = chess.Board()
    for san in pgn_moves.split():
        board.push_san(san)
    return board


class CoachFactTests(unittest.TestCase):
    def test_last_move_that_allows_mate_in_one(self):
        source = last_move_source(FOOLS_MATE_PGN, chess.Board(FOOLS_MATE_FEN))
        self.assertEqual(source.id, "L1")
        self.assertIn("白方上一手是 g4", source.text)
        self.assertIn("黑方可以走 Qh4# 直接將死", source.text)

    def test_player_colour_skips_the_opponents_reply(self):
        board = board_after("e4 e5 Qh5 Nc6")
        history = "1. e4 e5 2. Qh5 Nc6"
        own = last_move_source(history, board, chess.WHITE)
        self.assertIn("白方上一手是 Qh5", own.text)
        self.assertIn("黑方實際回應 Nc6", own.text)
        self.assertIn("黑方上一手是 Nc6", last_move_source(history, board).text)

    def test_last_move_that_hangs_a_piece_or_misses_a_capture(self):
        hang = board_after("e4 e5 Nf3 Nc6 Nh4")
        self.assertIn("馬（h4）受到攻擊且沒有保護", last_move_source("1. e4 e5 2. Nf3 Nc6 3. Nh4", hang).text)

        # 2...Qh4 left the queen undefended in front of the f3 knight; 3.d3 missed Nxh4.
        text = last_move_source("1. e4 e5 2. Nf3 Qh4 3. d3", board_after("e4 e5 Nf3 Qh4 d3")).text
        self.assertIn("原本可以走 Nxh4 吃掉沒有保護的后", text)

    def test_quiet_safe_move_says_so_without_claiming_it_is_best(self):
        text = last_move_source("1. e4", board_after("e4")).text
        self.assertIn("沒有讓對手一步將死", text)
        self.assertIn("是否為最佳手需另看引擎評估", text)

    def test_repeated_position_uses_the_latest_occurrence(self):
        # Knights go out and back: the board equals the start, but four moves were played.
        source = last_move_source("1. Nf3 Nf6 2. Ng1 Ng8", chess.Board())
        self.assertIn("黑方上一手是 Ng8", source.text)

    def test_en_passant_counts_as_a_capture(self):
        text = last_move_source("1. e4 a6 2. e5 d5 3. exd6", board_after("e4 a6 e5 d5 exd6")).text
        self.assertIn("吃掉兵", text)
        self.assertNotIn("原本可以走", text)

    def test_pinned_attackers_do_not_make_a_piece_loose(self):
        # The e2 knight attacks d4 but is pinned to its king by the e8 rook.
        for turn in ("w", "b"):
            board = chess.Board(f"k3r3/8/8/8/3q4/8/4N3/4K3 {turn} - - 0 1")
            self.assertEqual(loose_pieces(board, chess.BLACK), [], turn)

    def test_english_last_move_questions_are_position_questions(self):
        from coach_conversation import question_mode
        for question in ("Why was my last move bad?", "Was my previous move a mistake?"):
            self.assertEqual(question_mode(question), "position")

    def test_history_that_does_not_reach_the_board_is_ignored(self):
        self.assertIsNone(last_move_source("1. d4", chess.Board(FOOLS_MATE_FEN)))
        self.assertIsNone(last_move_source("", chess.Board(FOOLS_MATE_FEN)))
        self.assertIsNone(last_move_source("not a pgn ((", chess.Board(FOOLS_MATE_FEN)))
        self.assertEqual(replay_history("1. e4", chess.Board()), [])

    def test_threats_for_the_side_to_move(self):
        self.assertIn("黑方現在可以走 Qh4# 直接將死", threat_source(chess.Board(FOOLS_MATE_FEN)).text)
        check = chess.Board("4k3/8/8/8/8/8/4q3/4K3 w - - 0 1")
        self.assertTrue(threat_source(check).text.startswith("白方正被將軍，必須先解將。"))
        quiet = threat_source(chess.Board()).text
        self.assertIn("沒有一步將死的機會", quiet)
        self.assertIsNone(threat_source(board_after("f3 e5 g4 Qh4")))

    def test_mate_threat_against_the_side_to_move(self):
        # Black to move; White threatens Qxf7#.
        board = board_after("e4 e5 Bc4 Nc6 Qh5")
        board.push_san("a6")
        board.push_san("a3")
        self.assertIn("如果不處理，白方下一步可以走 Qxf7# 將死", threat_source(board).text)

    def test_threat_hint_points_at_the_danger_without_moves(self):
        board = board_after("e4 e5 Bc4 Nc6 Qh5 a6 a3")
        hint = threat_hint_source(board)
        self.assertIn("對手下一步有將死你的威脅", hint.text)
        self.assertEqual(chess_atoms(hint.text), set())
        self.assertIn("一步就能將死對手", threat_hint_source(chess.Board(FOOLS_MATE_FEN)).text)
        self.assertIsNone(threat_hint_source(chess.Board()))

    def test_hint_mode_leads_with_the_threat(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "", "ENABLE_CHROMA_RAG": "0"}):
            rag = ChessRAG()
        board = board_after("e4 e5 Bc4 Nc6 Qh5 a6 a3")
        reply = rag.get_response(board.fen(), "", "給我提示，不要告訴我答案",
                                 analysis_result={"best_move": board.parse_san("Qe7"), "pv": []})
        self.assertEqual(reply.mode, "hint")
        self.assertIn("對手下一步有將死你的威脅", reply.advice)
        self.assertEqual(chess_atoms(reply.advice.split("（")[0]), set())

    def test_loose_pieces_include_cheaper_attackers(self):
        board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 b - - 0 1")
        self.assertEqual(loose_pieces(board, chess.BLACK), [(chess.D5, "沒有保護")])
        defended = chess.Board("4k3/4r3/8/4q3/3P4/8/8/4K3 b - - 0 1")
        self.assertEqual(loose_pieces(defended, chess.BLACK), [(chess.E5, "會被價值較低的棋子吃掉")])

    def test_move_fact_summary(self):
        board = chess.Board(FOOLS_MATE_FEN)
        self.assertEqual(move_fact_summary(board, board.parse_san("Qh4#")), "Qh4# 直接將死。")
        capture = board_after("e4 d5")
        self.assertEqual(move_fact_summary(capture, capture.parse_san("exd5")), "exd5 會吃掉兵。")
        self.assertIsNone(move_fact_summary(chess.Board(), chess.Move.from_uci("e2e4")))


class CoachFactAnswerTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"GOOGLE_API_KEY": "", "ENABLE_CHROMA_RAG": "0"})
        env.start()
        self.addCleanup(env.stop)
        self.rag = ChessRAG()

    def test_fallback_answers_the_last_move_question_with_board_facts(self):
        mate = chess.Board(FOOLS_MATE_FEN).parse_san("Qh4#")
        reply = self.rag.get_response(FOOLS_MATE_FEN, FOOLS_MATE_PGN, "我剛才那步 g4 為什麼不好？",
                                      analysis_result={"best_move": mate, "pv": [mate.uci()]}, player_color="white")
        self.assertTrue(reply.advice.startswith("白方上一手是 g4"))
        self.assertIn("直接將死", reply.advice)
        self.assertIn("選這步的原因：盤面可直接確認：Qh4# 直接將死。", reply.advice)
        self.assertEqual([source["id"] for source in reply.sources], ["L1", "T1"])

    def test_last_move_check_only_leads_when_asked_about(self):
        mate = chess.Board(FOOLS_MATE_FEN).parse_san("Qh4#")
        reply = self.rag.get_response(FOOLS_MATE_FEN, FOOLS_MATE_PGN, "現在該怎麼走？",
                                      analysis_result={"best_move": mate, "pv": [mate.uci()]})
        self.assertEqual([source["id"] for source in reply.sources], ["T1"])

    def test_model_receives_board_facts_and_knowledge_questions_skip_them(self):
        captured = []

        def fake_call(prompt, **_kwargs):
            captured.append(prompt)
            raise RuntimeError("stop after capturing the prompt")

        self.rag.client = object()
        self.rag.call_gemini_with_fallback = fake_call
        mate = chess.Board(FOOLS_MATE_FEN).parse_san("Qh4#")
        self.rag.get_response(FOOLS_MATE_FEN, FOOLS_MATE_PGN, "我剛才那步為什麼不好？",
                              analysis_result={"best_move": mate, "pv": [mate.uci()]}, player_color="white")
        self.assertIn('"id": "L1"', captured[0])
        # The student is White but Black is to move, so the model must not say "you" for Qh4#.
        self.assertIn('"student_side": "白方"', captured[0])
        self.assertIn('"side_to_move": "黑方"', captured[0])
        self.assertIn('"id": "T1"', captured[0])
        self.rag.get_response(FOOLS_MATE_FEN, FOOLS_MATE_PGN, "王車易位的條件是什麼？")
        self.assertNotIn('"id": "L1"', captured[1])

    def test_explain_accepts_player_colour(self):
        client = TestClient(app)
        body = {"fen": FOOLS_MATE_FEN, "history": FOOLS_MATE_PGN, "question": "我剛才那步為什麼不好？"}
        self.assertEqual(client.post("/explain", json={**body, "player_color": "purple"}).status_code, 422)
        with patch("api.get_rag_engine", return_value=self.rag):
            data = client.post("/explain", json={**body, "player_color": "white"}).json()
        self.assertIn("白方上一手是 g4", data["advice"])


if __name__ == "__main__":
    unittest.main()
