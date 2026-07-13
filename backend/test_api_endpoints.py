import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from api import app


class ApiEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.make_move_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        cls.analysis_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"

    def test_make_move_returns_playable_move(self):
        response = self.client.post(
            "/make_move",
            json={
                "fen": self.make_move_fen,
                "time_limit": 0.2,
                "difficulty": "newbie",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertRegex(data["best_move"], r"^[a-h][1-8][a-h][1-8][qrbn]?$")
        self.assertEqual(data["difficulty"], "newbie")
        self.assertIn("depth_reached", data)
        self.assertIn("fen", data)

    def test_get_analysis_returns_engine_evaluation(self):
        response = self.client.post(
            "/get_analysis",
            json={
                "fen": self.analysis_fen,
                "history": "1. e4 e5",
                "question": "請分析當前局面",
                "depth": 2,
                "time_limit": 0.2,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        evaluation = data["evaluation"]
        self.assertIn("score_cp", evaluation)
        self.assertIn("display", evaluation)
        self.assertIn("winning_chance", evaluation)
        self.assertIn("pv_line", evaluation)
        self.assertEqual(data["game_state"], "opening")
        self.assertIn("teaching_analysis", data)
        self.assertGreaterEqual(len(data["teaching_analysis"]["candidates"]), 1)
        self.assertIn("criticality", data["teaching_analysis"])

    def test_make_move_does_not_return_teaching_analysis(self):
        response = self.client.post(
            "/make_move",
            json={
                "fen": self.make_move_fen,
                "time_limit": 0.2,
                "difficulty": "newbie",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("teaching_analysis", response.json())

    def test_analyze_compatibility_endpoint_returns_legacy_shape(self):
        response = self.client.post(
            "/analyze",
            json={"fen": self.make_move_fen, "depth": 2},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertRegex(data["best_move"], r"^[a-h][1-8][a-h][1-8][qrbn]?$")
        self.assertIn("evaluation_display", data)
        self.assertIn("winning_chance", data)

    def test_normal_question_containing_system_is_not_rejected(self):
        rag_engine = Mock()
        rag_engine.get_advice.return_value = "請先完成子力發展。"
        with patch("api.get_rag_engine", return_value=rag_engine):
            response = self.client.post(
                "/get_analysis",
                json={
                    "fen": self.analysis_fen,
                    "history": "1. e4 e5",
                    "question": "這個 system 性的弱點該怎麼守？",
                    "depth": 2,
                    "time_limit": 0.2,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["coach_advice"], "請先完成子力發展。")
        self.assertEqual(rag_engine.get_advice.call_args.args[2], "這個 system 性的弱點該怎麼守？")

    def test_explain_passes_verified_teaching_analysis_to_rag(self):
        rag_engine = Mock()
        rag_engine.get_advice.return_value = "推薦手：Nf3"
        analysis = {
            "best_move": None,
            "from_book": False,
            "book_line": [],
            "pv": [],
            "score": 20,
            "eval_display": "+0.20",
            "winning_chance": 52.0,
        }
        teaching_analysis = {
            "candidates": [{"san": "Nf3", "rank": 1}],
            "criticality": "normal",
            "position_themes": ["development"],
            "best_move_reason": "develops_piece",
            "mistake_warnings": [],
        }

        with (
            patch("api.get_rag_engine", return_value=rag_engine),
            patch("api.chess_engine.get_analysis", return_value=analysis),
            patch("api.chess_engine.get_teaching_analysis", return_value=teaching_analysis),
        ):
            response = self.client.post(
                "/explain",
                json={
                    "fen": self.analysis_fen,
                    "history": "1. e4 e5",
                    "question": "為什麼要發展騎士？",
                    "depth": 2,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            rag_engine.get_advice.call_args.kwargs["teaching_analysis"],
            teaching_analysis,
        )

    def test_analyze_full_after_make_move(self):
        move_response = self.client.post(
            "/make_move",
            json={"fen": self.make_move_fen, "time_limit": 0.05, "difficulty": "newbie"},
        )
        self.assertEqual(move_response.status_code, 200)

        response = self.client.post(
            "/analyze_full",
            json={"pgn": "1. e4 e5 2. Nf3 Nc6", "depth": 1, "perspective": "white"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 5)

    def test_invalid_fen_returns_400(self):
        response = self.client.post("/get_analysis", json={"fen": "invalid fen"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Invalid FEN string")


if __name__ == "__main__":
    unittest.main()
