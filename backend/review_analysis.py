"""Bounded two-pass Stockfish reviews and short-lived, server-owned evidence."""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
import io
import os
import secrets
import threading
import time

import chess
import chess.engine
import chess.pgn
from fastapi import HTTPException

from coach_evidence import EvidenceSource

CACHE_TTL = 1800
CACHE_SIZE = 8
_cache = OrderedDict()
_cache_lock = threading.Lock()


class ReviewCancelled(Exception):
    pass


def parse_game(pgn):
    stream = io.StringIO(pgn)
    try:
        game = chess.pgn.read_game(stream)
        if not game or game.errors or game.board().chess960 or not game.board().is_valid():
            raise ValueError()
        if game.headers.get('Variant', 'Standard') not in {'Standard', 'Chess'}:
            raise ValueError()
        if chess.pgn.read_game(stream) is not None:
            raise ValueError()
        moves = list(game.mainline_moves())
        if not 1 <= len(moves) <= 400:
            raise ValueError()
        board = game.board()
        for move in moves:
            if board.is_game_over() or move not in board.legal_moves:
                raise ValueError()
            board.push(move)
        return game
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(422, '請提供一局合法的標準西洋棋棋譜（1–400 個半回合）。') from exc


def settings():
    return {
        'quick_nodes': min(200000, max(10000, int(os.getenv('STOCKFISH_REVIEW_QUICK_NODES', '50000')))),
        'deep_nodes': min(2000000, max(200000, int(os.getenv('STOCKFISH_REVIEW_DEEP_NODES', '500000')))),
        'max_refinements': min(40, max(1, int(os.getenv('STOCKFISH_REVIEW_MAX_REFINEMENTS', '12')))),
        'seconds': min(300, max(30, int(os.getenv('STOCKFISH_REVIEW_TIMEOUT_SECONDS', '180')))),
    }


def score_data(info):
    score = info['score'].pov(chess.WHITE)
    return {'cp': score.score(), 'mate': score.mate(), 'display': score.score(mate_score=100000)}


def wdl_data(info):
    if info.get('wdl') is None:
        return None
    wdl = info['wdl'].pov(chess.WHITE)
    return {'white_win': wdl.wins / 10, 'draw': wdl.draws / 10,
            'black_win': wdl.losses / 10, 'expected_score': (wdl.wins + wdl.draws / 2) / 10}


def classify(loss):
    if loss is None: return None
    if loss < 50: return 'good'
    if loss < 150: return 'inaccuracy'
    if loss < 300: return 'mistake'
    return 'blunder'


def pv_san(board, moves):
    board = board.copy()
    result = []
    for uci in moves[:10]:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        result.append(board.san(move))
        board.push(move)
    return ' '.join(result)


def inspect_position(engine, board, played, nodes, check):
    check()
    # Each query starts from a clean search state; pin engine options separately.
    best = engine.analyse(board, chess.engine.Limit(nodes=nodes, time=8), game=object())
    check()
    candidate = (best.get('pv') or [None])[0]
    actual = best
    if played and candidate != played:
        # Compare the discovered candidate and played move in the same search.
        compared = engine.analyse(board, chess.engine.Limit(nodes=nodes, time=8),
                                  root_moves=[candidate, played], multipv=2, game=object())
        check()
        found = {info['pv'][0]: info for info in compared if info.get('pv')}
        if candidate not in found or played not in found:
            raise ValueError('Incomplete candidate comparison')
        actual = found[played]
        best = max(found.values(), key=lambda info: info['score'].pov(board.turn))
    return {'fen': board.fen(), 'best_move': (best.get('pv') or [None])[0].uci() if best.get('pv') else None,
            'played_move': played.uci() if played else None,
            'best': score_data(best), 'played': score_data(actual),
            'best_pv': [move.uci() for move in best.get('pv', [])[:10]],
            'played_pv': [move.uci() for move in actual.get('pv', [])[:10]],
            'depth': min(best.get('depth', 0), actual.get('depth', 0)),
            'searched_nodes': best.get('nodes', 0), 'node_budget': nodes,
            'wdl': wdl_data(actual), 'best_wdl': wdl_data(best)}


def result_row(position, board, move, ply, perspective, level):
    best, played = position['best'], position['played']
    sign = 1 if board.turn else -1
    raw = sign * (best['cp'] - played['cp']) if best['cp'] is not None and played['cp'] is not None else None
    loss = max(0, raw) if raw is not None else None
    after = board.copy()
    after.push(move)
    return {'move_number': ply, 'side_to_move': 'white' if board.turn else 'black',
            'move': move.uci(), 'best_move': position['best_move'], 'fen': after.fen(),
            'score': played['display'], 'score_for': played['display'] * (1 if perspective == 'white' else -1),
            'best_eval_for': best['display'] * (1 if perspective == 'white' else -1),
            'raw_cp_loss': raw, 'cp_loss': loss, 'classification': classify(loss),
            'mate_threat': played['mate'] is not None, 'mate_in': played['mate'],
            'score_kind': 'mate' if played['mate'] is not None else 'cp',
            'is_checkmate': after.is_checkmate(), 'perspective': perspective,
            'wdl': position['wdl'], 'analysis_source': 'stockfish', 'review_level': level,
            'node_budget': position['node_budget'], 'depth': position['depth']}


def needs_refinement(row):
    loss = row['cp_loss']
    return loss is None or loss >= 50 or any(abs(loss - threshold) <= 25 for threshold in (50, 150, 300))


@dataclass
class Review:
    rows: list
    positions: list
    history: str
    engine: str
    config: dict
    completed_at: float = field(default_factory=time.monotonic)


def save_review(review):
    token = secrets.token_urlsafe(24)
    with _cache_lock:
        _cache[token] = review
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return token


