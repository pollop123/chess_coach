"""Read-only Chess.com imports. Public responses are cached briefly in memory."""
from collections import OrderedDict
from contextlib import contextmanager
import io
import json
import re
import threading
import time

import chess.pgn
import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/imports/chesscom", tags=["imports"])
BASE_URL = "https://api.chess.com/pub/player"
USERNAME = re.compile(r"[a-zA-Z0-9_-]{1,50}\Z")
MONTH = re.compile(r"(\d{4})/(0[1-9]|1[0-2])\Z")
MAX_BYTES = 8 * 1024 * 1024
_cache = OrderedDict()
_lock = threading.Lock()


def clean_username(username):
    if not USERNAME.fullmatch(username):
        raise HTTPException(422, "請輸入 Chess.com 使用者名稱，不是網址。")
    return username.lower()


@contextmanager
def public_client():
    # Serialize upstream requests in each web process, including cache access.
    if not _lock.acquire(timeout=2):
        raise HTTPException(503, "匯入服務忙碌中，請稍後重試。", headers={"Retry-After": "2"})
    try:
        with httpx.Client(timeout=10, follow_redirects=False, headers={
            "User-Agent": "ChessCoach/1.0 (https://github.com/pollop123/chess_coach)",
            "Accept": "application/json",
        }) as client:
            yield client
    finally:
        _lock.release()


def fetch_json(client, url):
    cached = _cache.get(url)
    if cached and time.monotonic() - cached[0] < 300:
        _cache.move_to_end(url)
        return cached[1]
    try:
        with client.stream("GET", url) as response:
            if response.status_code == 404:
                raise HTTPException(404, "找不到這個使用者或月份的棋局。請確認名稱。")
            if response.status_code == 429:
                raise HTTPException(429, "Chess.com 暫時限制請求，請稍後再試。", headers={"Retry-After": "60"})
            if response.status_code != 200:
                raise HTTPException(502, "Chess.com 暫時無法提供資料，請稍後再試。")
            data = bytearray()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise HTTPException(502, "此月份資料過大，請選擇其他月份。")
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("Expected an object")
    except httpx.TimeoutException as exc:
        raise HTTPException(504, "Chess.com 回應逾時，請再試一次。") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Chess.com 回傳的資料暫時無法讀取。") from exc
    _cache[url] = (time.monotonic(), payload)
    _cache.move_to_end(url)
    # Monthly archives can be large, so keep this per-process cache small.
    while len(_cache) > 4:
        _cache.popitem(last=False)
    return payload


def normalize_game(raw, username):
    """Only pass a single, complete, legal standard-chess game to the UI."""
    if not isinstance(raw, dict) or raw.get("rules") != "chess":
        return None
    pgn = raw.get("pgn")
    url = raw.get("url", "")
    if not isinstance(pgn, str) or not 1 <= len(pgn) <= 200_000:
        return None
    if not isinstance(url, str) or not re.fullmatch(r"https://www\.chess\.com/(?:game/(?:live|daily)|live/game|daily/game)/\d+", url):
        return None
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
        if not game or game.errors or game.headers.get("Variant", "Standard") not in {"Standard", "Chess"}:
            return None
        if game.headers.get("Result") not in {"1-0", "0-1", "1/2-1/2"}:
            return None
        board = game.board()
        if not board.is_valid() or board.chess960:
            return None
        moves = list(game.mainline_moves())
        if not 1 <= len(moves) <= 400:
            return None
        white, black = game.headers.get("White", ""), game.headers.get("Black", "")
        if username not in {white.lower(), black.lower()}:
            return None
        side = "white" if white.lower() == username else "black"
        for move in moves:
            if move not in board.legal_moves:
                return None
            board.push(move)
        end_time = int(raw.get("end_time", 0))
        if not 0 < end_time < 32_503_680_000:
            return None
        return {
            "id": url, "url": url, "username": username,
            "white": white, "black": black, "perspective": side,
            "result": game.headers["Result"], "end_time": end_time,
            "time_class": str(raw.get("time_class", ""))[:20],
            "time_control": str(raw.get("time_control", ""))[:30],
            "pgn": game.accept(chess.pgn.StringExporter(headers=True, variations=False, comments=False)),
        }
    except (ValueError, TypeError, AttributeError):
        return None


@router.get("/{username}/archives")
def archives(username: str):
    username = clean_username(username)
    with public_client() as client:
        data = fetch_json(client, f"{BASE_URL}/{username}/games/archives")
    raw = data.get("archives")
    if not isinstance(raw, list):
        raise HTTPException(502, "Chess.com 的月份清單格式不正確。")
    prefix = f"{BASE_URL}/{username}/games/"
    months = {value[len(prefix):] for value in raw if isinstance(value, str)
              and value.startswith(prefix) and MONTH.fullmatch(value[len(prefix):])}
    return {"username": username, "months": sorted(months, reverse=True)}


@router.get("/{username}/{year}/{month}")
def monthly_games(username: str, year: int, month: int, page: int = Query(default=0, ge=0, le=1000)):
    username = clean_username(username)
    if not 2007 <= year <= 2100 or not 1 <= month <= 12:
        raise HTTPException(422, "月份格式不正確。")
    with public_client() as client:
        data = fetch_json(client, f"{BASE_URL}/{username}/games/{year:04d}/{month:02d}")
    raw = data.get("games")
    if not isinstance(raw, list):
        raise HTTPException(502, "Chess.com 的棋局清單格式不正確。")
    candidates = [item for item in raw if isinstance(item, dict) and item.get("rules") == "chess"
                  and type(item.get("end_time")) is int]
    candidates.sort(key=lambda item: item["end_time"], reverse=True)
    batch = candidates[page * 20:(page + 1) * 20]
    games = [game for item in batch if (game := normalize_game(item, username))]
    return {"username": username, "games": games, "page": page,
            "has_more": len(candidates) > (page + 1) * 20, "skipped": len(batch) - len(games)}
