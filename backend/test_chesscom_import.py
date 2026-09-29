import copy
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from api import app
import chesscom_import as importer

PGN = '[White "Opponent"]\n[Black "Player"]\n[Result "0-1"]\n\n1. f3 e5 2. g4 Qh4# 0-1'
RAW = {"rules": "chess", "pgn": PGN, "url": "https://www.chess.com/game/live/123", "end_time": 1700000000, "time_class": "rapid", "time_control": "600"}


class ChessComImportTests(unittest.TestCase):
    def setUp(self):
        importer._cache.clear()
        self.requests = []
        self.client = TestClient(app)
        real_client = httpx.Client
        def respond(request):
            self.requests.append(str(request.url))
            if request.url.path.endswith('/archives'):
                return httpx.Response(200, json={"archives": [
                    f"{importer.BASE_URL}/player/games/2025/01",
                    f"{importer.BASE_URL}/player/games/2025/02",
                    "https://evil.example/2025/03",
                ]})
            return httpx.Response(200, json={"games": [copy.deepcopy(RAW)]})
        self.respond = respond
        self.mock = patch('chesscom_import.httpx.Client', side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(lambda req: self.respond(req)), **kwargs))
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_archives_are_sorted_and_untrusted_urls_are_not_followed(self):
        response = self.client.get('/imports/chesscom/Player/archives')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['months'], ['2025/02', '2025/01'])
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.client.get('/imports/chesscom/bad.name/archives').status_code, 422)
        self.assertEqual(len(self.requests), 1)

    def test_import_validates_pgn_detects_black_and_does_not_use_database(self):
        with patch('api.SessionLocal', side_effect=AssertionError('imports must not persist')):
            response = self.client.get('/imports/chesscom/PLAYER/2025/02')
        self.assertEqual(response.status_code, 200)
        game = response.json()['games'][0]
        self.assertEqual(game['perspective'], 'black')
        self.assertEqual(game['result'], '0-1')
        self.assertIn('Qh4#', game['pgn'])
        self.client.get('/imports/chesscom/player/2025/02')
        self.assertEqual(len(self.requests), 1)

    def test_invalid_variant_player_unfinished_and_oversized_games_are_rejected(self):
        variants = [dict(RAW, rules='chess960'), dict(RAW, url='javascript:alert(1)'),
                    dict(RAW, pgn=PGN.replace('0-1', '*')), dict(RAW, pgn='x' * 200001),
                    dict(RAW, pgn=PGN.replace('Player', 'SomeoneElse'))]
        for raw in variants:
            self.assertIsNone(importer.normalize_game(raw, 'player'))
        self.assertEqual(self.client.get('/imports/chesscom/player/2025/13').status_code, 422)
        self.assertEqual(self.client.get('/imports/chesscom/player/2025/02?page=-1').status_code, 422)

    def test_pagination_uses_newest_first_and_skips_invalid_records(self):
        games = [dict(RAW, end_time=1700000000+i, url=f'https://www.chess.com/game/live/{i}') for i in range(25)]
        games[-1]['pgn'] = ''
        self.respond = lambda req: httpx.Response(200, json={'games': games})
        first = self.client.get('/imports/chesscom/player/2025/02').json()
        second = self.client.get('/imports/chesscom/player/2025/02?page=1').json()
        self.assertEqual(first['games'][0]['end_time'], 1700000023)
        self.assertEqual(first['skipped'], 1)
        self.assertTrue(first['has_more'])
        self.assertEqual(len(second['games']), 5)
        self.assertFalse(second['has_more'])

    def test_provider_errors_are_actionable_and_not_cached(self):
        for code, expected in [(404, 404), (429, 429), (503, 502), (302, 502)]:
            self.respond = lambda req, code=code: httpx.Response(code)
            self.assertEqual(self.client.get('/imports/chesscom/player/archives').status_code, expected)
        self.respond = lambda req: httpx.Response(200, text='not json')
        self.assertEqual(self.client.get('/imports/chesscom/player/archives').status_code, 502)
        def timeout(req):
            raise httpx.ReadTimeout('offline')
        self.respond = timeout
        self.assertEqual(self.client.get('/imports/chesscom/player/archives').status_code, 504)
        self.assertEqual(len(importer._cache), 0)

    def test_response_size_limit(self):
        self.respond = lambda req: httpx.Response(200, content=b'x' * 200)
        with patch.object(importer, 'MAX_BYTES', 100):
            self.assertEqual(self.client.get('/imports/chesscom/player/archives').status_code, 502)


if __name__ == '__main__':
    unittest.main()
