import chess
import math
import chess.polyglot
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import database
from api import router as api_router
from rag import rag_engine
import chess_engine  # Import the new engine module

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

class MoveRequest(BaseModel):
    fen: str
    difficulty: int = 3

class MoveResponse(BaseModel):
    best_move: str
    evaluation: int

@app.get("/")
def read_root():
    return {"message": "Chess AI Backend is running!"}

@app.post("/make_move", response_model=MoveResponse)
def make_move(request: MoveRequest):
    board = chess.Board(request.fen)
    
    # Use the engine from the new module
    best_move = chess_engine.get_best_move(board, request.difficulty)
    
    if best_move is None:
        # Fallback for game over or error
        return {"best_move": "none", "evaluation": 0}
        
    # Calculate evaluation for the response
    board.push(best_move)
    eval_score = chess_engine.evaluate_board(board)
    
    return {"best_move": best_move.uci(), "evaluation": eval_score}