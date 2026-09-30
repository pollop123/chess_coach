from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
import asyncio
import json
import queue
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Literal
from datetime import datetime
from contextlib import contextmanager
import chess
import chess.engine
import chess.pgn
import io
import logging
import math
import os
import shutil
import threading
import time

# 匯入你的核心引擎
import chess_engine  # Import the new engine module
from coach_conversation import current_conversation, question_mode
from chesscom_import import router as chesscom_router
import review_analysis
import stockfish_coach
# 匯入資料庫模組
from database import SessionLocal, Game

# 嘗試匯入 RAG 引擎
# 這樣就算 rag.py 有錯或沒 key，伺服器也能啟動其他功能
try:
    from rag import get_rag_engine
except Exception as e:
    logging.getLogger(__name__).warning("RAG engine failed to start: %s", e)
    get_rag_engine = None

logger = logging.getLogger(__name__)
app = FastAPI()
app.include_router(chesscom_router)


def _configured_cors_origins():
    configured = os.getenv(
        "CORS_ORIGINS",
        "http://localhost,http://localhost:5173",
    )
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or ["http://localhost", "http://localhost:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

# Keep CPU pressure bounded even though EngineSession now isolates mutable
# search state. The default remains one search per web process; deployments can
# raise it deliberately after measuring their CPU budget.
ENGINE_MAX_CONCURRENT_SEARCHES = max(
    1,
    int(os.getenv("ENGINE_MAX_CONCURRENT_SEARCHES", "1")),
)
engine_search_lock = threading.BoundedSemaphore(ENGINE_MAX_CONCURRENT_SEARCHES)
ENGINE_QUEUE_TIMEOUT_SECONDS = max(
    0.0,
    float(os.getenv("ENGINE_QUEUE_TIMEOUT_SECONDS", "2.0")),
)
MAX_REVIEW_PLIES = 400


@contextmanager
def engine_search_slot():
    acquired = engine_search_lock.acquire(timeout=ENGINE_QUEUE_TIMEOUT_SECONDS)
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail="Analysis capacity is busy; please retry shortly",
            headers={"Retry-After": "2"},
        )
    try:
        yield chess_engine.EngineSession()
    finally:
        engine_search_lock.release()


# --- Dependency: 取得資料庫連線 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 定義資料模型 (Pydantic) ---
class BoardRequest(BaseModel):
    fen: str = Field(min_length=1, max_length=120)
    depth: int = Field(default=3, ge=1, le=8)

class MakeMoveRequest(BaseModel):
    fen: str = Field(min_length=1, max_length=120)
    time_limit: float = Field(default=2.0, ge=0.05, le=5.0)
    difficulty: str = Field(default="intermediate", max_length=32)
    bot_style: str = Field(default="balanced", max_length=32)

