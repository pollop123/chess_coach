"""Build a reproducible, game-grouped corpus for evaluator calibration."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import chess
import chess.engine
import chess.polyglot

import chess_engine
from evaluation.phase import endgame_weight_percent
from stockfish_calibration import find_stockfish


SCHEMA_VERSION = 1
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "calibration" / "evaluation_corpus_v1.json"
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20_000,
}


def split_for_game(game_index: int) -> str:
    """Keep every position from a generated game in the same data split."""
    bucket = game_index % 20
    if bucket < 14:
        return "train"
    if bucket < 17:
        return "validation"
    return "test"


def position_topic(board: chess.Board, ply: int) -> str:
    phase = endgame_weight_percent(board)
    if phase >= 50:
        return "endgame"
    if board.is_check():
        return "tactics"
    for move in board.legal_moves:
        if move.promotion:
            return "tactics"
        if not board.is_capture(move):
            continue
        captured = board.piece_at(move.to_square)
        if captured and PIECE_VALUES[captured.piece_type] >= PIECE_VALUES[chess.ROOK]:
            return "tactics"
    if ply <= 18 and phase <= 25:
        return "opening"
    return "positional"


def _book_move(
    reader: chess.polyglot.MemoryMappedReader,
    board: chess.Board,
    rng: random.Random,
) -> chess.Move | None:
    entries = [entry for entry in reader.find_all(board) if entry.move in board.legal_moves]
    if not entries:
        return None
    entries.sort(key=lambda entry: (-entry.weight, entry.move.uci()))
    candidates = entries[: min(5, len(entries))]
    return rng.choices(candidates, weights=[max(1, item.weight) for item in candidates])[0].move


def _engine_move(
    engine: chess.engine.SimpleEngine,
    board: chess.Board,
    nodes: int,
    rng: random.Random,
) -> chess.Move | None:
    multipv = min(3, board.legal_moves.count())
    if multipv == 0:
        return None
    analysis = engine.analyse(board, chess.engine.Limit(nodes=nodes), multipv=multipv)
    moves = [item["pv"][0] for item in analysis if item.get("pv")]
    if not moves:
        return None
    roll = rng.random()
    choice = 0 if roll < 0.8 else 1 if roll < 0.95 else 2
    return moves[min(choice, len(moves) - 1)]


def _position_key(board: chess.Board) -> str:
    return " ".join(board.fen().split()[:4])


def generate_game(
    engine: chess.engine.SimpleEngine,
    reader: chess.polyglot.MemoryMappedReader,
    game_index: int,
    *,
    nodes: int,
    max_plies: int,
    sample_every: int,
    seed: int,
) -> list[dict]:
    rng = random.Random(seed + game_index * 1_000_003)
    board = chess.Board()
    positions = []
    seen = set()

    for ply in range(1, max_plies + 1):
        if board.is_game_over(claim_draw=True):
            break
        move = _book_move(reader, board, rng) if ply <= 12 else None
        if move is None:
            move = _engine_move(engine, board, nodes, rng)
        if move is None or move not in board.legal_moves:
            break
        board.push(move)

        if ply < 10 or ply % sample_every:
            continue
        key = _position_key(board)
        if key in seen or board.is_game_over(claim_draw=True):
            continue
        seen.add(key)
        positions.append(
            {
                "name": f"generated_{game_index:03d}_{ply:03d}",
                "fen": board.fen(),
                "topic": position_topic(board, ply),
                "game_id": f"generated_{game_index:03d}",
                "ply": ply,
                "split": split_for_game(game_index),
            }
        )
    return positions


def round_robin_sample(games: list[list[dict]], target: int) -> list[dict]:
    """Sample across games so the final corpus is not dominated by early games."""
    selected = []
    for index in range(max((len(game) for game in games), default=0)):
        for game in games:
            if index < len(game):
                selected.append(game[index])
                if len(selected) == target:
                    return selected
    return selected


def build_corpus(
    stockfish_path: str,
    *,
    games: int = 24,
    target: int = 300,
    nodes: int = 3_000,
    max_plies: int = 96,
    sample_every: int = 4,
    seed: int = 20260716,
) -> dict:
    generated_games = []
    with (
        chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine,
        chess.polyglot.open_reader(chess_engine.BOOK_PATH) as reader,
    ):
        engine.configure({"Threads": 1, "Hash": 64})
        for game_index in range(games):
            generated_games.append(
                generate_game(
                    engine,
                    reader,
                    game_index,
                    nodes=nodes,
                    max_plies=max_plies,
                    sample_every=sample_every,
                    seed=seed,
                )
            )

        positions = round_robin_sample(generated_games, target)
        topic_counts = {
            topic: sum(position["topic"] == topic for position in positions)
            for topic in ("opening", "positional", "tactics", "endgame")
        }
        split_counts = {
            split: sum(position["split"] == split for position in positions)
            for split in ("train", "validation", "test")
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "generator": "stockfish_selfplay_with_polyglot_openings",
            "stockfish": engine.id.get("name", "Stockfish"),
            "seed": seed,
            "nodes_per_move": nodes,
            "games": games,
            "target_positions": target,
            "positions": positions,
            "topic_counts": topic_counts,
            "split_counts": split_counts,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stockfish")
    parser.add_argument("--games", type=int, default=24)
    parser.add_argument("--target", type=int, default=300)
    parser.add_argument("--nodes", type=int, default=3_000)
    parser.add_argument("--max-plies", type=int, default=96)
    parser.add_argument("--sample-every", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260716)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report = build_corpus(
        find_stockfish(args.stockfish),
        games=args.games,
        target=args.target,
        nodes=args.nodes,
        max_plies=args.max_plies,
        sample_every=args.sample_every,
        seed=args.seed,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(report['positions'])} positions to {output} "
        f"topics={report['topic_counts']} splits={report['split_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
