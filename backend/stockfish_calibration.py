import argparse
import io
import json
import os
import shutil
import statistics
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine
import chess.pgn

import chess_engine


@dataclass(frozen=True)
class CalibrationConfig:
    name: str
    depth: int
    time_limit: float
    use_book: bool
    adaptive_depth: bool


@dataclass(frozen=True)
class CalibrationPosition:
    name: str
    phase: str
    fen: str


CONFIGS = (
    CalibrationConfig("newbie", 1, 0.35, False, False),
    CalibrationConfig("beginner", 2, 0.7, False, False),
    CalibrationConfig("intermediate", 4, 1.25, True, False),
    CalibrationConfig("advanced", 5, 1.5, True, True),
)


def fen_after(pgn):
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game or game.errors:
        raise ValueError(f"Invalid calibration PGN: {pgn}")
    return game.end().board().fen()


POSITIONS = (
    CalibrationPosition("initial", "opening", chess.STARTING_FEN),
    CalibrationPosition(
        "ruy_lopez",
        "opening",
        fen_after("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7"),
    ),
    CalibrationPosition(
        "najdorf",
        "opening",
        fen_after("1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6"),
    ),
    CalibrationPosition(
        "queens_gambit_declined",
        "opening",
        fen_after("1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. Bg5 Be7 5. e3 O-O"),
    ),
    CalibrationPosition(
        "caro_kann",
        "opening",
        fen_after("1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5 5. Ng3 Bg6"),
    ),
    CalibrationPosition(
        "italian_center",
        "middlegame",
        fen_after("1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O"),
    ),
    CalibrationPosition(
        "french_center",
        "middlegame",
        fen_after("1. e4 e6 2. d4 d5 3. Nc3 Nf6 4. e5 Nfd7 5. f4 c5 6. Nf3 Nc6 7. Be3"),
    ),
    CalibrationPosition(
        "kings_indian_center",
        "middlegame",
        fen_after("1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6 5. Nf3 O-O 6. Be2 e5 7. O-O Nc6 8. d5"),
    ),
    CalibrationPosition(
        "scholar_mate_finish",
        "tactics",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
    ),
    CalibrationPosition(
        "two_knights_pressure",
        "tactics",
        "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
    ),
    CalibrationPosition(
        "queen_mate",
        "endgame",
        "7k/8/5KQ1/8/8/8/8/8 w - - 0 1",
    ),
    CalibrationPosition(
        "pawn_promotion",
        "endgame",
        "8/4P3/4K3/8/8/8/8/4k3 w - - 0 1",
    ),
    CalibrationPosition(
        "king_pawn_opposition",
        "endgame",
        "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1",
    ),
    CalibrationPosition(
        "rook_endgame",
        "endgame",
        "8/5pk1/6p1/3R4/7P/6P1/5PK1/3r4 w - - 0 1",
    ),
)


def find_stockfish(explicit_path=None):
    path = explicit_path or os.getenv("STOCKFISH_PATH") or shutil.which("stockfish")
    if not path:
        raise FileNotFoundError(
            "Stockfish not found. Install it or set STOCKFISH_PATH to the UCI binary."
        )
    return path


def score_cp(info, color):
    return info["score"].pov(color).score(mate_score=100_000)


def win_expectation(info, color, ply):
    wdl = info["score"].pov(color).wdl(model="sf", ply=ply)
    return (wdl.wins + 0.5 * wdl.draws) / 1000


