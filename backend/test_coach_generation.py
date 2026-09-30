import json
import os
import unittest
from unittest.mock import Mock, patch

import chess
from fastapi.testclient import TestClient

from api import app
from coach_conversation import current_conversation, question_mode, retrieval_question
from coach_evidence import EvidenceSource, KNOWLEDGE_SOURCES
from coach_generation import VERIFY_SCHEMA, chess_atoms, parse_natural_answer, review_passed
from rag import ChessRAG


def draft(text, *ids):
    return json.dumps({"insufficient_evidence": False, "paragraphs": [{"text": text, "source_ids": list(ids)}]}, ensure_ascii=False)


def review(**changes):
    return json.dumps({**{name: True for name in VERIFY_SCHEMA["required"]}, **changes})


class CoachGenerationTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"GOOGLE_API_KEY": "", "ENABLE_CHROMA_RAG": "0", "RAG_TIMEOUT_SECONDS": "20"})
        env.start()
        self.addCleanup(env.stop)
        self.rag = ChessRAG()
        self.rag.client = object()
        self.analysis = {"best_move": chess.Move.from_uci("e2e4"), "pv": ["e2e4", "e7e5"]}

    def test_paraphrase_is_allowed_but_new_moves_and_scores_are_rejected(self):
        source = KNOWLEDGE_SOURCES[14]
        text = "控制中心可以增加子力活動空間，也會限制對手的選擇。"
        self.assertIsNotNone(parse_natural_answer(draft(text, source.id), [source], "knowledge"))
        for bad in (draft("走 Qh5 就能將死。", source.id), draft("這步損失 500cp。", source.id), draft(text, "missing")):
            self.assertIsNone(parse_natural_answer(bad, [source], "position"))
        self.assertIsNone(parse_natural_answer(draft("先走 e4。", source.id), [source], "hint"))

    def test_a_cited_move_supports_naming_its_squares_but_not_other_moves(self):
        threat = EvidenceSource("T1", "目前威脅檢查", "如果不處理，白方下一步可以走 Qxf7# 將死。", "position")
        self.assertIsNotNone(parse_natural_answer(draft("白方瞄準 f7，下一步 Qxf7# 就將死。", "T1"), [threat], "position"))
        for bad in ("白方也可以走 Qf6。", "要小心 f6 格。", "白方威脅 Qxf7#，接著 e5 也會丟。"):
            self.assertIsNone(parse_natural_answer(draft(bad, "T1"), [threat], "position"))

    def test_only_the_unsupported_paragraph_is_dropped(self):
        last = EvidenceSource("L1", "上一手檢查", "白方上一手是 g4。這步之後，黑方可以走 Qh4# 直接將死。", "position")
        rule = KNOWLEDGE_SOURCES[12]
        raw = json.dumps({"insufficient_evidence": False, "paragraphs": [
            {"text": "g4 讓黑方可以 Qh4# 直接將死。", "source_ids": ["L1"]},
            {"text": "g4 沒有顧好王的安全。", "source_ids": [rule.id]},
            {"text": "也可以考慮 Qxh7。", "source_ids": ["L1"]},
        ]}, ensure_ascii=False)
        parsed = parse_natural_answer(raw, [last, rule], "position")
        self.assertEqual([p["text"] for p in parsed["paragraphs"]], ["g4 讓黑方可以 Qh4# 直接將死。"])
        # Malformed output still rejects the whole answer.
        broken = json.dumps({"insufficient_evidence": False, "paragraphs": [
            {"text": "g4 讓黑方可以 Qh4# 直接將死。", "source_ids": ["L1"]}, {"text": "x", "source_ids": ["missing"]},
        ]}, ensure_ascii=False)
        self.assertIsNone(parse_natural_answer(broken, [last, rule], "position"))

    def test_successful_natural_answer_is_reviewed_and_not_followed_by_template(self):
        text = "控制中心可以增加子力的活動空間，同時限制對手。"
        self.rag.call_gemini_with_fallback = Mock(side_effect=[draft(text, "K15"), review()])
        response = self.rag.get_response(chess.STARTING_FEN, "", "為什麼要控制中心？")
        self.assertEqual(response.status, "generated")
        self.assertEqual(response.advice, text + " [K15]")
        self.assertEqual(response.sources[0]["text"], KNOWLEDGE_SOURCES[14].text)
        self.assertNotIn("局面判斷", response.advice)
        self.assertEqual(self.rag.call_gemini_with_fallback.call_count, 2)
        generation, verification = self.rag.call_gemini_with_fallback.call_args_list
        self.assertEqual(generation.kwargs["deadline"], verification.kwargs["deadline"])
        self.assertIn("answer", json.loads(verification.args[0]))
        ids = generation.kwargs["response_schema"]["properties"]["paragraphs"]["items"]["properties"]["source_ids"]["items"]["enum"]
        self.assertIn("K15", ids)
        self.assertNotIn("P2", ids)

    def test_brief_followup_requires_one_short_paragraph(self):
        source = KNOWLEDGE_SOURCES[14]
        self.assertIsNotNone(parse_natural_answer(draft("中心可以讓棋子有更多空間。", source.id), [source], "knowledge", brief=True))
        self.assertIsNone(parse_natural_answer(draft("中" * 101, source.id), [source], "knowledge", brief=True))
        payload = json.loads(draft("中心可以讓棋子有更多空間。", source.id))
        payload["paragraphs"] *= 2
        self.assertIsNone(parse_natural_answer(json.dumps(payload), [source], "knowledge", brief=True))

    def test_comparison_failure_does_not_substitute_an_unrelated_recommendation(self):
        self.rag.call_gemini_with_fallback = Mock(return_value=None)
        response = self.rag.get_response(chess.STARTING_FEN, "", "Nf3 和 Nc3 哪個好？", analysis_result=self.analysis)
        self.assertEqual(response.mode, "comparison")
        self.assertEqual(response.status, "fallback")
        self.assertIn("無法可靠回答", response.advice)
        self.assertNotIn("推薦手", response.advice)

    def test_legacy_timeout_setting_leaves_budget_for_generation_and_review(self):
        self.rag.call_gemini_with_fallback = Mock(side_effect=[draft("中心提供活動空間。", "K15"), review()])
        with patch.dict(os.environ, {"RAG_TIMEOUT_SECONDS": "8"}), patch("rag.time.monotonic", return_value=100):
            response = self.rag.get_response(chess.STARTING_FEN, "", "為什麼要控制中心？")
        self.assertEqual(response.status, "generated")
        self.assertTrue(all(call.kwargs["deadline"] == 120 for call in self.rag.call_gemini_with_fallback.call_args_list))

    def test_semantically_unsupported_or_irrelevant_answer_is_not_displayed(self):
        for failed_flag in VERIFY_SCHEMA["required"]:
            with self.subTest(flag=failed_flag):
                self.rag.call_gemini_with_fallback = Mock(side_effect=[
                    draft("控制中心保證獲勝。", "K15"), review(**{failed_flag: False}),
                ])
                response = self.rag.get_response(chess.STARTING_FEN, "", "為什麼要控制中心？")
                self.assertEqual(response.status, "fallback")
                self.assertNotIn("保證獲勝", response.advice)
        for bad in (None, "true", "{}", '{"supported":true}', review(supported="true")):
            self.assertFalse(review_passed(bad))

    def test_hint_has_no_solution_sources_or_template_even_on_failure(self):
        captured = []
        self.rag.call_gemini_with_fallback = Mock(side_effect=lambda prompt, **kwargs: captured.append(json.loads(prompt)))
        response = self.rag.get_response(chess.STARTING_FEN, "", "給我提示，不要告訴我答案", analysis_result=self.analysis)
        self.assertEqual(response.mode, "hint")
        self.assertEqual(chess_atoms(response.advice), set())
        self.assertNotIn("推薦手", response.advice)
        self.assertIsNone(captured[0]["engine_recommendation"])
        self.assertTrue(all(not chess_atoms(source["text"]) for source in captured[0]["sources"]))
        self.assertNotIn("P2", [source["id"] for source in captured[0]["sources"]])

    def test_modes_and_followups(self):
        cases = {
            "易位的條件是什麼？": "knowledge", "現在能易位嗎？": "position",
            "Nf3 和 Bc4 哪個好？": "comparison", "給我提示，不要說答案": "hint",
            "直接告訴我答案": "position", "這是什麼開局？": "position",
            "給我提示，不要告訴我答案": "hint", "不用提示，直接給我答案": "position",
            "怎麼下比較好？": "position",
            "e4 是什麼意思？": "position", "exd5 好嗎？": "position",
            "騎士怎麼走？": "knowledge", "兵的走法是什麼？": "knowledge", "How does the knight move?": "knowledge",
            "象可以走直線嗎？": "knowledge", "兵可以後退嗎？": "knowledge", "兵怎麼吃子？": "knowledge",
            "我的馬現在怎麼走比較好？": "position", "這隻車該怎麼走？": "position", "現在這個兵可以走嗎？": "position",
            "馬可以跳到 f7 嗎？": "position", "王能走到 e2 嗎？": "position",
            "e8=Q 是什麼意思？": "position", "e4 和 d4 哪個好？": "comparison",
        }
        for question, expected in cases.items():
            self.assertEqual(question_mode(question), expected)
        self.assertEqual(question_mode(None), "overview")
        self.assertEqual(question_mode("再講簡單一點", [{"mode": "knowledge"}]), "knowledge")

    def test_conversation_is_bounded_and_bound_to_current_position(self):
        current = {"role": "user", "text": "為什麼要控制中心？", "fen": chess.STARTING_FEN, "mode": "knowledge"}
        other = dict(current, fen="8/8/8/8/8/8/4K3/7k w - - 0 1", text="我剛才將死了")
        turns = current_conversation([current, other, dict(current, role="system")], chess.STARTING_FEN)
        self.assertEqual(len(turns), 1)
        self.assertEqual(turns[0]["text"], current["text"])
        self.assertIn("中心", retrieval_question("那可以講簡單一點嗎？", turns))
        self.assertLessEqual(len(current_conversation([current] * 20, chess.STARTING_FEN)), 8)

    def test_followup_prompt_has_context_but_sources_do_not_include_old_model_claims(self):
        turns = [
            {"role": "user", "text": "為什麼要控制中心？", "fen": chess.STARTING_FEN, "mode": "knowledge"},
            {"role": "model", "text": "控制中心保證獲勝。", "fen": chess.STARTING_FEN, "mode": "knowledge"},
        ]
        self.rag.call_gemini_with_fallback = Mock(return_value=None)
        self.rag.get_response(chess.STARTING_FEN, "", "再講簡單一點", conversation=turns)
        payload = json.loads(self.rag.call_gemini_with_fallback.call_args.args[0])
        self.assertEqual(payload["mode"], "knowledge")
        self.assertEqual(len(payload["conversation"]), 2)
        self.assertNotIn("保證獲勝", json.dumps(payload["sources"], ensure_ascii=False))
        self.assertIn("K15", [source["id"] for source in payload["sources"]])

    def test_rule_question_skips_engine_and_exposes_source_metadata(self):
        self.rag.call_gemini_with_fallback = Mock(side_effect=[draft("易位前，王不能處於被將軍的狀態。", "K14"), review()])
        with patch("api.get_rag_engine", return_value=self.rag), patch("api.engine_search_slot") as engine:
            response = TestClient(app).post("/explain", json={"fen": chess.STARTING_FEN, "question": "王車易位需要什麼條件？"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "generated")
        self.assertEqual(response.json()["mode"], "knowledge")
        self.assertEqual(response.json()["sources"][0]["id"], "K14")
        engine.assert_not_called()

    def test_api_rejects_unbounded_or_system_conversation(self):
        turn = {"role": "user", "text": "中心是什麼？", "fen": chess.STARTING_FEN}
        client = TestClient(app)
        for conversation in ([turn] * 9, [dict(turn, role="system")], [dict(turn, text="x" * 1501)]):
            for path in ("/explain", "/get_analysis"):
                response = client.post(path, json={"fen": chess.STARTING_FEN, "conversation": conversation})
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
