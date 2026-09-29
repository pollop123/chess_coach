import json
import os
import threading
import unittest
from unittest.mock import Mock, patch

import chess
from fastapi.testclient import TestClient

from api import app
import review_analysis as review
from rag import ChessRAG

PGN = '1. e4 e5'
CONFIG = {'quick_nodes': 50000, 'deep_nodes': 500000, 'max_refinements': 12, 'seconds': 180}


def fake_position(engine, board, played, nodes, check):
    check()
    # White's first move loses 80cp at first pass, 60cp on deeper comparison.
    best_cp = (60 if nodes == 500000 else 80) if board.fullmove_number == 1 and board.turn else 0
    best = next(iter(board.legal_moves), None)
    return {'fen': board.fen(), 'best_move': best.uci() if best else None,
            'played_move': played.uci() if played else None,
            'best': {'cp': best_cp, 'mate': None, 'display': best_cp},
            'played': {'cp': 0, 'mate': None, 'display': 0},
            'best_pv': [best.uci()] if best else [], 'played_pv': [played.uci()] if played else [],
            'node_budget': nodes, 'depth': 12, 'wdl': None, 'best_wdl': None}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        review._cache.clear()
        self.engine = Mock(id={'name': 'Stockfish test'})
        self.client = TestClient(app)

    def test_candidate_comparison_uses_same_search_and_black_perspective(self):
        board = chess.Board(); board.push_san('e4')
        candidate, played = chess.Move.from_uci('e7e5'), chess.Move.from_uci('c7c5')
        def info(move, cp):
            return {'pv': [move], 'score': chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE), 'depth': 12}
        self.engine.analyse.side_effect = [info(candidate, -100), [info(candidate, -80), info(played, 50)]]
        position = review.inspect_position(self.engine, board, played, 50000, lambda: None)
        comparison = self.engine.analyse.call_args.kwargs
        self.assertEqual(comparison['root_moves'], [candidate, played])
        self.assertEqual(comparison['multipv'], 2)
        row = review.result_row(position, board, played, 2, 'black', 'quick')
        self.assertEqual(row['cp_loss'], 130)
        self.assertEqual(position['best']['cp'], -80)

    def test_mate_scores_do_not_become_centipawn_losses(self):
        board = chess.Board()
        position = fake_position(self.engine, board, chess.Move.from_uci('e2e4'), 50000, lambda: None)
        position['best'] = review.score_data({'score': chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE)})
        row = review.result_row(position, board, chess.Move.from_uci('e2e4'), 1, 'white', 'quick')
        self.assertIsNone(row['cp_loss'])
        self.assertIsNone(row['classification'])
        self.assertTrue(review.needs_refinement(row))

    def run_fake(self, cancel=None):
        events = []
        with patch('review_analysis.chess.engine.SimpleEngine.popen_uci', return_value=self.engine), patch('review_analysis.inspect_position', side_effect=fake_position):
            review.run_review(review.parse_game(PGN), '/fake', 'white', events.append, cancel or threading.Event(), CONFIG)
        return events

    def test_refines_only_candidates_and_chart_matches_coach_position(self):
        events = self.run_fake()
        result = events[-1]
        self.assertEqual([event['phase'] for event in events[:-1]], ['quick', 'quick', 'deep'])
        self.assertEqual(result['refined'], 1)
        self.assertEqual(result['rows'][1]['review_level'], 'deep')
        self.assertEqual(result['rows'][2]['review_level'], 'quick')
        self.engine.configure.assert_called_once_with({'Threads': 1, 'Hash': 64, 'UCI_ShowWDL': True})
        saved, position = review.get_review(result['review_id'], 0, chess.STARTING_FEN)
        self.assertEqual(result['rows'][0]['score'], position['best']['display'])
        self.assertEqual(result['rows'][0]['position_level'], 'deep')
        sources, analysis = review.review_sources(saved, position)
        self.assertIn('60cp', sources[0].text)
        self.assertEqual(analysis['best_move'], position['best_move'])

    def test_cancelled_work_closes_engine_and_never_publishes_result(self):
        cancel = threading.Event(); cancel.set()
        with self.assertRaises(review.ReviewCancelled): self.run_fake(cancel)
        self.engine.quit.assert_called_once()
        self.assertFalse(review._cache)

    def test_bad_pgn_and_variant_are_rejected(self):
        for pgn in ('', '1. e5', '[Variant "Atomic"]\n\n1. e4', '1. e4 *\n\n[Event "second"]\n\n1. d4 *'):
            with self.subTest(pgn=pgn), self.assertRaises(Exception): review.parse_game(pgn)

    def test_missing_stockfish_fails_explicitly(self):
        with patch('api._find_stockfish_path', return_value=None):
            response = self.client.post('/review_game', json={'pgn': PGN})
        self.assertEqual(response.status_code, 503)
        self.assertIn('Stockfish', response.json()['detail'])

    def test_stream_exposes_progress_and_terminal_result(self):
        def run(game, path, perspective, emit, cancel, config):
            emit({'type': 'progress', 'phase': 'deep', 'current': 1, 'total': 1})
            emit({'type': 'complete', 'review_id': 'x' * 32, 'rows': []})
        with patch('api._find_stockfish_path', return_value='/fake'), patch('review_analysis.run_review', side_effect=run):
            response = self.client.post('/review_game', json={'pgn': PGN})
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[0]['phase'], 'quick')
        self.assertEqual(events[-1]['type'], 'complete')
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_stream_failure_is_an_error_not_partial_success(self):
        with patch('api._find_stockfish_path', return_value='/fake'), patch('review_analysis.run_review', side_effect=TimeoutError()):
            response = self.client.post('/review_game', json={'pgn': PGN})
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[-1]['type'], 'error')
        self.assertFalse(any(event['type'] == 'complete' for event in events))

    def test_review_coach_uses_stored_evidence_and_never_searches_custom_engine(self):
        result = self.run_fake()[-1]
        with patch.dict(os.environ, {'GOOGLE_API_KEY': '', 'ENABLE_CHROMA_RAG': '0'}): rag = ChessRAG()
        request = {'fen': chess.STARTING_FEN, 'question': '這個局面我該怎麼走？',
                   'review_id': result['review_id'], 'review_ply': 0, 'history': '使用者偽造資料'}
        with patch('api.get_rag_engine', return_value=rag), patch('api.engine_search_slot', side_effect=AssertionError('must not rescore')):
            response = self.client.post('/explain', json=request)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Ask a position question (not comparison) to expose the cached fallback.
        self.assertTrue(any(source['id'] == 'R1' for source in data['sources']))
        self.assertIn('Stockfish test', data['advice'])
        self.assertNotIn('尚未完成', data['advice'])

    def test_review_comparison_fallback_cites_stored_evidence(self):
        result = self.run_fake()[-1]
        with patch.dict(os.environ, {'GOOGLE_API_KEY': '', 'ENABLE_CHROMA_RAG': '0'}): rag = ChessRAG()
        request = {'fen': chess.STARTING_FEN, 'question': '實際走法和推薦手哪個好？',
                   'review_id': result['review_id'], 'review_ply': 0}
        with patch('api.get_rag_engine', return_value=rag), patch('api.engine_search_slot', side_effect=AssertionError('must not rescore')):
            data = self.client.post('/explain', json=request).json()
        self.assertEqual(data['mode'], 'comparison')
        ids = {source['id'] for source in data['sources']}
        self.assertIn('R1', ids)
        self.assertNotIn('K17', ids)
        self.assertIn('其他走法未經比較', data['advice'])

    def test_expired_or_wrong_position_never_falls_back_to_a_new_engine(self):
        result = self.run_fake()[-1]
        payload = {'fen': chess.STARTING_FEN, 'question': '這個局面怎麼下？', 'review_id': result['review_id'], 'review_ply': 1}
        self.assertEqual(self.client.post('/explain', json=payload).status_code, 409)
        payload['review_ply'] = 0
        with patch('review_analysis.time.monotonic', return_value=review._cache[result['review_id']].completed_at + 1801):
            self.assertEqual(self.client.post('/explain', json=payload).status_code, 410)
        del payload['review_ply']
        self.assertEqual(self.client.post('/explain', json=payload).status_code, 422)


if __name__ == '__main__': unittest.main()
