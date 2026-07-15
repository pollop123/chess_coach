import chess
import math
import chess.polyglot
import os
import threading
import time
from dataclasses import dataclass

from evaluation import (
    BISHOP_TABLE,
    DEFAULT_EVALUATOR,
    KING_TABLE_ENDGAME,
    KING_TABLE_OPENING,
    KNIGHT_TABLE,
    MATE_SCORE,
    PAWN_TABLE,
    PIECE_VALUES,
    QUEEN_TABLE,
    ROOK_TABLE,
    get_piece_square_value,
    middlegame_king_exposure_penalty,
)

# Transposition table shared across iterative-deepening passes and requests.
transposition_table = {}
TT_MAX_ENTRIES = 200_000
TT_EXACT = "exact"
TT_LOWER = "lower"
TT_UPPER = "upper"
tt_generation = 0
search_stats = {
    "nodes": 0,
    "tt_hits": 0,
    "tt_cutoffs": 0,
    "pvs_researches": 0,
    "candidate_cache_hits": 0,
    "candidate_bound_skips": 0,
}
search_runtime = threading.local()
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_PATH = os.path.join(ENGINE_DIR, "books", "gm2001.bin")

# --- 評估與搜尋合約常數 ---
MATE_THRESHOLD = 15000
ONLY_MOVE_LOSS_CP = 250

# Backwards-compatible aliases for search helpers and external callers. The
# authoritative definitions now live under backend/evaluation/.
piece_values = PIECE_VALUES
pawntable = PAWN_TABLE
knightstable = KNIGHT_TABLE
bishopstable = BISHOP_TABLE
rookstable = ROOK_TABLE
queenstable = QUEEN_TABLE
king_table_opening = KING_TABLE_OPENING
king_table_endgame = KING_TABLE_ENDGAME

DIFFICULTY_MOVE_PROFILES = {
    "newbie": {"target_loss": 220, "max_loss": 350, "error_rate": 60, "candidates": 18},
    "beginner": {"target_loss": 140, "max_loss": 240, "error_rate": 45, "candidates": 16},
    "intermediate": {"target_loss": 60, "max_loss": 110, "error_rate": 25, "candidates": 14},
    "advanced": {"target_loss": 0, "max_loss": 20, "error_rate": 0, "candidates": 12},
    "challenge": {"target_loss": 0, "max_loss": 20, "error_rate": 0, "candidates": 12},
}


@dataclass(frozen=True)
class TTEntry:
    depth: int
    score: int | float
    flag: str
    best_move: chess.Move | None
    generation: int


class SearchTimeout(Exception):
    pass


def visit_search_node():
    search_stats["nodes"] += 1
    if search_stats["nodes"] % 64 != 0:
        return
    deadline = getattr(search_runtime, "deadline", None)
    if deadline is not None and time.monotonic() >= deadline:
        raise SearchTimeout


def tt_key(board):
    return chess.polyglot.zobrist_hash(board), board.halfmove_clock


def build_repetition_counts(board):
    counts = {}
    history = board.copy(stack=True)
    while True:
        position_hash = chess.polyglot.zobrist_hash(history)
        counts[position_hash] = counts.get(position_hash, 0) + 1
        if not history.move_stack:
            break
        history.pop()
    return counts


def push_repetition(repetition_counts, board):
    position_hash = chess.polyglot.zobrist_hash(board)
    repetition_counts[position_hash] = repetition_counts.get(position_hash, 0) + 1
    return position_hash


def pop_repetition(repetition_counts, position_hash):
    remaining = repetition_counts[position_hash] - 1
    if remaining:
        repetition_counts[position_hash] = remaining
    else:
        repetition_counts.pop(position_hash)


def score_to_tt(score, ply_from_root):
    if score > MATE_THRESHOLD:
        return score + ply_from_root
    if score < -MATE_THRESHOLD:
        return score - ply_from_root
    return score


def score_from_tt(score, ply_from_root):
    if score > MATE_THRESHOLD:
        return score - ply_from_root
    if score < -MATE_THRESHOLD:
        return score + ply_from_root
    return score


def store_tt(key, depth, score, flag, best_move, ply_from_root):
    current = transposition_table.get(key)
    if current and current.generation == tt_generation and current.depth > depth:
        return

    if key not in transposition_table and len(transposition_table) >= TT_MAX_ENTRIES:
        transposition_table.pop(next(iter(transposition_table)))

    transposition_table[key] = TTEntry(
        depth=depth,
        score=score_to_tt(score, ply_from_root),
        flag=flag,
        best_move=best_move,
        generation=tt_generation,
    )


def begin_search_generation(deadline=None):
    global tt_generation
    tt_generation += 1
    search_stats.update(
        nodes=0,
        tt_hits=0,
        tt_cutoffs=0,
        pvs_researches=0,
        candidate_cache_hits=0,
        candidate_bound_skips=0,
    )
    search_runtime.deadline = deadline

    if len(transposition_table) > TT_MAX_ENTRIES // 2:
        oldest_allowed = tt_generation - 2
        stale_keys = [
            key for key, entry in transposition_table.items()
            if entry.generation < oldest_allowed
        ]
        for key in stale_keys:
            transposition_table.pop(key, None)


