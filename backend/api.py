from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import chess
import chess.pgn
import io
import math
import os

# 匯入你的核心引擎
import chess_engine  # Import the new engine module
# 匯入資料庫模組
from database import SessionLocal, Game

# 嘗試匯入 RAG 引擎
# 這樣就算 rag.py 有錯或沒 key，伺服器也能啟動其他功能
try:
    from rag import rag_engine
except Exception as e:
    print(f"⚠️ Warning: RAG engine failed to start: {e}")
    rag_engine = None

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependency: 取得資料庫連線 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 定義資料模型 (Pydantic) ---
class BoardRequest(BaseModel):
    fen: str
    depth: int = 3

class AnalysisRequest(BaseModel):
    pgn: str
    depth: int = 2
    perspective: str = "white"  # "white" or "black"

class GameCreate(BaseModel):
    pgn: str
    result: str
    fen: str
    player_white: str = "Human"
    player_black: str = "AI (Minimax)"

class GameResponse(GameCreate):
    id: int
    date: datetime
    class Config:
        # Pydantic V2 新寫法，解決 UserWarning
        from_attributes = True 

class ExplainRequest(BaseModel):
    fen: str
    history: str = "" # 可選

# --- API 端點 ---

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chess AI is running!"}

# 1. 單步分析 (給遊戲進行中使用)
@app.post("/analyze")
def analyze_game(request: BoardRequest):
    try:
        board = chess.Board(request.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string")

    if board.is_game_over():
        return {"game_over": True, "result": board.result()}

    best_move = chess_engine.get_best_move(board, depth=request.depth)

    return {
        "best_move": best_move.uci() if best_move else None,
        "evaluation": "N/A"
    }

# 2. 🔥 完整賽局分析 (你的新功能，適合賽後復盤)
@app.post("/analyze_full")
def analyze_full_game(request: AnalysisRequest):
    pgn_io = io.StringIO(request.pgn)
    game = chess.pgn.read_game(pgn_io)
    if not game:
        raise HTTPException(status_code=400, detail="Invalid PGN")

    board = game.board()
    evaluations = []
    
    # 設定視角
    persp = (getattr(request, "perspective", "white") or "white").lower()
    if persp not in ("white","black"):
        persp = "white"
    
    # 定義分數轉換函數 (如果是黑方視角，分數要反轉顯示)
    def orient(v):
        return v if persp == "white" else -v

    # 初始局面評分
    start_eval, _ = chess_engine.minimax(board, max(1, request.depth), -math.inf, math.inf, board.turn == chess.WHITE)
    evaluations.append({
        "move_number": 0,
        "fen": board.fen(),
        "score": start_eval,
        "score_for": orient(start_eval),
        "perspective": persp
    })

    move_count = 1
    for move in game.mainline_moves():
        side = "white" if board.turn == chess.WHITE else "black"
        
        # 1. 計算這一步之前的「最佳建議」
        # 注意：這裡會呼叫 Minimax，如果整盤棋很長，這一步驟會花很多時間
        best_move = chess_engine.get_best_move(board, depth=request.depth)
        
        if best_move:
            board.push(best_move)
            # 算出最佳步的分數
            best_eval, _ = chess_engine.minimax(board, max(1, request.depth - 1), -math.inf, math.inf, board.turn == chess.WHITE)
            board.pop()
        else:
            best_eval = chess_engine.evaluate_board(board)

        # 2. 執行「實際走的那一步」
        board.push(move)
        move_eval, _ = chess_engine.minimax(board, max(1, request.depth - 1), -math.inf, math.inf, board.turn == chess.WHITE)
        fen_after = board.fen()

        # 3. 計算損失 (CP Loss)
        # 如果是白方走，loss = 最佳分 - 實際分
        # 如果是黑方走，loss = 實際分 - 最佳分 (因為黑方希望分數越小越好)
        cp_loss = best_eval - move_eval if side == "white" else move_eval - best_eval
        
        # 4. 判斷好壞棋
        if cp_loss < 50: classification = "good"
        elif cp_loss < 150: classification = "inaccuracy"
        elif cp_loss < 300: classification = "mistake"
        else: classification = "blunder"

        mate_threat = abs(move_eval) > 90000 or abs(best_eval) > 90000

        evaluations.append({
            "move_number": move_count,
            "side_to_move": side,
            "move": move.uci(),
            "best_move": best_move.uci() if best_move else None,
            "fen": fen_after,
            "score": move_eval,
            "score_for": orient(move_eval),
            "best_eval_for": orient(best_eval),
            "cp_loss": int(cp_loss),
            "classification": classification,
            "mate_threat": mate_threat,
            "perspective": persp
        })
        move_count += 1

    return evaluations

# 3. 儲存比賽
@app.post("/games", response_model=GameResponse)
def save_game(game: GameCreate, db: Session = Depends(get_db)):
    db_game = Game(
        pgn=game.pgn,
        result=game.result,
        fen=game.fen,
        player_white=game.player_white,
        player_black=game.player_black
    )
    db.add(db_game)
    db.commit()
    db.refresh(db_game)
    return db_game

# 4. 查詢歷史比賽
@app.get("/games", response_model=List[GameResponse])
def read_games(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    games = db.query(Game).order_by(Game.date.desc()).offset(skip).limit(limit).all()
    return games

# 5. RAG AI 解說
class ExplainRequest(BaseModel):
    fen: str
    history: str = ""
    question: Optional[str] = None
    depth: int = 5  # 新增：引擎分析深度

@app.post("/explain")
def explain_position(request: ExplainRequest):
    if not rag_engine:
        return {"advice": "❌ RAG 引擎未啟動，請檢查 API Key 設定"}
    
    # 如果使用者沒問問題，就用預設的 Prompt (總評)
    user_question = request.question or "請評估目前局勢並給出建議"
    
    # 🔥 計算引擎的預測變例 (PV Line)
    pv_line = None
    pv_score = None
    try:
        board = chess.Board(request.fen)
        if not board.is_game_over():
            best_move, score, pv = chess_engine.get_analysis(board, depth=request.depth)
            if pv and len(pv) > 0:
                pv_line = pv
                pv_score = score
                print(f"🎯 PV Line 已計算: {pv} (評分: {score})")
    except Exception as e:
        print(f"⚠️ PV 計算失敗: {e}")
    
    advice = rag_engine.get_advice(
        request.fen, 
        request.history, 
        user_question,
        pv_line=pv_line,
        pv_score=pv_score
    )
    return {"advice": advice}