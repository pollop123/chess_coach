import importlib
import os
import threading
import unittest
from unittest.mock import Mock, patch

import chess
import chess_engine


# lichess_bot validates credentials and constructs its API client at import
# time. Keep that external setup inert for this unit test.
with (
    patch.dict(os.environ, {"LICHESS_API_TOKEN": "test-token"}),
    patch("berserk.TokenSession", return_value=Mock()),
    patch("berserk.Client", return_value=Mock()),
):
    lichess_bot = importlib.import_module("lichess_bot")


class LichessBotSessionTests(unittest.TestCase):
    def test_parallel_games_use_distinct_engine_sessions(self):
        start_barrier = threading.Barrier(2)
        seen_sessions = []
        seen_lock = threading.Lock()
        errors = []

        fake_client = Mock()
        fake_client.account.get.return_value = {"id": "bot"}
        fake_client.bots.stream_game_state.side_effect = lambda _game_id: iter(
            [
                {
                    "type": "gameFull",
                    "state": {"moves": ""},
                    "white": {"id": "bot"},
                }
            ]
        )

        def analyze(engine_session, board, **kwargs):
            with seen_lock:
                seen_sessions.append(engine_session)
            start_barrier.wait(timeout=5)
            self.assertEqual(kwargs, {"depth": 3})
            return {"best_move": chess.Move.from_uci("e2e4")}

        def run_game(game_id):
            try:
                lichess_bot.play_game(game_id)
            except BaseException as exc:  # Surface thread failures to unittest.
                with seen_lock:
                    errors.append(exc)

        with (
            patch.object(lichess_bot, "client", fake_client),
            patch.object(lichess_bot, "LICHESS_TT_MAX_ENTRIES", 321),
            patch.object(
                chess_engine.EngineSession,
                "analyze",
                autospec=True,
                side_effect=analyze,
            ),
        ):
            threads = [
                threading.Thread(target=run_game, args=("game-a",)),
                threading.Thread(target=run_game, args=("game-b",)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(seen_sessions), 2)
        self.assertIsNot(seen_sessions[0], seen_sessions[1])
        self.assertEqual(
            [session.tt_max_entries for session in seen_sessions],
            [321, 321],
        )
        fake_client.bots.make_move.assert_any_call("game-a", "e2e4")
        fake_client.bots.make_move.assert_any_call("game-b", "e2e4")

    def test_capacity_rejects_excess_challenge_and_does_not_start_excess_game(self):
        fake_client = Mock()
        fake_client.account.get.return_value = {"id": "bot", "username": "Bot"}
        fake_client.bots.stream_incoming_events.return_value = iter(
            [
                {
                    "type": "challenge",
                    "challenge": {
                        "id": "game-a",
                        "challenger": {"name": "A"},
                        "speed": "rapid",
                    },
                },
                {
                    "type": "challenge",
                    "challenge": {
                        "id": "game-b",
                        "challenger": {"name": "B"},
                        "speed": "rapid",
                    },
                },
                {"type": "gameStart", "game": {"gameId": "game-a"}},
                {"type": "gameStart", "game": {"gameId": "game-b"}},
            ]
        )
        release_game = threading.Event()
        game_finished = threading.Event()
        started_games = []

        def hold_game(game_id):
            started_games.append(game_id)
            release_game.wait(timeout=5)
            game_finished.set()

        game_slots = threading.BoundedSemaphore(1)
        with (
            patch.object(lichess_bot, "client", fake_client),
            patch.object(lichess_bot, "MAX_CONCURRENT_GAMES", 1),
            patch.object(lichess_bot, "_game_slots", game_slots),
            patch.object(lichess_bot, "_reserved_challenges", set()),
            patch.object(lichess_bot, "play_game", side_effect=hold_game),
        ):
            lichess_bot.main()
            release_game.set()
            self.assertTrue(game_finished.wait(timeout=5))
            self.assertTrue(game_slots.acquire(timeout=5))
            game_slots.release()

        self.assertEqual(started_games, ["game-a"])
        fake_client.bots.accept_challenge.assert_called_once_with("game-a")
        fake_client.bots.decline_challenge.assert_called_once_with(
            "game-b",
            reason="later",
        )

    def test_failed_accept_and_thread_start_release_their_slots(self):
        fake_client = Mock()
        fake_client.account.get.return_value = {"id": "bot", "username": "Bot"}
        fake_client.bots.accept_challenge.side_effect = RuntimeError("accept failed")
        fake_client.bots.stream_incoming_events.return_value = iter(
            [
                {
                    "type": "challenge",
                    "challenge": {
                        "id": "challenge-a",
                        "challenger": {"name": "A"},
                        "speed": "rapid",
                    },
                },
                {"type": "gameStart", "game": {"gameId": "game-a"}},
            ]
        )
        game_slots = threading.BoundedSemaphore(1)
        failed_thread = Mock()
        failed_thread.start.side_effect = RuntimeError("thread failed")

        with (
            patch.object(lichess_bot, "client", fake_client),
            patch.object(lichess_bot, "_game_slots", game_slots),
            patch.object(lichess_bot, "_reserved_challenges", set()),
            patch.object(
                lichess_bot.threading,
                "Thread",
                return_value=failed_thread,
            ) as thread_factory,
        ):
            lichess_bot.main()
            thread_factory.assert_called_once_with(
                target=lichess_bot._play_game_with_slot,
                args=("game-a",),
                name="lichess-game-game-a",
                daemon=False,
            )
            self.assertTrue(game_slots.acquire(blocking=False))
            game_slots.release()


if __name__ == "__main__":
    unittest.main()
