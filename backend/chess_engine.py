import chess
import math
import chess.polyglot
import os
import time

# Transposition table
transposition_table = {}
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_PATH = os.path.join(ENGINE_DIR, "books", "gm2001.bin")

# --- 評估體系常數 ---
MATE_SCORE = 20000
MATE_THRESHOLD = 15000

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

# --- 1. 定義棋子價值 ---
piece_values = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# --- 2. 位置權重表 (PST) ---
pawntable = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5,  5, 10, 25, 25, 10,  5,  5,
    0,  0,  0, 20, 20,  0,  0,  0,
    5, -5,-10,  0,  0,-10, -5,  5,
    5, 10, 10,-20,-20, 10, 10,  5,
    0,  0,  0,  0,  0,  0,  0,  0
]
knightstable = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]
bishopstable = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]
rookstable = [
     0, -15,  0,  5,  5,  0, -15,  0,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -10, -10,  0,  0,  0,  0, -10, -10, 
     0,  0,  0,  10, 10,  5,  0,  0
]
queenstable = [
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
]
king_table_opening = [
    20, 30, 10,  0,  0, 10, 30, 20,
    20, 20,  0,  0,  0,  0, 20, 20,
    -10,-20,-20,-20,-20,-20,-20,-10,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30
]
king_table_endgame = [
    -50,-30,-30,-30,-30,-30,-30,-50,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -50,-40,-30,-20,-20,-30,-40,-50
]

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

def get_piece_square_value(piece_type, square, color, is_endgame):
    if color == chess.WHITE:
        square = chess.square_mirror(square)

    if piece_type == chess.PAWN: return pawntable[square]
    elif piece_type == chess.KNIGHT: return knightstable[square]
    elif piece_type == chess.BISHOP: return bishopstable[square]
    elif piece_type == chess.ROOK: return rookstable[square]
    elif piece_type == chess.QUEEN: return queenstable[square]
    elif piece_type == chess.KING:
        return king_table_endgame[square] if is_endgame else king_table_opening[square]
    return 0

def evaluate_board(board, ply_from_root=0):
    if board.is_checkmate():
        score = MATE_SCORE - ply_from_root
        return -score if board.turn == chess.WHITE else score
        
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
    minor_pieces = len(board.pieces(chess.KNIGHT, chess.WHITE)) + \
                   len(board.pieces(chess.BISHOP, chess.WHITE)) + \
                   len(board.pieces(chess.KNIGHT, chess.BLACK)) + \
                   len(board.pieces(chess.BISHOP, chess.BLACK))
    
    is_endgame = (white_queens == 0 and black_queens == 0) or (minor_pieces <= 2)
    score = 0
    
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            value = piece_values[piece.piece_type]
            pst_value = get_piece_square_value(piece.piece_type, square, piece.color, is_endgame)
            
            if piece.color == chess.WHITE:
                score += value + pst_value
            else:
                score -= (value + pst_value)

    if not is_endgame:
        if board.has_castling_rights(chess.WHITE): score += 20
        if board.has_castling_rights(chess.BLACK): score -= 20

    if is_endgame:
        winning_side = None
        if score > 200: winning_side = chess.WHITE
        elif score < -200: winning_side = chess.BLACK
        
        if winning_side is not None:
            losing_king = board.king(not winning_side)
            winning_king = board.king(winning_side)
            if losing_king and winning_king:
                lr, lf = chess.square_rank(losing_king), chess.square_file(losing_king)
                dist_center = max(3 - lr, lr - 4) + max(3 - lf, lf - 4)
                wr, wf = chess.square_rank(winning_king), chess.square_file(winning_king)
                dist_kings = abs(lr - wr) + abs(lf - wf)
                mop_score = (4 * dist_center) + (14 - dist_kings)
                if winning_side == chess.WHITE: score += mop_score * 10
                else: score -= mop_score * 10

    # 🔥 Contempt Factor
    if board.is_repetition(2):
        if score > 500: return -1000
        if score < -500: return 1000
        return 0

    return score

def quiescence_search(board, alpha, beta, q_depth=0, ply_from_root=0):
    if board.is_game_over():
        return evaluate_board(board, ply_from_root)

    if q_depth > 10:
        return evaluate_board(board, ply_from_root)

    stand_pat = evaluate_board(board, ply_from_root)
    capture_moves = [move for move in order_moves(board) if board.is_capture(move)]

    if board.turn == chess.WHITE:
        if stand_pat >= beta: return beta
        if stand_pat > alpha: alpha = stand_pat

        for move in capture_moves:
            board.push(move)
            score = quiescence_search(board, alpha, beta, q_depth + 1, ply_from_root + 1)
            board.pop()
            if score >= beta: return beta
            if score > alpha: alpha = score
        return alpha

    if stand_pat <= alpha: return alpha
    if stand_pat < beta: beta = stand_pat

    for move in capture_moves:
        board.push(move)
        score = quiescence_search(board, alpha, beta, q_depth + 1, ply_from_root + 1)
        board.pop()
        if score <= alpha: return alpha
        if score < beta: beta = score
    return beta