def get_review(token, ply, fen):
    with _cache_lock:
        review = _cache.get(token)
        if review is None or time.monotonic() - review.completed_at > CACHE_TTL:
            _cache.pop(token, None)
            raise HTTPException(410, '分析依據已過期或服務已重啟，請重新分析這局。')
        if not 0 <= ply < len(review.positions) or review.positions[ply]['fen'] != fen:
            raise HTTPException(409, '所選局面與分析紀錄不一致，請重新選擇步數。')
        return review, deepcopy(review.positions[ply])


def run_review(game, path, perspective, emit, cancel, config=None):
    config = config or settings()
    start = time.monotonic()
    def check():
        if cancel.is_set(): raise ReviewCancelled()
        if time.monotonic() - start > config['seconds']:
            raise TimeoutError('Review time budget exceeded')
    boards, moves, board = [], list(game.mainline_moves()), game.board()
    for move in moves:
        boards.append(board.copy(stack=True))
        board.push(move)
    positions, rows = [], []
    engine = chess.engine.SimpleEngine.popen_uci(path, timeout=15)
    try:
        engine.configure({'Threads': 1, 'Hash': 64, 'UCI_ShowWDL': True})
        engine_name = engine.id.get('name', 'Stockfish')
        for index, (before, move) in enumerate(zip(boards, moves)):
            position = inspect_position(engine, before, move, config['quick_nodes'], check)
            position['level'] = 'quick'
            positions.append(position)
            rows.append(result_row(position, before, move, index + 1, perspective, 'quick'))
            emit({'type': 'progress', 'phase': 'quick', 'current': index + 1, 'total': len(moves)})
        candidates = [i for i, row in enumerate(rows) if needs_refinement(row)]
        candidates.sort(key=lambda i: rows[i]['cp_loss'] if rows[i]['cp_loss'] is not None else 100000, reverse=True)
        selected = candidates[:config['max_refinements']]
        for count, index in enumerate(selected, start=1):
            position = inspect_position(engine, boards[index], moves[index], config['deep_nodes'], check)
            position['level'] = 'deep'
            positions[index] = position
            rows[index] = result_row(position, boards[index], moves[index], index + 1, perspective, 'deep')
            emit({'type': 'progress', 'phase': 'deep', 'current': count, 'total': len(selected)})
        # The final board also needs server-owned evidence if it is selected.
        final = inspect_position(engine, board, None, config['quick_nodes'], check)
        final['level'] = 'quick'
        positions.append(final)
        first = positions[0]
        initial = {'move_number': 0, 'fen': first['fen'], 'score': first['best']['display'],
                   'score_for': first['best']['display'] * (1 if perspective == 'white' else -1),
                   'perspective': perspective, 'analysis_source': 'stockfish', 'review_level': first['level'],
                   'mate_in': first['best']['mate'], 'mate_threat': first['best']['mate'] is not None,
                   'score_kind': 'mate' if first['best']['mate'] is not None else 'cp', 'wdl': None}
        check()
        all_rows = [initial, *rows]
        # A chart point and the coach for that exact board share one evaluation.
        # The move's loss/classification still describes the preceding decision.
        for row, position in zip(all_rows, positions):
            score = position['best']
            row.update(score=score['display'], score_for=score['display'] * (1 if perspective == 'white' else -1),
                       mate_in=score['mate'], mate_threat=score['mate'] is not None,
                       score_kind='mate' if score['mate'] is not None else 'cp',
                       wdl=position['best_wdl'], position_level=position['level'])
        review = Review(all_rows, positions, game.accept(chess.pgn.StringExporter(variations=False, comments=False)), engine_name, config)
        token = save_review(review)
        emit({'type': 'complete', 'review_id': token, 'rows': review.rows, 'engine': engine_name,
              'quick_nodes': config['quick_nodes'], 'deep_nodes': config['deep_nodes'],
              'refined': len(selected), 'candidates': len(candidates), 'expires_in': CACHE_TTL})
    finally:
        engine.quit()


def review_sources(review, position):
    board = chess.Board(position['fen'])
    def score_text(score):
        if score['mate'] is not None:
            return f"白方視角將殺分數 {score['mate']}（正值為白方將殺，負值為黑方將殺）"
        return f"白方視角評分 {score['cp']}cp"
    level = '已加深複核' if position['level'] == 'deep' else '初評，尚未加深複核'
    best = board.parse_uci(position['best_move']) if position['best_move'] else None
    best_san = board.san(best) if best else '無合法手'
    sources = [EvidenceSource('R1', '賽後分析推薦',
        f"{review.engine} 本次搜尋推薦 {best_san}；{score_text(position['best'])}。{level}；節點上限 {position['node_budget']}，搜尋深度 {position['depth']}。有限搜尋不保證絕對最佳。", 'position')]
    if position['played_move']:
        move = board.parse_uci(position['played_move'])
        text = f"棋譜實際走了 {board.san(move)}；{score_text(position['played'])}。"
        if position['best']['cp'] is not None and position['played']['cp'] is not None:
            loss = max(0, (1 if board.turn else -1) * (position['best']['cp'] - position['played']['cp']))
            text += f"相對本次推薦手約損失 {loss}cp。"
        else:
            text += '分數涉及將殺，不使用一般百分兵掉分比較。'
        sources.append(EvidenceSource('R2', '實際走法比較', text, 'position'))
    for id_, label, key in [('R3', '推薦走法變例', 'best_pv'), ('R4', '實際走法變例', 'played_pv')]:
        line = pv_san(board, position[key])
        if line:
            sources.append(EvidenceSource(id_, label, f"{label}：{line}。這是本次搜尋的可能延續，不保證對手一定照走。", 'position'))
    analysis = {'best_move': position['best_move'], 'pv': position['best_pv']}
    return sources, analysis
