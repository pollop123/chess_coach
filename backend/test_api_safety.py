import os
import threading
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import chess
from fastapi.testclient import TestClient

from api import MAX_REVIEW_PLIES, _configured_cors_origins, app, get_db


class ApiSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.analysis_fen = (
            "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        )

    def test_analysis_depth_and_time_are_bounded(self):
        too_deep = self.client.post(
            "/get_analysis",
            json={"fen": self.analysis_fen, "depth": 9, "time_limit": 0.2},
        )
        too_slow = self.client.post(
            "/get_analysis",
            json={"fen": self.analysis_fen, "depth": 2, "time_limit": 10.1},
        )

        self.assertEqual(too_deep.status_code, 422)
        self.assertEqual(too_slow.status_code, 422)

    def test_game_history_pagination_is_bounded(self):
        negative_skip = self.client.get("/games?skip=-1")
        excessive_limit = self.client.get("/games?limit=101")

        self.assertEqual(negative_skip.status_code, 422)
        self.assertEqual(excessive_limit.status_code, 422)

    def test_legacy_game_rows_are_not_revalidated_as_new_writes(self):
        legacy_row = SimpleNamespace(
            id=1,
            date=datetime(2026, 7, 31),
            pgn="",
            result="",
            fen="",
            player_white="W" * 101,
            player_black=None,
        )
        db = Mock()
        query = db.query.return_value.order_by.return_value
        query.offset.return_value.limit.return_value.all.return_value = [legacy_row]

        def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        try:
            response = self.client.get("/games")
        finally:
            app.dependency_overrides.pop(get_db, None)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["pgn"], "")
        self.assertEqual(response.json()[0]["player_white"], "W" * 101)
        self.assertIsNone(response.json()[0]["player_black"])

    def test_unknown_review_perspective_is_rejected(self):
        response = self.client.post(
            "/analyze_full",
            json={"pgn": "1. e4 e5", "depth": 1, "perspective": "sideways"},
        )

        self.assertEqual(response.status_code, 422)

    def test_engine_capacity_returns_retryable_503(self):
        busy_lock = Mock()
        busy_lock.acquire.return_value = False
        with patch("api.engine_search_lock", busy_lock):
            response = self.client.post(
                "/get_analysis",
                json={"fen": self.analysis_fen, "depth": 2, "time_limit": 0.2},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], "2")
        self.assertIn("retry", response.json()["detail"].lower())
        busy_lock.release.assert_not_called()

    def test_full_review_rejects_unbounded_move_count(self):
        oversized_game = Mock()
        oversized_game.mainline_moves.return_value = iter(
            range(MAX_REVIEW_PLIES + 1)
        )
        with patch("api.chess.pgn.read_game", return_value=oversized_game):
            response = self.client.post(
                "/analyze_full",
                json={"pgn": "1. e4", "depth": 1, "perspective": "white"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn(str(MAX_REVIEW_PLIES), response.json()["detail"])

    def test_cors_origins_are_environment_driven(self):
        with patch.dict(
            os.environ,
            {"CORS_ORIGINS": "https://app.example.com, https://admin.example.com"},
        ):
            self.assertEqual(
                _configured_cors_origins(),
                ["https://app.example.com", "https://admin.example.com"],
            )

    @patch.dict(os.environ, {"COACH_ENGINE": "builtin"})
    def test_permitted_parallel_requests_receive_distinct_engine_sessions(self):
        barrier = threading.Barrier(2)
        seen_sessions = []
        responses = []
        errors = []
        seen_lock = threading.Lock()

        def analyze(session, _board, **_kwargs):
            with seen_lock:
                seen_sessions.append(session)
            barrier.wait(timeout=5)
            return {
                "best_move": chess.Move.from_uci("g1f3"),
                "score": 10,
                "eval_display": "+0.10",
                "winning_chance": 51.0,
                "pv": ["g1f3"],
                "depth": 1,
                "nodes": 10,
                "tt_hits": 0,
                "tt_cutoffs": 0,
                "tt_size": 1,
                "pvs_researches": 0,
                "lmr_reductions": 0,
                "lmr_researches": 0,
                "candidate_cache_hits": 0,
                "candidate_bound_skips": 0,
                "timed_out": False,
            }

        def request_analysis():
            try:
                response = self.client.post(
                    "/get_analysis",
                    json={
                        "fen": self.analysis_fen,
                        "depth": 1,
                        "time_limit": 0.2,
                    },
                )
                with seen_lock:
                    responses.append(response)
            except BaseException as exc:
                with seen_lock:
                    errors.append(exc)

        with (
            patch("api.engine_search_lock", threading.BoundedSemaphore(2)),
            patch(
                "api.chess_engine.EngineSession.analyze",
                autospec=True,
                side_effect=analyze,
            ),
            patch(
                "api.chess_engine.EngineSession.teaching_analysis",
                autospec=True,
                return_value={"candidates": []},
            ),
            patch("api.get_rag_engine", None),
        ):
            threads = [threading.Thread(target=request_analysis) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertEqual(len(seen_sessions), 2)
        self.assertIsNot(seen_sessions[0], seen_sessions[1])


if __name__ == "__main__":
    unittest.main()