def minimax(board, depth, alpha, beta, maximizing_player, ply_from_root=0):
    if board.is_repetition(2):
        if depth == 0: 
             return evaluate_board(board, ply_from_root), None

    key = chess.polyglot.zobrist_hash(board)
    tt_entry = transposition_table.get((key, depth, maximizing_player, ply_from_root))
    tt_move = None
    
    if tt_entry:
        return tt_entry[0], tt_entry[1]

    if depth == 0 or board.is_game_over():
        if board.is_game_over():
            val = evaluate_board(board, ply_from_root)
        else:
            val = quiescence_search(board, alpha, beta, ply_from_root=ply_from_root)
        
        transposition_table[(key, depth, maximizing_player, ply_from_root)] = (val, None)
        return val, None

    # 簡單嘗試獲取同一局面但不同深度的 move 來排序 (加速用)
    # 這裡因為 Key 包含 depth，所以其實還是拿不到，但邏輯保留沒問題
    moves = order_moves(board, tt_move) 

    best_move = None
    if maximizing_player:
        max_eval = -math.inf
        for move in moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, False, ply_from_root + 1)
            board.pop()
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha: break 
        transposition_table[(key, depth, maximizing_player, ply_from_root)] = (max_eval, best_move)
        return max_eval, best_move
    else:
        min_eval = math.inf
        for move in moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, True, ply_from_root + 1)
            board.pop()
            
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha: break
        transposition_table[(key, depth, maximizing_player, ply_from_root)] = (min_eval, best_move)
        return min_eval, best_move

# 🔥 補上：你漏掉了這個函式
def get_pv_line(board, depth):
    """從置換表 (TT) 重建預測變例 (Principal Variation)"""
    pv_line = []
    curr_board = board.copy()
    is_maximizing = curr_board.turn == chess.WHITE
    ply_from_root = 0
    
    for d in range(depth, 0, -1):
        key = chess.polyglot.zobrist_hash(curr_board)
        tt_entry = transposition_table.get((key, d, is_maximizing, ply_from_root))
        
        if tt_entry and tt_entry[1]:
            move = tt_entry[1]
            pv_line.append(move.uci())
            curr_board.push(move)
            is_maximizing = not is_maximizing
            ply_from_root += 1
        else:
            break
    return pv_line

def get_analysis(board, depth=3, time_limit=None):
    """
    深度分析棋盤局面
    
    Args:
        board: 棋盤狀態
        depth: 搜尋深度
        time_limit: 時間限制（秒），None 則使用固定深度
    
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
    if len(board.move_stack) < 10:  # 前 10 手使用開局庫
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
                        'from_book': True
                    }
        except Exception:
            # 開局庫缺局面或檔案不可用時，直接回到引擎計算。
            pass
    
    transposition_table.clear()
    is_maximizing = board.turn == chess.WHITE
    
    # 根據子力數量動態調整基礎深度
    total_pieces = len(board.piece_map())
    if total_pieces < 6:
        depth = max(depth, 8)  # 殘局加深
    elif total_pieces < 12:
        depth = max(depth, 6)
    
    best_move = None
    best_score = -math.inf
    nodes_searched = 0
    final_depth = depth
    
    # 迭代加深搜尋 (Iterative Deepening)
    if time_limit:
        start_time = time.time()
        for current_depth in range(1, depth + 1):
            if time.time() - start_time > time_limit:
                break
            score, move = minimax(board, current_depth, -math.inf, math.inf, is_maximizing)
            best_move = move
            best_score = score
            final_depth = current_depth
            nodes_searched = len(transposition_table)
    else:
        # 固定深度搜尋
        best_score, best_move = minimax(board, depth, -math.inf, math.inf, is_maximizing)
        nodes_searched = len(transposition_table)
    
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
        'from_book': False
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
    
    if total_pieces <= 6:
        return "endgame"
    elif (
        board.fullmove_number <= 3
        and total_pieces >= 24
        and (white_queens > 0 or black_queens > 0)
        and undeveloped_minor_pieces >= 3
    ):
        return "opening"
    else:
        return "middle_game"
