import math
import threading
import time
import unittest

import chess

import chess_engine


class EngineSessionTests(unittest.TestCase):
    def setUp(self):
        chess_engine.reset_transposition_table()

    def test_sessions_isolate_tt_stats_deadline_and_generation(self):
        first = chess_engine.EngineSession()
        second = chess_engine.EngineSession()
        board = chess.Board()
        deadline = time.monotonic() + 60

        with first.activate():
            chess_engine.begin_search_generation(deadline=deadline)
            chess_engine.minimax(board, 1, -math.inf, math.inf, True)
            first_nodes = chess_engine.search_stats["nodes"]
            self.assertTrue(chess_engine.transposition_table)
            self.assertEqual(chess_engine.search_runtime.deadline, deadline)

        with second.activate():
            self.assertEqual(chess_engine.transposition_table, {})
            self.assertEqual(chess_engine.search_stats["nodes"], 0)
            self.assertIsNone(chess_engine.search_runtime.deadline)
            chess_engine.begin_search_generation()
            chess_engine.minimax(board, 1, -math.inf, math.inf, True)

        self.assertGreater(first_nodes, 0)
        self.assertIsNot(first.transposition_table, second.transposition_table)
        self.assertNotEqual(first.tt_generation, 0)
        self.assertNotEqual(second.tt_generation, 0)
        self.assertEqual(chess_engine.transposition_table, {})

    def test_nested_activation_restores_the_outer_session(self):
        outer = chess_engine.EngineSession()
        inner = chess_engine.EngineSession()

        with outer.activate():
            self.assertIs(chess_engine.current_engine_session(), outer)
            with inner.activate():
                self.assertIs(chess_engine.current_engine_session(), inner)
            self.assertIs(chess_engine.current_engine_session(), outer)

    def test_activation_is_restored_after_exception(self):
        session = chess_engine.EngineSession()
        default_session = chess_engine.current_engine_session()

        with self.assertRaisesRegex(RuntimeError, "boom"):
            with session.activate():
                self.assertIs(chess_engine.current_engine_session(), session)
                raise RuntimeError("boom")

        self.assertIs(chess_engine.current_engine_session(), default_session)

    def test_timeout_in_one_thread_does_not_cancel_another_session(self):
        timeout_session = chess_engine.EngineSession()
        healthy_session = chess_engine.EngineSession()
        timeout_board = chess.Board()
        timeout_fen = timeout_board.fen()
        barrier = threading.Barrier(2)
        outcomes = {}

        def timeout_worker():
            with timeout_session.activate():
                chess_engine.begin_search_generation(deadline=0)
                chess_engine.search_stats["nodes"] = 63
                barrier.wait()
                try:
                    chess_engine.minimax(
                        timeout_board,
                        2,
                        -math.inf,
                        math.inf,
                        True,
                    )
                except chess_engine.SearchTimeout:
                    outcomes["timeout"] = True

        def healthy_worker():
            with healthy_session.activate():
                chess_engine.begin_search_generation()
                barrier.wait()
                outcomes["healthy"] = chess_engine.minimax(
                    chess.Board(),
                    1,
                    -math.inf,
                    math.inf,
                    True,
                )

        threads = [
            threading.Thread(target=timeout_worker),
            threading.Thread(target=healthy_worker),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertTrue(outcomes.get("timeout"))
        self.assertIsNotNone(outcomes.get("healthy", (None,))[1])
        self.assertGreater(healthy_session.stats["nodes"], 0)
        self.assertEqual(timeout_board.fen(), timeout_fen)
        self.assertEqual(chess_engine.transposition_table, {})

    def test_parallel_sessions_return_the_same_analysis_and_restore_boards(self):
        barrier = threading.Barrier(2)
        boards = [chess.Board(), chess.Board()]
        original_fen = chess.STARTING_FEN
        results = [None, None]

        def worker(index):
            barrier.wait()
            results[index] = chess_engine.EngineSession().analyze(
                boards[index],
                depth=2,
                use_book=False,
                adaptive_depth=False,
            )

        threads = [
            threading.Thread(target=worker, args=(0,)),
            threading.Thread(target=worker, args=(1,)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertEqual(
            (results[0]["best_move"], results[0]["score"], results[0]["pv"]),
            (results[1]["best_move"], results[1]["score"], results[1]["pv"]),
        )
        self.assertEqual([board.fen() for board in boards], [original_fen, original_fen])

    def test_tt_disabled_analysis_does_not_touch_the_session_table(self):
        session = chess_engine.EngineSession()

        result = session.analyze(
            chess.Board(),
            depth=2,
            use_book=False,
            adaptive_depth=False,
            use_tt=False,
        )

        self.assertIsNotNone(result["best_move"])
        self.assertEqual(session.transposition_table, {})
        self.assertEqual(session.stats["tt_hits"], 0)

    def test_session_can_override_evaluator_without_global_mutation(self):
        class ConstantEvaluator:
            def score(self, _board, _ply=0):
                return 321

        session = chess_engine.EngineSession(evaluator=ConstantEvaluator())
        default_score = chess_engine.evaluate_board(chess.Board())

        with session.activate():
            self.assertEqual(chess_engine.evaluate_board(chess.Board()), 321)

        self.assertEqual(chess_engine.evaluate_board(chess.Board()), default_score)

    def test_main_and_teaching_analysis_reuse_one_session_table(self):
        session = chess_engine.EngineSession()
        board = chess.Board(
            "r1bq1rk1/pp2bppp/2n1pn2/2pp4/8/1PN1PN2/"
            "PBP1BPPP/R2Q1RK1 w - - 0 9"
        )

        base = session.analyze(
            board,
            depth=2,
            use_book=False,
            adaptive_depth=False,
        )
        table_identity = id(session.transposition_table)
        keys_after_main = set(session.transposition_table)
        generation_after_main = session.tt_generation

        teaching = session.teaching_analysis(
            board,
            base,
            candidate_count=2,
            depth=1,
        )

        self.assertTrue(keys_after_main)
        self.assertEqual(id(session.transposition_table), table_identity)
        self.assertTrue(keys_after_main.issubset(session.transposition_table))
        self.assertGreater(session.tt_generation, generation_after_main)
        self.assertEqual(len(teaching["candidates"]), 2)
        self.assertEqual(
            board.fen(),
            "r1bq1rk1/pp2bppp/2n1pn2/2pp4/8/1PN1PN2/"
            "PBP1BPPP/R2Q1RK1 w - - 0 9",
        )


if __name__ == "__main__":
    unittest.main()
