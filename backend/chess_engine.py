import chess
import math
import chess.polyglot
import os

# Transposition table (keyed by zobrist hash, depth, side)
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
    # --- Rank 1 (白棋底線) / Rank 8 (黑棋底線) ---
     0, -15,  0,  5,  5,  0, -15,  0,
    # Rank 2
    -5,  0,  0,  0,  0,  0,  0, -5,
    
    # Rank 3-6 (中間區域)
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    
    # Rank 7 (針對對手的 Rank 2)
    -10, -10,  0,  0,  0,  0, -10, -10, 
    
    # Rank 8 (對手底線)
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

def move_score(board, move):
    score = 0
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        if victim and attacker:
            score += piece_values.get(victim.piece_type, 0) * 10 - piece_values.get(attacker.piece_type, 0)
    if move.promotion:
        score += piece_values.get(move.promotion, 0) - piece_values.get(chess.PAWN, 0)
    if board.gives_check(move):
        score += 50
    return score

def order_moves(board):
    return sorted(list(board.legal_moves), key=lambda m: move_score(board, m), reverse=True)

def evaluate_board(board):
    if board.is_checkmate():
        if board.turn: return -99999
        else: return 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    # 1. 判斷遊戲階段
    white_queens = len(board.pieces(chess.QUEEN, chess.WHITE))
    black_queens = len(board.pieces(chess.QUEEN, chess.BLACK))
    minor_pieces = len(board.pieces(chess.KNIGHT, chess.WHITE)) + \
                   len(board.pieces(chess.BISHOP, chess.WHITE)) + \
                   len(board.pieces(chess.KNIGHT, chess.BLACK)) + \
                   len(board.pieces(chess.BISHOP, chess.BLACK))
    
    is_endgame = (white_queens == 0 and black_queens == 0) or (minor_pieces <= 2)

    score = 0
    
    # 2. 計算材質與位置分 (Material & PST)
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
                if is_endgame: pst_value = king_table_endgame[square]
                else: pst_value = king_table_opening[square]
            
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
                    if is_endgame: pst_value_black = king_table_endgame[mirror_square]
                    else: pst_value_black = king_table_opening[mirror_square]

                score -= (value + pst_value_black)

    # 3. 開局與易位邏輯
    if not is_endgame:
        if board.has_castling_rights(chess.WHITE): score += 150
        if board.has_castling_rights(chess.BLACK): score -= 150
        if board.king(chess.WHITE) in [chess.G1, chess.C1]: score += 80
        if board.king(chess.BLACK) in [chess.G8, chess.C8]: score -= 80

        # 懲罰擋路
        if board.king(chess.WHITE) == chess.E1:
            for sq in [chess.F1, chess.D1, chess.G1, chess.B1]:
                p = board.piece_at(sq)
                if p and p.piece_type == chess.ROOK and p.color == chess.WHITE:
                    score -= 50
        
        if board.king(chess.BLACK) == chess.E8:
            for sq in [chess.F8, chess.D8, chess.G8, chess.B8]:
                p = board.piece_at(sq)
                if p and p.piece_type == chess.ROOK and p.color == chess.BLACK:
                    score += 50

    # 4. Mop-up Evaluation (殘局掃蕩)
    if is_endgame:
        winning_side = None
        if score > 200: winning_side = chess.WHITE
        elif score < -200: winning_side = chess.BLACK
        
        if winning_side is not None:
            losing_king_sq = board.king(not winning_side)
            winning_king_sq = board.king(winning_side)
            
            if losing_king_sq is not None and winning_king_sq is not None:
                losing_rank, losing_file = chess.square_rank(losing_king_sq), chess.square_file(losing_king_sq)
                dist_to_center = max(3 - losing_rank, losing_rank - 4) + max(3 - losing_file, losing_file - 4)
                winning_rank, winning_file = chess.square_rank(winning_king_sq), chess.square_file(winning_king_sq)
                dist_between_kings = abs(losing_rank - winning_rank) + abs(losing_file - winning_file)
                
                mop_up_score = (4 * dist_to_center) + (14 - dist_between_kings)
                
                if winning_side == chess.WHITE: score += mop_up_score * 10 
                else: score -= mop_up_score * 10

    # 5. 🔥 防止鬼打牆 (Repetition Logic)
    # 如果局面重複出現兩次 (is_repetition(2))，視為和棋 (0分)
    # 這樣贏的一方會避免重複，輸的一方會尋求重複 (逼和)
    if board.is_repetition(2):
        return 0

    return score