def analyze_with_stockfish(engine, board, move, nodes):
    engine.configure({"Clear Hash": None})
    best_info = engine.analyse(board, chess.engine.Limit(nodes=nodes))
    engine.configure({"Clear Hash": None})
    played_info = engine.analyse(
        board,
        chess.engine.Limit(nodes=nodes),
        root_moves=[move],
    )
    best_score = score_cp(best_info, board.turn)
    played_score = score_cp(played_info, board.turn)
    raw_loss = max(0, best_score - played_score)
    best_expectation = win_expectation(best_info, board.turn, board.ply())
    played_expectation = win_expectation(played_info, board.turn, board.ply())
    expectation_loss = max(0, best_expectation - played_expectation)
    best_mate = best_info["score"].pov(board.turn).mate()
    played_mate = played_info["score"].pov(board.turn).mate()
    return {
        "best_move": best_info["pv"][0],
        "best_score": best_score,
        "played_score": played_score,
        "loss_cp": min(raw_loss, 1000),
        "expectation_loss": expectation_loss,
        "best_is_mate": best_mate is not None and best_mate > 0,
        "played_is_mate": played_mate is not None and played_mate > 0,
    }


def run_config(stockfish, config, positions, nodes):
    results = []
    for position in positions:
        chess_engine.reset_transposition_table()
        board = chess.Board(position.fen)
        analysis = chess_engine.get_analysis(
            board,
            depth=config.depth,
            time_limit=config.time_limit,
            use_book=config.use_book,
            adaptive_depth=config.adaptive_depth,
            style="balanced",
            difficulty=config.name,
        )
        move = analysis["best_move"]
        judge = analyze_with_stockfish(stockfish, board, move, nodes)
        loss = judge["loss_cp"]
        expectation_loss = judge["expectation_loss"]
        results.append({
            "name": position.name,
            "phase": position.phase,
            "played": board.san(move),
            "stockfish_best": board.san(judge["best_move"]),
            "loss_cp": loss,
            "expectation_loss": round(expectation_loss, 4),
            "best_move": loss <= 15,
            "blunder": expectation_loss >= 0.2,
            "major_piece_hang": chess_engine.major_piece_loss_after_move(board, move),
            "missed_mate": judge["best_is_mate"] and not judge["played_is_mate"],
            "depth": analysis["depth"],
            "difficulty_loss": analysis.get("difficulty_loss", 0),
        })

    losses = [item["loss_cp"] for item in results]
    expectation_losses = [item["expectation_loss"] for item in results]
    return {
        "config": config.name,
        "positions": len(results),
        "acpl": round(statistics.mean(losses), 1),
        "median_loss": round(statistics.median(losses), 1),
        "avg_expectation_loss": round(statistics.mean(expectation_losses), 4),
        "best_move_rate": round(sum(item["best_move"] for item in results) / len(results), 3),
        "blunder_rate": round(sum(item["blunder"] for item in results) / len(results), 3),
        "major_piece_hangs": sum(item["major_piece_hang"] for item in results),
        "missed_mates": sum(item["missed_mate"] for item in results),
        "results": results,
    }


def run(stockfish_path, nodes=12_000):
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    try:
        engine.configure({"Threads": 1, "Hash": 64})
        return {
            "stockfish": engine.id.get("name", "Stockfish"),
            "nodes_per_analysis": nodes,
            "reports": [run_config(engine, config, POSITIONS, nodes) for config in CONFIGS],
        }
    finally:
        engine.quit()


def main():
    parser = argparse.ArgumentParser(description="Calibrate custom bot levels with Stockfish.")
    parser.add_argument("--stockfish", help="Path to the Stockfish UCI binary.")
    parser.add_argument("--nodes", type=int, default=12_000, help="Nodes per Stockfish judgment.")
    parser.add_argument("--json", action="store_true", help="Print full JSON results.")
    parser.add_argument("--output", help="Write the full JSON report to this path.")
    args = parser.parse_args()

    report = run(find_stockfish(args.stockfish), nodes=args.nodes)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"Judge: {report['stockfish']} ({report['nodes_per_analysis']} nodes/analysis)")
    for item in report["reports"]:
        print(
            f"{item['config']:12} ACPL={item['acpl']:6.1f} "
            f"WPL={item['avg_expectation_loss']:.1%} "
            f"near-best={item['best_move_rate']:.0%} blunders={item['blunder_rate']:.0%} "
            f"hangs={item['major_piece_hangs']} missed_mates={item['missed_mates']}"
        )


if __name__ == "__main__":
    main()
