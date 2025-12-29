import chess
import math
import chess.polyglot
import os

# Transposition table
transposition_table = {}

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
            
        return score

    return sorted(moves, key=score_move, reverse=True)

def evaluate_board(board, depth=0):
    if board.is_checkmate():
        score = 20000 + depth
        if board.turn: return -score
        else: return score
        
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
            pst_value = 0
            
            if piece.piece_type == chess.PAWN: pst_value = pawntable[square]
            elif piece.piece_type == chess.KNIGHT: pst_value = knightstable[square]
            elif piece.piece_type == chess.BISHOP: pst_value = bishopstable[square]
            elif piece.piece_type == chess.ROOK: pst_value = rookstable[square]
            elif piece.piece_type == chess.QUEEN: pst_value = queenstable[square]
            elif piece.piece_type == chess.KING:
                pst_value = king_table_endgame[square] if is_endgame else king_table_opening[square]
            
            if piece.color == chess.WHITE:
                score += value + pst_value
            else:
                mirror_square = chess.square_mirror(square)
                pst_value_black = 0
                if piece.piece_type == chess.PAWN: pst_value_black = pawntable[mirror_square]
                elif piece.piece_type == chess.KNIGHT: pst_value_black = knightstable[mirror_square]
                elif piece.piece_type == chess.BISHOP: pst_value_black = bishopstable[mirror_square]
                elif piece.piece_type == chess.ROOK: pst_value_black = rookstable[mirror_square]
                elif piece.piece_type == chess.QUEEN: pst_value_black = queenstable[mirror_square]
                elif piece.piece_type == chess.KING:
                    pst_value_black = king_table_endgame[mirror_square] if is_endgame else king_table_opening[mirror_square]
                score -= (value + pst_value_black)

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

# 🔥 修正：這裡一定要加 q_depth=0，不然會 crash
def quiescence_search(board, alpha, beta, q_depth=0):
    if q_depth > 10:
        turn_multiplier = 1 if board.turn == chess.WHITE else -1
        return evaluate_board(board) * turn_multiplier

    stand_pat = evaluate_board(board)
    if board.turn == chess.BLACK:
        stand_pat = -stand_pat
    
    if stand_pat >= beta: return beta
    if stand_pat > alpha: alpha = stand_pat
        
    for move in board.legal_moves:
        if not board.is_capture(move): continue
        board.push(move)
        score = -quiescence_search(board, -beta, -alpha, q_depth + 1)
        board.pop()
        if score >= beta: return beta
        if score > alpha: alpha = score
            
    return alpha

def minimax(board, depth, alpha, beta, maximizing_player):
    if board.is_repetition(2):
        if depth == 0: 
             return evaluate_board(board), None

    key = chess.polyglot.zobrist_hash(board)
    tt_entry = transposition_table.get((key, depth, maximizing_player))
    tt_move = None
    
    if tt_entry:
        return tt_entry[0], tt_entry[1]

    if depth == 0 or board.is_game_over():
        if board.is_game_over():
            val = evaluate_board(board, depth)
        else:
            qs_val = quiescence_search(board, alpha, beta)
            val = qs_val if maximizing_player else -qs_val
        
        transposition_table[(key, depth, maximizing_player)] = (val, None)
        return val, None

    # 簡單嘗試獲取同一局面但不同深度的 move 來排序 (加速用)
    # 這裡因為 Key 包含 depth，所以其實還是拿不到，但邏輯保留沒問題
    moves = order_moves(board, tt_move) 

    best_move = None
    if maximizing_player:
        max_eval = -math.inf
        for move in moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha: break 
        transposition_table[(key, depth, maximizing_player)] = (max_eval, best_move)
        return max_eval, best_move
    else:
        min_eval = math.inf
        for move in moves:
            board.push(move)
            eval_score, _ = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha: break
        transposition_table[(key, depth, maximizing_player)] = (min_eval, best_move)
        return min_eval, best_move

# 🔥 補上：你漏掉了這個函式
def get_pv_line(board, depth):
    """從置換表 (TT) 重建預測變例 (Principal Variation)"""
    pv_line = []
    curr_board = board.copy()
    is_maximizing = curr_board.turn == chess.WHITE
    
    for d in range(depth, 0, -1):
        key = chess.polyglot.zobrist_hash(curr_board)
        tt_entry = transposition_table.get((key, d, is_maximizing))
        
        if tt_entry and tt_entry[1]:
            move = tt_entry[1]
            pv_line.append(move.uci())
            curr_board.push(move)
            is_maximizing = not is_maximizing
        else:
            break
    return pv_line

def get_analysis(board, depth=3):
    transposition_table.clear()
    is_maximizing = board.turn == chess.WHITE
    score, best_move = minimax(board, depth, -math.inf, math.inf, is_maximizing)
    pv_line = get_pv_line(board, depth)
    return best_move, score, pv_line

def get_best_move(board, depth):
    book_path = "books/gm2001.bin"
    if os.path.exists(book_path):
        try:
            with chess.polyglot.open_reader(book_path) as reader:
                entry = reader.weighted_choice(board)
                if entry:
                    print(f"📖 Book Move: {entry.move}")
                    return entry.move
        except Exception:
            pass

    total_pieces = len(board.piece_map())
    if total_pieces < 6: depth = 8
    elif total_pieces < 12: depth = 6
    elif total_pieces < 16: depth = 5
    
    best_move, score, pv = get_analysis(board, depth)
    return best_move