class CoachTurn(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(min_length=1, max_length=1500)
    fen: str = Field(min_length=1, max_length=120)
    mode: Literal["knowledge", "position", "comparison", "hint", "overview"] = "position"


class CoachContext(BaseModel):
    conversation: List[CoachTurn] = Field(default_factory=list, max_length=8)
    mode: Literal["auto", "overview", "hint"] = "auto"
    # Which side the asker plays, so "my last move" skips the opponent's reply.
    player_color: Optional[Literal["white", "black"]] = None


class GetAnalysisRequest(CoachContext):
    fen: str = Field(min_length=1, max_length=120)
    history: str = Field(default="", max_length=20_000)
    question: Optional[str] = Field(default=None, max_length=500)
    depth: int = Field(default=5, ge=1, le=8)
    time_limit: float = Field(default=5.0, ge=0.1, le=10.0)

class AnalysisRequest(BaseModel):
    pgn: str = Field(min_length=1, max_length=200_000)
    depth: int = Field(default=2, ge=1, le=6)
    perspective: Literal["white", "black"] = "white"

class GameCreate(BaseModel):
    pgn: str = Field(min_length=1, max_length=200_000)
    result: str = Field(min_length=1, max_length=16)
    fen: str = Field(min_length=1, max_length=120)
    player_white: str = Field(default="Human", max_length=100)
    player_black: str = Field(default="AI (Minimax)", max_length=100)

class GameResponse(BaseModel):
    # Response models intentionally do not inherit write-time constraints.
    # Alembic's legacy baseline preserves the original nullable/unbounded
    # columns, so historical rows must remain readable after adoption.
    id: int
    date: Optional[datetime] = None
    pgn: Optional[str] = None
    result: Optional[str] = None
    fen: Optional[str] = None
    player_white: Optional[str] = None
    player_black: Optional[str] = None

    class Config:
        # Pydantic V2 新寫法，解決 UserWarning
        from_attributes = True 

BOT_DIFFICULTY_PROFILES = {
    "newbie": {
        "label": "新手",
        "depth": 1,
        "time_limit": 0.35,
        "use_book": False,
        "adaptive_depth": False,
    },
    "beginner": {
        "label": "初階",
        "depth": 2,
        "time_limit": 0.7,
        "use_book": False,
        "adaptive_depth": False,
    },
    "intermediate": {
        "label": "中階",
        "depth": 4,
        "time_limit": 1.25,
        "use_book": True,
        "adaptive_depth": False,
    },
    "advanced": {
        "label": "中階加強",
        "depth": 5,
        "time_limit": 1.5,
        "use_book": True,
        "adaptive_depth": True,
    },
    # Backward-compatible alias for older clients.
    "challenge": {
        "label": "中階加強",
        "depth": 5,
        "time_limit": 1.5,
        "use_book": True,
        "adaptive_depth": True,
    },
}

# --- API 端點 ---

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Chess AI is running!"}

# 1. 快速走法端點 (用於遊戲進行)
@app.post("/make_move")
def make_move(request: MakeMoveRequest):
    """
    快速計算最佳走法，2秒內必須回應
    用於遊戲進行時的 AI 走法
    """
    try:
        board = chess.Board(request.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string")

    if board.is_game_over():
        return {
            "game_over": True,
            "result": board.result(),
            "best_move": None,
            "fen": request.fen
        }

    difficulty = request.difficulty if request.difficulty in BOT_DIFFICULTY_PROFILES else "intermediate"
    profile = BOT_DIFFICULTY_PROFILES[difficulty]
    bot_style = request.bot_style if request.bot_style in {"balanced", "trickster"} else "balanced"

    # 使用難度檔位控制搜尋深度、開局庫與殘局自動加深。
    with engine_search_slot() as engine_session:
        analysis = engine_session.analyze(
            board,
            depth=profile["depth"],
            time_limit=min(request.time_limit, profile["time_limit"]),
            use_book=profile["use_book"],
            adaptive_depth=profile["adaptive_depth"],
            style=bot_style,
            difficulty=difficulty,
        )

    if not analysis['best_move']:
        raise HTTPException(status_code=500, detail="Engine failed to find move")

    # 執行走法
    board.push(analysis['best_move'])

    return {
        "best_move": analysis['best_move'].uci(),
        "fen": board.fen(),
        "is_game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
        "difficulty": difficulty,
        "difficulty_label": profile["label"],
        "bot_style": bot_style,
        "depth_reached": analysis["depth"],
        "from_book": analysis.get("from_book", False),
        "style_bonus": analysis.get("style_bonus", 0),
        "difficulty_loss": analysis.get("difficulty_loss", 0),
        "tt_hits": analysis.get("tt_hits", 0),
        "tt_cutoffs": analysis.get("tt_cutoffs", 0),
        "pvs_researches": analysis.get("pvs_researches", 0),
        "lmr_reductions": analysis.get("lmr_reductions", 0),
        "lmr_researches": analysis.get("lmr_researches", 0),
        "candidate_cache_hits": analysis.get("candidate_cache_hits", 0),
        "candidate_bound_skips": analysis.get("candidate_bound_skips", 0),
        "timed_out": analysis.get("timed_out", False),
    }

# 2. 深度分析端點 (用於分析與教練建議)
@app.post("/get_analysis")
def get_analysis_endpoint(request: GetAnalysisRequest):
    """
    深度分析當前局面，包含引擎評估與 AI 教練建議
    允許較長時間運算以提供更準確的分析
    """
    try:
        board = chess.Board(request.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string")

    if board.is_game_over():
        return {
            "game_over": True,
            "result": board.result(),
            "analysis": None,
            "coach_advice": "遊戲已結束"
        }

    # 深度分析
    analysis, teaching_analysis = coach_engine_analysis(
        board, request.depth, request.time_limit, min(1.0, max(0.2, request.time_limit * 0.25)),
    )
    
    game_phase = chess_engine.detect_game_phase(board)

    # 準備 AI 教練建議
    coach_advice = None
    coach_sources = []
    coach_mode = None
    coach_status = "unavailable"
    if get_rag_engine:
        # 安全防禦：清洗用戶輸入
        user_question = request.question or "請評估目前局勢並給出建議"
        
        # 限制問題長度
        if len(user_question) > 200:
            user_question = user_question[:200]
        
        try:
            rag_engine = get_rag_engine()
            reply = rag_engine.get_response(
                request.fen,
                request.history,
                user_question,
                pv_line=analysis['pv'],
                pv_score=analysis['score'],
                analysis_result=analysis,
                teaching_analysis=teaching_analysis,
                conversation=[turn.model_dump() for turn in request.conversation],
                mode="overview" if not request.question and request.mode == "auto" else request.mode,
                player_color=request.player_color,
            )
            coach_advice, coach_sources = reply.advice, reply.sources
            coach_mode, coach_status = reply.mode, reply.status
        except Exception as e:
            logger.warning("RAG analysis failed: %s", e)
            coach_advice = "教練分析暫時無法使用"

    return {
        "evaluation": {
            "score_cp": analysis['score'],
            "display": analysis['eval_display'],
            "winning_chance": analysis['winning_chance'],
            "pv_line": analysis['pv'],
            "depth_reached": analysis['depth'],
            "nodes_searched": analysis['nodes'],
            "tt_hits": analysis.get('tt_hits', 0),
            "tt_cutoffs": analysis.get('tt_cutoffs', 0),
            "tt_size": analysis.get('tt_size', 0),
            "pvs_researches": analysis.get('pvs_researches', 0),
            "lmr_reductions": analysis.get('lmr_reductions', 0),
            "lmr_researches": analysis.get('lmr_researches', 0),
            "candidate_cache_hits": analysis.get('candidate_cache_hits', 0),
            "candidate_bound_skips": analysis.get('candidate_bound_skips', 0),
            "timed_out": analysis.get('timed_out', False),
            "analysis_source": analysis.get('analysis_source', 'builtin'),
        },
        "teaching_analysis": teaching_analysis,
        "game_state": game_phase,
        "coach_advice": coach_advice,
        "coach_sources": coach_sources,
        "coach_mode": coach_mode,
        "coach_status": coach_status,
    }

# 3. 相容性端點 (保留舊版 API)
@app.post("/analyze")
def analyze_game(request: BoardRequest):
    """
    相容性端點，保留舊版 API
    建議使用 /make_move 和 /get_analysis 替代
    """
    try:
        board = chess.Board(request.fen)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FEN string")

    if board.is_game_over():
        return {"game_over": True, "result": board.result()}

    # 使用新的分析引擎，加上時限
    with engine_search_slot() as engine_session:
        analysis = engine_session.analyze(
            board,
            depth=request.depth,
            time_limit=3.0
        )
    game_phase = chess_engine.detect_game_phase(board)

    return {
        "best_move": analysis['best_move'].uci() if analysis['best_move'] else None,
        "evaluation_score": analysis['score'],
        "evaluation_display": analysis['eval_display'],
        "winning_chance": analysis['winning_chance'],
        "depth_reached": analysis['depth'],
        "pv": analysis['pv'],
        "game_state": game_phase,
        "nodes_searched": analysis['nodes']
    }

def _classify_cp_loss(cp_loss):
    if cp_loss < 50:
        return "good"
    if cp_loss < 150:
        return "inaccuracy"
    if cp_loss < 300:
        return "mistake"
    return "blunder"


def _find_stockfish_path():
    configured_path = os.getenv("STOCKFISH_PATH")
    if configured_path and os.path.isfile(configured_path) and os.access(configured_path, os.X_OK):
        return configured_path

    discovered_path = shutil.which("stockfish")
    if discovered_path:
        return discovered_path

    docker_path = "/usr/games/stockfish"
    if os.path.isfile(docker_path) and os.access(docker_path, os.X_OK):
        return docker_path
    return None


def _stockfish_score(info, color=chess.WHITE):
    score = info.get("score")
    if score is None:
        raise ValueError("Stockfish did not return a score")
    centipawns = score.pov(color).score(mate_score=100_000)
    if centipawns is None:
        raise ValueError("Stockfish returned an unusable score")
    return int(centipawns)


def _stockfish_wdl(info, color=chess.WHITE):
    pov_wdl = info.get("wdl")
    if pov_wdl is None:
        return None
    wdl = pov_wdl.pov(color)
    white_win = round(wdl.wins / 10, 1)
    draw = round(wdl.draws / 10, 1)
    black_win = round(wdl.losses / 10, 1)
    return {
        "white_win": white_win,
        "draw": draw,
        "black_win": black_win,
        "expected_score": round(white_win + draw / 2, 1),
    }


def _analyze_full_with_stockfish(game, perspective, stockfish_path, nodes):
    board = game.board()
    evaluations = []
    orient = lambda value: value if perspective == "white" else -value
    limit = chess.engine.Limit(nodes=nodes)
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    try:
        if "UCI_ShowWDL" not in engine.options:
            raise RuntimeError("Installed Stockfish does not support UCI_ShowWDL")
        engine.configure({"UCI_ShowWDL": True})

        start_info = engine.analyse(board, limit)
        start_eval = _stockfish_score(start_info)
        evaluations.append({
            "move_number": 0,
            "fen": board.fen(),
            "score": start_eval,
            "score_for": orient(start_eval),
            "perspective": perspective,
            "wdl": _stockfish_wdl(start_info),
            "analysis_source": "stockfish",
        })

        for move_count, move in enumerate(game.mainline_moves(), start=1):
            side = "white" if board.turn == chess.WHITE else "black"
            mover = board.turn
            best_info = engine.analyse(board, limit)
            played_info = engine.analyse(board, limit, root_moves=[move])

            best_eval = _stockfish_score(best_info)
            move_eval = _stockfish_score(played_info)
            best_for_mover = _stockfish_score(best_info, mover)
            played_for_mover = _stockfish_score(played_info, mover)
            cp_loss = max(0, best_for_mover - played_for_mover)
            best_pv = best_info.get("pv") or []

            board.push(move)
            is_checkmate = board.is_checkmate()
            mate_threat = (
                is_checkmate
                or abs(move_eval) > chess_engine.MATE_THRESHOLD
                or abs(best_eval) > chess_engine.MATE_THRESHOLD
            )

            evaluations.append({
                "move_number": move_count,
                "side_to_move": side,
                "move": move.uci(),
                "best_move": best_pv[0].uci() if best_pv else None,
                "fen": board.fen(),
                "score": move_eval,
                "score_for": orient(move_eval),
                "best_eval_for": orient(best_eval),
                "raw_cp_loss": int(best_for_mover - played_for_mover),
                "cp_loss": int(cp_loss),
                "classification": _classify_cp_loss(cp_loss),
                "mate_threat": mate_threat,
                "is_checkmate": is_checkmate,
                "perspective": perspective,
                "wdl": _stockfish_wdl(played_info),
                "analysis_source": "stockfish",
            })
    finally:
        engine.quit()

    return evaluations


def _analyze_full_with_custom_engine(game, perspective, depth):
    board = game.board()
    evaluations = []
    chess_engine.begin_search_generation(deadline=time.monotonic() + 20.0)

    def orient(value):
        return value if perspective == "white" else -value

    def search_position(search_board, search_depth):
        if search_board.is_game_over():
            return chess_engine.evaluate_board(search_board), None
        depth = max(1, search_depth)
        try:
            return chess_engine.minimax(
                search_board,
                depth,
                -math.inf,
                math.inf,
                search_board.turn == chess.WHITE,
            )
        except chess_engine.SearchTimeout:
            return chess_engine.evaluate_board(search_board), None

    # 初始局面評分
    start_eval, _ = search_position(board, depth)
    evaluations.append({
        "move_number": 0,
        "fen": board.fen(),
        "score": start_eval,
        "score_for": orient(start_eval),
        "perspective": perspective,
        "wdl": None,
        "analysis_source": "custom",
    })

    move_count = 1
    for move in game.mainline_moves():
        side = "white" if board.turn == chess.WHITE else "black"
        
        # 1. 計算這一步之前的「最佳建議」
        # 賽後趨勢用純搜尋，不使用開局庫的固定 +0.15，避免圖表前段失真。
        best_eval, best_move = search_position(board, depth)

        # 2. 執行「實際走的那一步」
        board.push(move)
        move_eval, _ = search_position(board, depth - 1)
        fen_after = board.fen()
        is_checkmate = board.is_checkmate()

        # 3. 計算損失 (CP Loss)
        # 如果是白方走，loss = 最佳分 - 實際分
        # 如果是黑方走，loss = 實際分 - 最佳分 (因為黑方希望分數越小越好)
        raw_cp_loss = best_eval - move_eval if side == "white" else move_eval - best_eval
        cp_loss = max(0, raw_cp_loss)
        
        classification = _classify_cp_loss(cp_loss)

        mate_threat = is_checkmate or abs(move_eval) > chess_engine.MATE_THRESHOLD or abs(best_eval) > chess_engine.MATE_THRESHOLD

        evaluations.append({
            "move_number": move_count,
            "side_to_move": side,
            "move": move.uci(),
            "best_move": best_move.uci() if best_move else None,
            "fen": fen_after,
            "score": move_eval,
            "score_for": orient(move_eval),
            "best_eval_for": orient(best_eval),
            "raw_cp_loss": int(raw_cp_loss),
            "cp_loss": int(cp_loss),
            "classification": classification,
            "mate_threat": mate_threat,
            "is_checkmate": is_checkmate,
            "perspective": perspective,
            "wdl": None,
            "analysis_source": "custom",
        })
        move_count += 1

    return evaluations


# 完整賽局分析：優先使用 Stockfish 作賽後裁判；遊戲走子仍由自製引擎負責。
@app.post("/analyze_full")
def analyze_full_game(request: AnalysisRequest):
    game = chess.pgn.read_game(io.StringIO(request.pgn))
    if not game:
        raise HTTPException(status_code=400, detail="Invalid PGN")
    if sum(1 for _ in game.mainline_moves()) > MAX_REVIEW_PLIES:
        raise HTTPException(
            status_code=400,
            detail=f"PGN exceeds the {MAX_REVIEW_PLIES}-ply review limit",
        )

    perspective = (request.perspective or "white").lower()
    if perspective not in ("white", "black"):
        perspective = "white"

    stockfish_path = _find_stockfish_path()
    with engine_search_slot() as engine_session:
        with engine_session.activate():
            if stockfish_path:
                nodes = max(100, int(os.getenv("STOCKFISH_REVIEW_NODES", "4000")))
                try:
                    return _analyze_full_with_stockfish(
                        game,
                        perspective,
                        stockfish_path,
                        nodes,
                    )
                except Exception as exc:
                    logger.warning(
                        "Stockfish review failed; falling back to custom engine: %s",
                        exc,
                    )

            return _analyze_full_with_custom_engine(game, perspective, request.depth)

@app.post("/review_game")
async def review_game(request: AnalysisRequest, connection: Request):
    game = review_analysis.parse_game(request.pgn)
    path = _find_stockfish_path()
    if not path:
        raise HTTPException(503, "賽後複核需要 Stockfish，目前無法啟動；請檢查安裝設定。")
    config = review_analysis.settings()

    async def events():
        output = queue.Queue()
        cancelled = threading.Event()
        def worker():
            acquired = engine_search_lock.acquire(timeout=ENGINE_QUEUE_TIMEOUT_SECONDS)
            try:
                if not acquired:
                    raise RuntimeError('busy')
                review_analysis.run_review(game, path, request.perspective, output.put, cancelled, config)
            except review_analysis.ReviewCancelled:
                pass
            except Exception as exc:
                logger.warning('Review stopped (%s)', type(exc).__name__)
                message = '分析超過時間預算，請縮短棋譜後重試。' if isinstance(exc, TimeoutError) else '分析暫時無法完成，請稍後重試。'
                output.put({'type': 'error', 'message': message})
            finally:
                if acquired:
                    engine_search_lock.release()
                output.put(None)
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            yield json.dumps({'type': 'progress', 'phase': 'quick', 'current': 0,
                              'total': sum(1 for _ in game.mainline_moves())}) + '\n'
            while not await connection.is_disconnected():
                try:
                    event = await asyncio.to_thread(output.get, True, 0.25)
                except queue.Empty:
                    continue
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + '\n'
        finally:
            cancelled.set()

    return StreamingResponse(events(), media_type='application/x-ndjson',
                             headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no'})


def coach_engine_analysis(board, depth, time_limit, teaching_time_limit):
    """(analysis, teaching_analysis) for the coach: Stockfish when available, else the built-in engine.

    COACH_ENGINE=builtin forces the built-in engine. Both run under the same
    concurrency slot as every other search.
    """
    path = _find_stockfish_path() if os.getenv("COACH_ENGINE", "stockfish") != "builtin" else None
    with engine_search_slot() as engine_session:
        if path:
            try:
                return stockfish_coach.coach_analysis(board, path)
            except Exception as exc:
                logger.warning("Stockfish coach analysis failed (%s); using the built-in engine", type(exc).__name__)
        analysis = engine_session.analyze(board, depth=depth, time_limit=time_limit)
        teaching = engine_session.teaching_analysis(board, analysis, time_limit=teaching_time_limit)
        return analysis, teaching


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
def read_games(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    games = db.query(Game).order_by(Game.date.desc()).offset(skip).limit(limit).all()
    return games

# 5. 相容性 /explain 端點 (建議使用 /get_analysis 替代)
class ExplainRequest(CoachContext):
    review_id: Optional[str] = Field(default=None, min_length=20, max_length=64)
    review_ply: Optional[int] = Field(default=None, ge=0, le=400)
    fen: str = Field(min_length=1, max_length=120)
    history: str = Field(default="", max_length=20_000)
    question: Optional[str] = Field(default=None, max_length=500)
    depth: int = Field(default=5, ge=1, le=8)
    max_question_length: int = Field(default=200, ge=1, le=500)

@app.post("/explain")
def explain_position(request: ExplainRequest):
    """
    相容性端點，提供 AI 教練建議
    建議使用 /get_analysis 替代，功能更完整
    """
    if not get_rag_engine:
        return {"advice": "RAG 引擎未啟動，請檢查 API Key 設定"}
    
    # 安全防禦：清洗用戶輸入
    user_question = request.question or "請評估目前局勢並給出建議"
    
    # 限制問題長度
    if len(user_question) > request.max_question_length:
        user_question = user_question[:request.max_question_length]

    conversation = [turn.model_dump() for turn in request.conversation]
    # Route on the same truncated text RAG receives, so both layers agree on
    # whether an engine search is needed.
    mode = question_mode(
        user_question if request.question else None,
        current_conversation(conversation, request.fen),
        request.mode,
    )
    review_sources = None
    cached_analysis = None
    review_history = request.history
    if request.review_id is not None or request.review_ply is not None:
        if request.review_id is None or request.review_ply is None:
            raise HTTPException(422, '分析編號與步數必須一起提供。')
        saved_review, position = review_analysis.get_review(request.review_id, request.review_ply, request.fen)
        review_sources, cached_analysis = review_analysis.review_sources(saved_review, position)
        review_history = saved_review.history
    
    # 計算引擎分析
    pv_line = None
    pv_score = None
    analysis = cached_analysis
    teaching_analysis = None
    
    try:
        board = chess.Board(request.fen)
        if not board.is_valid():
            raise ValueError("Invalid board position")
        if not board.is_game_over() and mode != "knowledge" and cached_analysis is None:
            analysis, teaching_analysis = coach_engine_analysis(board, request.depth, 4.0, 0.8)
            pv_line = analysis['pv']
            pv_score = analysis['score']
            logger.debug(
                "PV=%s score=%s win=%s from_book=%s",
                pv_line,
                analysis["eval_display"],
                analysis["winning_chance"],
                analysis.get("from_book", False),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid FEN string") from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Engine analysis failed: %s", e)
        return {"advice": "引擎分析暫時無法使用"}
    
    # 傳遞給 RAG 教練
    try:
        rag_engine = get_rag_engine()
        reply = rag_engine.get_response(
            request.fen,
            review_history,
            user_question,
            pv_line=pv_line,
            pv_score=pv_score,
            analysis_result=analysis,
            teaching_analysis=teaching_analysis,
            conversation=conversation,
            mode=mode if mode in {"overview", "hint"} else request.mode,
            review_evidence=review_sources,
            player_color=request.player_color,
        )
    except Exception as e:
        logger.warning("RAG analysis failed: %s", e)
        return {"advice": "教練分析暫時無法使用", "sources": [], "mode": mode, "status": "unavailable"}

    return {"advice": reply.advice, "sources": reply.sources, "mode": reply.mode, "status": reply.status}