def reset_transposition_table():
    transposition_table.clear()
    search_stats.update(
        nodes=0,
        tt_hits=0,
        tt_cutoffs=0,
        pvs_researches=0,
        candidate_cache_hits=0,
        candidate_bound_skips=0,
    )
    search_runtime.deadline = None

def format_evaluation(score):
    """將 centipawn 分數格式化為用戶友好的顯示"""
    if abs(score) > MATE_THRESHOLD:
        plies_to_mate = max(1, MATE_SCORE - abs(score))
        moves_to_mate = max(1, math.ceil(plies_to_mate / 2))
        return f"M{moves_to_mate}" if score > 0 else f"-M{moves_to_mate}"
    else:
        # 一般局面：轉換為兵值
        return f"{score/100:+.2f}"

def calculate_winning_chance(score):
    """使用 Sigmoid 函數計算勝率 (0-100%)"""
    if abs(score) > MATE_THRESHOLD:
        return 100.0 if score > 0 else 0.0
    # Sigmoid: 1 / (1 + e^(-0.00368 * cp))
    try:
        win_prob = 1.0 / (1.0 + math.exp(-0.00368 * score))
        return round(win_prob * 100, 1)
    except OverflowError:
        return 100.0 if score > 0 else 0.0

def order_moves(board, tt_best_move=None):
    moves = list(board.legal_moves)
    
    def score_move(move):
        if move == tt_best_move:
            return 1000000
        
        score = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)
            if victim and attacker:
                score += piece_values.get(victim.piece_type, 0) * 10 - piece_values.get(attacker.piece_type, 0)
        
        if move.promotion:
            score += piece_values.get(move.promotion, 0)

        if board.gives_check(move):
            score += 80

        to_file = chess.square_file(move.to_square)
        to_rank = chess.square_rank(move.to_square)
        if 2 <= to_file <= 5 and 2 <= to_rank <= 5:
            score += 20
            
        return score

    return sorted(moves, key=score_move, reverse=True)

def choose_book_entry(reader, board):
    """Return the highest-weight Polyglot entry for deterministic book play."""
    entries = list(reader.find_all(board))
    if not entries:
        return None
    return max(entries, key=lambda entry: entry.weight)

def build_book_line(reader, board, first_move, max_plies=6):
    """Build a short SAN book line from the current position."""
    line = []
    current = board.copy()

    if first_move not in current.legal_moves:
        return line

    line.append(current.san(first_move))
    current.push(first_move)

    for _ in range(max_plies - 1):
        entry = choose_book_entry(reader, current)
        if not entry or entry.move not in current.legal_moves:
            break
        line.append(current.san(entry.move))
        current.push(entry.move)

    return line

def evaluate_board(board, ply_from_root=0):
    """Compatibility score entrypoint used by search and API fallbacks."""
    return DEFAULT_EVALUATOR.score(board, ply_from_root)


def evaluate_position(board, ply_from_root=0):
    """Return the modular evaluator's score, phase, and component breakdown."""
    return DEFAULT_EVALUATOR.evaluate(board, ply_from_root)

def quiescence_search(board, alpha, beta, q_depth=0, ply_from_root=0):
    visit_search_node()
    if board.is_game_over():
        return evaluate_board(board, ply_from_root)

    if q_depth > 10:
        return evaluate_board(board, ply_from_root)

    in_check = board.is_check()
    stand_pat = evaluate_board(board, ply_from_root)
    if in_check:
        tactical_moves = order_moves(board)
    else:
        tactical_moves = [
            move for move in order_moves(board)
            if board.is_capture(move) or move.promotion
        ]

    if board.turn == chess.WHITE:
        if not in_check:
            if stand_pat >= beta: return beta
            if stand_pat > alpha: alpha = stand_pat

        for move in tactical_moves:
            board.push(move)
            try:
                score = quiescence_search(board, alpha, beta, q_depth + 1, ply_from_root + 1)
            finally:
                board.pop()
            if score >= beta: return beta
            if score > alpha: alpha = score
        return alpha

    if not in_check:
        if stand_pat <= alpha: return alpha
        if stand_pat < beta: beta = stand_pat

    for move in tactical_moves:
        board.push(move)
        try:
            score = quiescence_search(board, alpha, beta, q_depth + 1, ply_from_root + 1)
        finally:
            board.pop()
        if score <= alpha: return alpha
        if score < beta: beta = score
    return beta