def quiescence_search(board, alpha, beta):
    # 1. Stand-pat (不吃子，直接評估當前局面)
    # ⚠️ 修正：evaluate_board 回傳的是絕對分數 (白正黑負)
    # 但 Quiescence Search 是 Negamax 邏輯，需要「當前玩家視角」的分數
    stand_pat = evaluate_board(board)
    if board.turn == chess.BLACK:
        stand_pat = -stand_pat
    
    # 2. Fail-hard Beta Cutoff (如果當前局面已經比 Beta 好，對手不會讓你走到這)
    if stand_pat >= beta:
        return beta
    
    # 3. Update Alpha (如果當前局面比 Alpha 好，更新 Alpha)
    if stand_pat > alpha:
        alpha = stand_pat
        
    # 4. 只生成吃子步 (Captures Only)
    # ⚠️ 修正：原本用 occupied_co 會漏掉「過路兵 (En Passant)」，因為目標格是空的
    # 改回用 legal_moves + is_capture 雖然慢一點點，但最安全
    for move in board.legal_moves:
        if not board.is_capture(move):
            continue
            
        board.push(move)
        score = -quiescence_search(board, -beta, -alpha)
        board.pop()
        
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
            
    return alpha

def minimax(board, depth, alpha, beta, maximizing_player):
    key = chess.polyglot.zobrist_hash(board)
    tt_val = transposition_table.get((key, depth, maximizing_player))
    if tt_val is not None:
        return tt_val
        
    if depth == 0 or board.is_game_over():
        if board.is_game_over():
            val = evaluate_board(board)
        else:
            # 🔥 改用靜止搜索 (Quiescence Search) 取代直接評估
            # 這能防止水平線效應 (Horizon Effect)
            if maximizing_player:
                val = quiescence_search(board, alpha, beta)
            else:
                # Minimizing Player (黑方)
                # Quiescence Search 是 Negamax，回傳「對當前玩家(黑)」的分數
                # 我們需要將其轉回「對白方」的絕對分數，所以加負號
                # 同時 Alpha/Beta 也要反轉視角傳入
                val = -quiescence_search(board, -beta, -alpha)

        transposition_table[(key, depth, maximizing_player)] = val
        return val

    if maximizing_player:
        max_eval = -math.inf
        for move in order_moves(board):
            board.push(move)
            eval_score = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            max_eval = max(max_eval, eval_score)
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break 
        transposition_table[(key, depth, maximizing_player)] = max_eval
        return max_eval
    else:
        min_eval = math.inf
        for move in order_moves(board):
            board.push(move)
            eval_score = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            min_eval = min(min_eval, eval_score)
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        transposition_table[(key, depth, maximizing_player)] = min_eval
        return min_eval

def get_best_move(board, depth):
    # 0. 嘗試查閱開局庫 (Opening Book)
    # 這能讓 AI 在開局階段秒出，而且變化多端 (不再只走阿廖興)
    book_path = "books/gm2001.bin"
    if os.path.exists(book_path):
        try:
            with chess.polyglot.open_reader(book_path) as reader:
                # 隨機選擇權重最高的幾個走法之一
                entry = reader.weighted_choice(board)
                if entry:
                    print(f"📖 Book Move: {entry.move}")
                    return entry.move
        except Exception as e:
            print(f"Book Error: {e}")

    # 5. 動態深度 (Dynamic Depth)
    # 如果棋子很少 (殘局)，我們可以算深一點！
    total_pieces = len(board.piece_map())
    if total_pieces < 6:
        depth = 6  # 超級殘局算 6 步 (可以算到將死)
    elif total_pieces < 10:
        depth = 5  # 殘局算 5 步
    
    best_move = None
    max_eval = -math.inf
    alpha = -math.inf
    beta = math.inf
    is_maximizing = board.turn == chess.WHITE
    if not is_maximizing:
        max_eval = math.inf

    # 6. 隨機性 (Randomness) - 如果沒有開局庫，這能增加一點變化
    # 我們收集前 3 名的好棋，然後隨機挑一個 (避免每次都走一樣)
    # 這裡先保留原本的邏輯，因為有開局庫通常就夠了
    
    for move in order_moves(board):
        board.push(move)
        eval_score = minimax(board, depth - 1, alpha, beta, not is_maximizing)
        board.pop()
        
        if is_maximizing:
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
        else:
            if eval_score < max_eval:
                max_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
    return best_move