def minimax(
    board,
    depth,
    alpha,
    beta,
    maximizing_player,
    ply_from_root=0,
    repetition_counts=None,
):
    visit_search_node()
    if repetition_counts is None:
        repetition_counts = build_repetition_counts(board)
    position_hash = chess.polyglot.zobrist_hash(board)
    is_repetition = repetition_counts.get(position_hash, 0) >= 2
    if is_repetition:
        if depth == 0: 
             return evaluate_board(board, ply_from_root), None

    alpha_original = alpha
    beta_original = beta
    key = tt_key(board)
    entry = None if is_repetition else transposition_table.get(key)
    tt_move = entry.best_move if entry else None

    if entry:
        search_stats["tt_hits"] += 1
        cached_score = score_from_tt(entry.score, ply_from_root)
        if entry.depth >= depth:
            if entry.flag == TT_EXACT:
                search_stats["tt_cutoffs"] += 1
                return cached_score, entry.best_move
            if entry.flag == TT_LOWER:
                alpha = max(alpha, cached_score)
            elif entry.flag == TT_UPPER:
                beta = min(beta, cached_score)
            if alpha >= beta:
                search_stats["tt_cutoffs"] += 1
                return cached_score, entry.best_move

    if depth == 0 or board.is_game_over():
        if board.is_game_over():
            val = evaluate_board(board, ply_from_root)
        else:
            val = quiescence_search(board, alpha, beta, ply_from_root=ply_from_root)
        
        if val <= alpha_original:
            flag = TT_UPPER
        elif val >= beta_original:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        if not is_repetition:
            store_tt(key, depth, val, flag, None, ply_from_root)
        return val, None

    moves = order_moves(board, tt_move) 

    best_move = None
    if maximizing_player:
        max_eval = -math.inf
        for move_index, move in enumerate(moves):
            board.push(move)
            child_hash = push_repetition(repetition_counts, board)
            try:
                if move_index == 0:
                    eval_score, _ = minimax(
                        board, depth - 1, alpha, beta, False, ply_from_root + 1,
                        repetition_counts
                    )
                else:
                    eval_score, _ = minimax(
                        board, depth - 1, alpha, alpha + 1, False, ply_from_root + 1,
                        repetition_counts
                    )
                    if alpha < eval_score < beta:
                        search_stats["pvs_researches"] += 1
                        eval_score, _ = minimax(
                            board, depth - 1, alpha, beta, False, ply_from_root + 1,
                            repetition_counts
                        )
            finally:
                pop_repetition(repetition_counts, child_hash)
                board.pop()
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha: break 
        if max_eval <= alpha_original:
            flag = TT_UPPER
        elif max_eval >= beta_original:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        if not is_repetition:
            store_tt(key, depth, max_eval, flag, best_move, ply_from_root)
        return max_eval, best_move
    else:
        min_eval = math.inf
        for move_index, move in enumerate(moves):
            board.push(move)
            child_hash = push_repetition(repetition_counts, board)
            try:
                if move_index == 0:
                    eval_score, _ = minimax(
                        board, depth - 1, alpha, beta, True, ply_from_root + 1,
                        repetition_counts
                    )
                else:
                    eval_score, _ = minimax(
                        board, depth - 1, beta - 1, beta, True, ply_from_root + 1,
                        repetition_counts
                    )
                    if alpha < eval_score < beta:
                        search_stats["pvs_researches"] += 1
                        eval_score, _ = minimax(
                            board, depth - 1, alpha, beta, True, ply_from_root + 1,
                            repetition_counts
                        )
            finally:
                pop_repetition(repetition_counts, child_hash)
                board.pop()
            
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha: break
        if min_eval <= alpha_original:
            flag = TT_UPPER
        elif min_eval >= beta_original:
            flag = TT_LOWER
        else:
            flag = TT_EXACT
        if not is_repetition:
            store_tt(key, depth, min_eval, flag, best_move, ply_from_root)
        return min_eval, best_move

# 🔥 補上：你漏掉了這個函式
def get_pv_line(board, depth):
    """從置換表 (TT) 重建預測變例 (Principal Variation)"""
    pv_line = []
    curr_board = board.copy()
    for _ in range(depth):
        entry = transposition_table.get(tt_key(curr_board))

        if entry and entry.best_move and entry.best_move in curr_board.legal_moves:
            move = entry.best_move
            pv_line.append(move.uci())
            curr_board.push(move)
        else:
            break
    return pv_line

def major_piece_loss_after_move(board, move):
    """Return True when a style candidate permits an immediate bad major-piece trade."""
    mover = board.turn
    moving_piece = board.piece_at(move.from_square)
    captured_piece = board.piece_at(move.to_square) if board.is_capture(move) else None
    captured_value = piece_values.get(captured_piece.piece_type, 0) if captured_piece else 0

    board.push(move)
    if board.is_checkmate():
        board.pop()
        return False

    for reply in board.legal_moves:
        if not board.is_capture(reply):
            continue

        target = board.piece_at(reply.to_square)
        attacker = board.piece_at(reply.from_square)
        if not target or not attacker or target.color != mover:
            continue
        if target.piece_type not in {chess.ROOK, chess.QUEEN}:
            continue

        target_value = piece_values[target.piece_type]
        attacker_value = piece_values[attacker.piece_type]
        uncompensated_loss = target_value - captured_value
        if uncompensated_loss >= 300 and target_value - attacker_value >= 150:
            board.pop()
            return True

    board.pop()
    return False


def score_trickster_move(board, move):
    """Heuristic bonus for moves that create practical traps for humans."""
    mover = board.turn
    bonus = 0

    if board.gives_check(move):
        bonus += 100

    captured = board.piece_at(move.to_square)
    if captured:
        bonus += min(90, piece_values.get(captured.piece_type, 0) // 8)

    board.push(move)

    opponent_replies = board.legal_moves.count()
    bonus += max(0, 28 - opponent_replies) * 4

    enemy_king = board.king(not mover)
    if enemy_king is not None:
        king_zone = [enemy_king, *chess.SquareSet(chess.BB_KING_ATTACKS[enemy_king])]
        attacked_king_zone = sum(1 for square in king_zone if board.is_attacked_by(mover, square))
        bonus += attacked_king_zone * 12

    attacked_material = 0
    for square, piece in board.piece_map().items():
        if piece.color != mover and board.is_attacked_by(mover, square):
            attacked_material += piece_values.get(piece.piece_type, 0)
    bonus += min(140, attacked_material // 12)

    board.pop()
    return bonus


def should_apply_difficulty_error(board, profile):
    error_rate = profile["error_rate"]
    if error_rate <= 0:
        return False
    position_bucket = (chess.polyglot.zobrist_hash(board) >> 40) % 100
    return position_bucket < error_rate


def select_difficulty_move(board, depth, best_move, best_score, difficulty, style):
    """Select a reproducible, safe move from a difficulty-specific loss band."""
    if best_move is None:
        return best_move, best_score, 0, 0

    mover = board.turn
    profile = DIFFICULTY_MOVE_PROFILES.get(difficulty, DIFFICULTY_MOVE_PROFILES["advanced"])
    candidate_depth = max(1, depth - 1)
    candidates = []
    ordered_candidates = order_moves(board)[:profile["candidates"]]
    candidate_moves = [best_move, *[move for move in ordered_candidates if move != best_move]]

    for move in candidate_moves:
        if major_piece_loss_after_move(board, move):
            continue

        try:
            board.push(move)
            try:
                cached_entry = transposition_table.get(tt_key(board))
                cached_score = None
                if cached_entry and cached_entry.depth >= candidate_depth:
                    cached_score = score_from_tt(cached_entry.score, 1)
                    if cached_entry.flag == TT_EXACT:
                        search_stats["candidate_cache_hits"] += 1
                    elif candidates:
                        bound_is_upper = (
                            mover == chess.WHITE and cached_entry.flag == TT_UPPER
                        ) or (
                            mover == chess.BLACK and cached_entry.flag == TT_LOWER
                        )
                        bound_perspective = cached_score if mover == chess.WHITE else -cached_score
                        best_known = max(item["perspective_score"] for item in candidates)
                        if bound_is_upper and bound_perspective < best_known - profile["max_loss"]:
                            search_stats["candidate_bound_skips"] += 1
                            continue

                if cached_entry and cached_entry.depth >= candidate_depth and cached_entry.flag == TT_EXACT:
                    score = cached_score
                elif board.is_game_over():
                    score = evaluate_board(board, 1)
                else:
                    score, _ = minimax(
                        board,
                        candidate_depth,
                        -math.inf,
                        math.inf,
                        board.turn == chess.WHITE,
                        1,
                    )
            finally:
                board.pop()
        except SearchTimeout:
            break

        perspective_score = score if mover == chess.WHITE else -score
        bonus = score_trickster_move(board, move) if style == "trickster" else 0
        candidates.append({
            "move": move,
            "score": score,
            "perspective_score": perspective_score,
            "bonus": bonus,
        })

    if not candidates:
        return best_move, best_score, 0, 0

    best_perspective = max(item["perspective_score"] for item in candidates)
    for item in candidates:
        item["loss"] = max(0, best_perspective - item["perspective_score"])

    viable_candidates = [item for item in candidates if item["loss"] <= profile["max_loss"]]
    if not viable_candidates:
        return best_move, best_score, 0, 0

    target_loss = profile["target_loss"] if should_apply_difficulty_error(board, profile) else 0

    def selection_key(item):
        style_influence = min(item["bonus"], 35) if style == "trickster" else 0
        return (-abs(item["loss"] - target_loss) + style_influence, item["perspective_score"])

    selected = max(viable_candidates, key=selection_key)
    return selected["move"], selected["score"], selected["bonus"], selected["loss"]


def select_trickster_move(board, depth, best_move, best_score):
    """Backward-compatible wrapper for the intermediate trap personality."""
    move, score, bonus, _loss = select_difficulty_move(
        board, depth, best_move, best_score, "intermediate", "trickster"
    )
    return move, score, bonus


def _move_attacks_king_zone(board, move):
    mover = board.turn
    board.push(move)
    try:
        enemy_king = board.king(not mover)
        if enemy_king is None:
            return False
        king_zone = [enemy_king, *chess.SquareSet(chess.BB_KING_ATTACKS[enemy_king])]
        return any(board.is_attacked_by(mover, square) for square in king_zone)
    finally:
        board.pop()


def _king_zone_pressure(board, attacker, king_color):
    king_square = board.king(king_color)
    if king_square is None:
        return 0
    king_zone = [king_square, *chess.SquareSet(chess.BB_KING_ATTACKS[king_square])]
    return sum(board.is_attacked_by(attacker, square) for square in king_zone)


def _move_increases_enemy_king_pressure(board, move):
    mover = board.turn
    before = _king_zone_pressure(board, mover, not mover)
    board.push(move)
    try:
        after = _king_zone_pressure(board, mover, not mover)
        return after > before
    finally:
        board.pop()


def _move_improves_own_king_safety(board, move):
    mover = board.turn
    before = _king_zone_pressure(board, not mover, mover)
    board.push(move)
    try:
        after = _king_zone_pressure(board, not mover, mover)
        return after < before
    finally:
        board.pop()


def _move_controls_center(board, move):
    mover = board.turn
    board.push(move)
    try:
        piece = board.piece_at(move.to_square)
        if not piece or piece.color != mover:
            return False
        center = chess.SquareSet(chess.BB_CENTER)
        return bool(board.attacks(move.to_square) & center)
    finally:
        board.pop()


def _captured_piece(board, move):
    if not board.is_capture(move):
        return None
    if board.is_en_passant(move):
        captured_square = move.to_square - 8 if board.turn == chess.WHITE else move.to_square + 8
        return board.piece_at(captured_square)
    return board.piece_at(move.to_square)


def _move_wins_material_after_recapture(board, move):
    captured_piece = _captured_piece(board, move)
    moving_piece = board.piece_at(move.from_square)
    if not captured_piece or not moving_piece:
        return False
    captured_value = piece_values[captured_piece.piece_type]
    moving_value = piece_values[moving_piece.piece_type]
    board.push(move)
    try:
        can_recapture_mover = any(
            board.is_capture(reply)
            and reply.to_square == move.to_square
            and board.piece_at(reply.to_square)
            and board.piece_at(reply.to_square).color != board.turn
            for reply in board.legal_moves
        )
    finally:
        board.pop()
    net_gain = captured_value - moving_value if can_recapture_mover else captured_value
    return net_gain >= 100


def _move_rescues_attacked_major_piece(board, move):
    mover = board.turn
    moving_piece = board.piece_at(move.from_square)
    if not moving_piece or moving_piece.piece_type not in {chess.ROOK, chess.QUEEN}:
        return False
    before = board.copy(stack=False)
    before.turn = not mover
    has_legal_capture_before = any(
        reply.to_square == move.from_square and before.is_capture(reply)
        for reply in before.legal_moves
    )
    if not has_legal_capture_before:
        return False
    board.push(move)
    try:
        has_legal_capture_after = any(
            reply.to_square == move.to_square and board.is_capture(reply)
            for reply in board.legal_moves
        )
        return not has_legal_capture_after
    finally:
        board.pop()


def _valuable_targets_attacked_by_moving_piece(board, move):
    mover = board.turn
    board.push(move)
    try:
        targets = []
        for square in board.attacks(move.to_square):
            piece = board.piece_at(square)
            if (
                piece
                and piece.color != mover
                and piece.piece_type in {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}
            ):
                targets.append((square, piece.piece_type))
        return targets
    finally:
        board.pop()


def _move_creates_valuable_piece_fork(board, move):
    moving_piece = board.piece_at(move.from_square)
    if not moving_piece:
        return False
    before_targets = {
        (square, board.piece_at(square).piece_type)
        for square in board.attacks(move.from_square)
        if board.piece_at(square)
        and board.piece_at(square).color != board.turn
        and board.piece_at(square).piece_type
        in {chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN}
    }
    after_targets = set(_valuable_targets_attacked_by_moving_piece(board, move))
    return len(after_targets) >= 2 and len(after_targets) > len(before_targets)


def _move_allows_immediate_mate(board, move):
    board.push(move)
    try:
        for reply in board.legal_moves:
            board.push(reply)
            try:
                if board.is_checkmate():
                    return True
            finally:
                board.pop()
        return False
    finally:
        board.pop()


def _is_teaching_endgame(board):
    white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
    minor_pieces = (
        len(board.pieces(chess.KNIGHT, chess.WHITE))
        + len(board.pieces(chess.BISHOP, chess.WHITE))
        + len(board.pieces(chess.KNIGHT, chess.BLACK))
        + len(board.pieces(chess.BISHOP, chess.BLACK))
    )
    rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
    total_pieces = len(board.piece_map())
    non_pawn_army = white_queens + black_queens + rooks + minor_pieces
    return total_pieces <= 10 or (
        white_queens == 0
        and black_queens == 0
        and non_pawn_army <= 4
        and total_pieces <= 14
    )


def _move_themes(board, move, reason=None):
    themes = set()
    moving_piece = board.piece_at(move.from_square)
    is_endgame = _is_teaching_endgame(board)

    if detect_game_phase(board) == "opening" and not is_endgame:
        themes.add("opening_principle")

    if moving_piece and moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        starting_squares = {
            chess.B1, chess.G1, chess.C1, chess.F1,
            chess.B8, chess.G8, chess.C8, chess.F8,
        }
        if move.from_square in starting_squares:
            themes.add("development")

    tactical_reasons = {
        "checkmate", "check", "wins_material", "promotes_or_supports_promotion",
        "creates_valuable_piece_fork",
    }
    if reason not in tactical_reasons and _move_controls_center(board, move):
        themes.add("center_control")

    if reason in tactical_reasons:
        themes.add("tactics")

    if reason in {"checkmate", "check", "attacks_enemy_king"}:
        themes.add("king_attack")

    if reason in {"castle", "resolves_check", "improves_king_safety"}:
        themes.add("king_safety")

    if is_endgame or move.promotion:
        themes.add("endgame")
    if is_endgame:
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        rooks = len(board.pieces(chess.ROOK, chess.WHITE)) + len(board.pieces(chess.ROOK, chess.BLACK))
        minors = sum(
            len(board.pieces(piece_type, color))
            for piece_type in (chess.KNIGHT, chess.BISHOP)
            for color in (chess.WHITE, chess.BLACK)
        )
        if queens:
            themes.add("queen_endgame")
        elif rooks:
            themes.add("rook_endgame")
        elif minors:
            themes.add("minor_piece_endgame")
        else:
            themes.add("pawn_endgame")

    return sorted(themes)


def _move_reason(board, move, warnings):
    moving_piece = board.piece_at(move.from_square)
    was_in_check = board.is_check()

    board.push(move)
    try:
        if board.is_checkmate():
            return "checkmate"
    finally:
        board.pop()

    if board.is_castling(move):
        return "castle"
    if was_in_check:
        return "resolves_check"
    if move.promotion:
        return "promotes_or_supports_promotion"
    if board.gives_check(move):
        return "check"
    if _move_wins_material_after_recapture(board, move):
        return "wins_material"
    if "hangs_major_piece" not in warnings and _move_rescues_attacked_major_piece(board, move):
        return "avoids_major_piece_loss"
    if _move_creates_valuable_piece_fork(board, move):
        return "creates_valuable_piece_fork"
    if moving_piece and moving_piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        starting_squares = {
            chess.B1, chess.G1, chess.C1, chess.F1,
            chess.B8, chess.G8, chess.C8, chess.F8,
        }
        if move.from_square in starting_squares:
            return "develops_piece"
    if _move_controls_center(board, move):
        return "controls_center"
    if _move_improves_own_king_safety(board, move):
        return "improves_king_safety"
    if _move_increases_enemy_king_pressure(board, move):
        return "attacks_enemy_king"
    return "best_engine_score"


REASON_EVIDENCE = {
    "checkmate": "verified",
    "check": "verified",
    "castle": "verified",
    "resolves_check": "verified",
    "promotes_or_supports_promotion": "verified",
    "wins_material": "supported",
    "avoids_major_piece_loss": "supported",
    "creates_valuable_piece_fork": "verified",
    "improves_king_safety": "supported",
    "attacks_enemy_king": "supported",
    "best_engine_score": "supported",
    "develops_piece": "heuristic",
    "controls_center": "heuristic",
}


def _reason_evidence(reason):
    return REASON_EVIDENCE.get(reason, "heuristic")


def _theme_evidence(theme, reason):
    if theme in {"queen_endgame", "rook_endgame", "minor_piece_endgame", "pawn_endgame"}:
        return "verified"
    if theme in {"tactics", "king_attack"} and reason in {
        "checkmate", "check", "promotes_or_supports_promotion", "creates_valuable_piece_fork"
    }:
        return "verified"
    if theme in {"king_safety", "only_move"}:
        return "supported"
    return "heuristic"


def _candidate_moves(board, best_move, candidate_count):
    moves = []
    if best_move and best_move in board.legal_moves:
        moves.append(best_move)
    for move in order_moves(board):
        if move not in moves:
            moves.append(move)
        if len(moves) >= candidate_count:
            break
    return moves


def _candidate_score(board, depth):
    if board.is_game_over():
        return evaluate_board(board, 1)
    score, _move = minimax(
        board,
        max(1, depth),
        -math.inf,
        math.inf,
        board.turn == chess.WHITE,
        1,
    )
    return score


def _teaching_score_type(score):
    return "mate" if abs(score) >= MATE_THRESHOLD else "centipawn"


def get_teaching_analysis(
    board,
    base_analysis,
    candidate_count=5,
    depth=None,
    time_limit=None,
):
    """Return structured candidate comparisons and teaching evidence."""
    original_fen = board.fen()
    mover = board.turn
    best_move = base_analysis.get("best_move")
    base_depth = depth if depth is not None else max(1, int(base_analysis.get("depth") or 1) - 1)
    started_at = time.monotonic()
    deadline = started_at + time_limit if time_limit else None
    begin_search_generation(deadline=deadline)

    planned_moves = _candidate_moves(board, best_move, candidate_count)
    candidates = []
    analysis_complete = True
    for move in planned_moves:
        if deadline is not None and time.monotonic() >= deadline:
            analysis_complete = False
            break

        san = board.san(move)
        warnings = []
        if major_piece_loss_after_move(board, move):
            warnings.append("hangs_major_piece")
        if _move_allows_immediate_mate(board, move):
            warnings.append("allows_mate_threat")

        search_board = board.copy()
        search_board.push(move)
        try:
            score = _candidate_score(search_board, base_depth)
        except SearchTimeout:
            analysis_complete = False
            break

        reason = _move_reason(board, move, warnings)
        themes = _move_themes(board, move, reason)
        theme_evidence = {theme: _theme_evidence(theme, reason) for theme in themes}
        pv = [move.uci(), *get_pv_line(search_board, base_depth)]
        perspective_score = score if mover == chess.WHITE else -score
        candidates.append({
            "move_obj": move,
            "move": move.uci(),
            "san": san,
            "score_cp": int(score),
            "score_type": _teaching_score_type(score),
            "score_status": "complete",
            "display": format_evaluation(score),
            "perspective_score": perspective_score,
            "base_engine_choice": bool(best_move and move == best_move),
            "pv": pv,
            "warnings": warnings,
            "themes": themes,
            "theme_evidence": theme_evidence,
            "reason": reason,
            "reason_evidence": _reason_evidence(reason),
        })

    candidates.sort(key=lambda item: item["perspective_score"], reverse=True)
    if not candidates and best_move and best_move in board.legal_moves:
        score = int(base_analysis.get("score") or 0)
        analysis_complete = False
        candidates.append({
            "move_obj": best_move,
            "move": best_move.uci(),
            "san": board.san(best_move),
            "score_cp": score,
            "score_type": _teaching_score_type(score),
            "score_status": "base_only",
            "display": format_evaluation(score),
            "perspective_score": score if mover == chess.WHITE else -score,
            "base_engine_choice": True,
            "pv": [best_move.uci()],
            "warnings": [],
            "themes": _move_themes(board, best_move),
            "reason": _move_reason(board, best_move, []),
        })
        candidates[0]["reason_evidence"] = _reason_evidence(candidates[0]["reason"])
        candidates[0]["theme_evidence"] = {
            theme: _theme_evidence(theme, candidates[0]["reason"])
            for theme in candidates[0]["themes"]
        }

    best_perspective = candidates[0]["perspective_score"] if candidates else 0
    best_score_type = candidates[0]["score_type"] if candidates else "centipawn"
    for index, item in enumerate(candidates, start=1):
        item["rank"] = index
        comparison_loss = int(max(0, best_perspective - item["perspective_score"]))
        item["comparison_loss"] = comparison_loss
        comparable_cp = best_score_type == "centipawn" and item["score_type"] == "centipawn"
        item["loss_cp"] = comparison_loss if comparable_cp else None
        item["near_equal"] = comparable_cp and comparison_loss <= 25
        if comparison_loss >= 150 and "large_eval_drop" not in item["warnings"]:
            item["warnings"].append("large_eval_drop")

    if candidates and candidates[0]["reason"] == "checkmate":
        for item in candidates[1:]:
            if item["reason"] != "checkmate" and "misses_mate" not in item["warnings"]:
                item["warnings"].append("misses_mate")

    all_candidate_themes = set()
    mistake_warnings = set()
    for item in candidates:
        all_candidate_themes.update(item["themes"])
        mistake_warnings.update(item["warnings"])
    position_themes = set(candidates[0]["themes"] if candidates else [])

    comparison_complete = analysis_complete and len(candidates) == len(planned_moves)
    if not comparison_complete:
        criticality = "partial"
    elif len(candidates) >= 2 and candidates[1]["comparison_loss"] >= ONLY_MOVE_LOSS_CP:
        criticality = "only_move"
        position_themes.add("only_move")
    elif mistake_warnings or (len(candidates) >= 2 and candidates[-1]["comparison_loss"] >= 150):
        criticality = "sharp"
    else:
        criticality = "normal"

    best_reason = candidates[0]["reason"] if candidates else "best_engine_score"
    position_theme_evidence = dict(
        candidates[0].get("theme_evidence", {}) if candidates else {}
    )
    if "only_move" in position_themes:
        position_theme_evidence["only_move"] = "supported"
    public_candidates = []
    for item in candidates:
        public_item = dict(item)
        public_item.pop("move_obj", None)
        public_item.pop("perspective_score", None)
        public_item.pop("comparison_loss", None)
        public_candidates.append(public_item)

    if board.fen() != original_fen:
        raise RuntimeError("teaching analysis mutated the board")

    return {
        "candidates": public_candidates,
        "criticality": criticality,
        "position_themes": sorted(position_themes),
        "candidate_themes": sorted(all_candidate_themes),
        "best_move_reason": best_reason,
        "best_move_evidence": _reason_evidence(best_reason),
        "position_theme_evidence": position_theme_evidence,
        "mistake_warnings": sorted(mistake_warnings),
        "analysis_complete": comparison_complete,
        "evaluated_candidate_count": sum(
            item.get("score_status") == "complete" for item in candidates
        ),
        "returned_candidate_count": len(candidates),
        "requested_candidate_count": len(planned_moves),
    }


def get_analysis(
    board,
    depth=3,
    time_limit=None,
    use_book=True,
    adaptive_depth=True,
    style="balanced",
    difficulty="advanced",
):
    """
    深度分析棋盤局面
    
    Args:
        board: 棋盤狀態
        depth: 搜尋深度
        time_limit: 時間限制（秒），None 則使用固定深度
        use_book: 是否使用開局庫
        adaptive_depth: 是否在殘局自動加深
        style: balanced 或 trickster
        difficulty: newbie、beginner、intermediate 或 advanced
    
    Returns:
        dict: {
            'best_move': 最佳走法,
            'score': 分數 (centipawns),
            'eval_display': 格式化分數,
            'winning_chance': 勝率百分比,
            'pv': PV Line,
            'depth': 實際搜尋深度,
            'nodes': 搜尋節點數
        }
    """
    # 🔥 優先使用開局庫（開局階段）
    if use_book and len(board.move_stack) < 10:  # 前 10 手使用開局庫
        try:
            with chess.polyglot.open_reader(BOOK_PATH) as reader:
                entry = choose_book_entry(reader, board)
                if entry:
                    book_line = build_book_line(reader, board, entry.move)
                    # 從開局庫找到走法，直接返回
                    return {
                        'best_move': entry.move,
                        'score': 15,  # 開局庫走法給予小優勢評分
                        'eval_display': '+0.15',
                        'winning_chance': 52,
                        'pv': [entry.move.uci()],
                        'book_line': book_line,
                        'depth': 0,  # 來自開局庫
                        'nodes': 0,
                        'tt_hits': 0,
                        'tt_cutoffs': 0,
                        'pvs_researches': 0,
                        'candidate_cache_hits': 0,
                        'candidate_bound_skips': 0,
                        'tt_size': len(transposition_table),
                        'from_book': True,
                        'difficulty_loss': 0,
                    }
        except Exception:
            # 開局庫缺局面或檔案不可用時，直接回到引擎計算。
            pass
    
    started_at = time.monotonic()
    overall_deadline = started_at + time_limit if time_limit else None
    needs_move_overlay = style == "trickster" or difficulty not in {"advanced", "challenge"}
    if overall_deadline and needs_move_overlay:
        search_deadline = started_at + time_limit * 0.65
    else:
        search_deadline = overall_deadline
    begin_search_generation(deadline=search_deadline)
    is_maximizing = board.turn == chess.WHITE
    repetition_counts = build_repetition_counts(board)
    
    # 根據子力數量動態調整基礎深度
    if adaptive_depth:
        total_pieces = len(board.piece_map())
        if total_pieces < 6:
            depth = max(depth, 8)  # 殘局加深
        elif total_pieces < 12:
            depth = max(depth, 6)
    
    best_move = None
    best_score = -math.inf
    nodes_searched = 0
    final_depth = depth
    timed_out = False
    
    # 迭代加深搜尋 (Iterative Deepening)
    if time_limit:
        for current_depth in range(1, depth + 1):
            if time.monotonic() >= search_deadline:
                break
            try:
                score, move = minimax(
                    board,
                    current_depth,
                    -math.inf,
                    math.inf,
                    is_maximizing,
                    repetition_counts=repetition_counts,
                )
            except SearchTimeout:
                timed_out = True
                break
            best_move = move
            best_score = score
            final_depth = current_depth
            nodes_searched = search_stats["nodes"]
    else:
        # 固定深度搜尋
        best_score, best_move = minimax(
            board,
            depth,
            -math.inf,
            math.inf,
            is_maximizing,
            repetition_counts=repetition_counts,
        )
        nodes_searched = search_stats["nodes"]

    if best_move is None:
        safe_moves = [move for move in order_moves(board) if not major_piece_loss_after_move(board, move)]
        fallback_moves = safe_moves or list(board.legal_moves)
        best_move = fallback_moves[0] if fallback_moves else None
        if best_move:
            board.push(best_move)
            try:
                best_score = evaluate_board(board, 1)
            finally:
                board.pop()
        final_depth = 0
        nodes_searched = search_stats["nodes"]

    style_bonus = 0
    difficulty_loss = 0
    if best_move and needs_move_overlay:
        search_runtime.deadline = overall_deadline
        try:
            best_move, best_score, style_bonus, difficulty_loss = select_difficulty_move(
                board,
                final_depth,
                best_move,
                best_score,
                difficulty,
                style,
            )
        except SearchTimeout:
            timed_out = True
            pass
    
    # 提取 PV Line
    pv_line = get_pv_line(board, final_depth)
    
    return {
        'best_move': best_move,
        'score': best_score,
        'eval_display': format_evaluation(best_score),
        'winning_chance': calculate_winning_chance(best_score),
        'pv': pv_line,
        'book_line': [],
        'depth': final_depth,
        'nodes': nodes_searched,
        'tt_hits': search_stats["tt_hits"],
        'tt_cutoffs': search_stats["tt_cutoffs"],
        'tt_size': len(transposition_table),
        'pvs_researches': search_stats["pvs_researches"],
        'candidate_cache_hits': search_stats["candidate_cache_hits"],
        'candidate_bound_skips': search_stats["candidate_bound_skips"],
        'from_book': False,
        'style': style,
        'style_bonus': style_bonus,
        'difficulty_loss': difficulty_loss,
        'timed_out': timed_out,
    }

def get_best_move(board, depth=5):
    """簡化版：只返回最佳走法"""
    result = get_analysis(board, depth)
    return result['best_move']

def detect_game_phase(board):
    """檢測當前遊戲階段"""
    total_pieces = len(board.piece_map())
    white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
    starting_squares = (
        chess.B1, chess.G1, chess.C1, chess.F1,
        chess.B8, chess.G8, chess.C8, chess.F8,
    )
    undeveloped_minor_pieces = sum(
        1 for square in starting_squares
        if (piece := board.piece_at(square)) and piece.piece_type in (chess.KNIGHT, chess.BISHOP)
    )
    
    if _is_teaching_endgame(board):
        return "endgame"
    elif (
        board.fullmove_number <= 10
        and total_pieces >= 20
        and (white_queens > 0 or black_queens > 0)
        and undeveloped_minor_pieces >= 1
    ):
        return "opening"
    else:
        return "middle_game"
