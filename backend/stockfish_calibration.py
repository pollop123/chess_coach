import argparse
import io
import json
import os
import shutil
import statistics
from dataclasses import dataclass, replace
from pathlib import Path

import chess
import chess.engine
import chess.pgn

import chess_engine
from evaluation import CALIBRATED_FEATURE_WEIGHTS, PositionEvaluator


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


def move_loss_metrics(
    best_move,
    played_move,
    best_score,
    played_score,
    best_expectation,
    played_expectation,
):
    if best_move == played_move:
        return {"loss_cp": 0, "expectation_loss": 0}
    return {
        "loss_cp": min(max(0, best_score - played_score), 1000),
        "expectation_loss": max(0, best_expectation - played_expectation),
    }


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
    best_expectation = win_expectation(best_info, board.turn, board.ply())
    played_expectation = win_expectation(played_info, board.turn, board.ply())
    best_move = best_info["pv"][0]
    metrics = move_loss_metrics(
        best_move,
        move,
        best_score,
        played_score,
        best_expectation,
        played_expectation,
    )
    best_mate = best_info["score"].pov(board.turn).mate()
    played_mate = played_info["score"].pov(board.turn).mate()
    return {
        "best_move": best_move,
        "best_score": best_score,
        "played_score": played_score,
        "loss_cp": metrics["loss_cp"],
        "expectation_loss": metrics["expectation_loss"],
        "best_is_mate": best_mate is not None and best_mate > 0,
        "played_is_mate": played_mate is not None and played_mate > 0,
    }


def run_config(stockfish, config, positions, nodes, *, use_tt=True):
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
            use_tt=use_tt,
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
            "nodes": analysis.get("nodes", 0),
            "tt_hits": analysis.get("tt_hits", 0),
            "tt_cutoffs": analysis.get("tt_cutoffs", 0),
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


def load_corpus_positions(path, splits=None):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("positions"), list):
        raise ValueError("Unsupported evaluation corpus schema")
    selected_splits = set(splits or ())
    positions = []
    for item in payload["positions"]:
        if selected_splits and item.get("split") not in selected_splits:
            continue
        board = chess.Board(item["fen"])
        if not board.is_valid() or board.is_game_over(claim_draw=True):
            raise ValueError(f"Invalid or finished corpus position: {item.get('name')}")
        positions.append(
            CalibrationPosition(str(item["name"]), str(item["topic"]), str(item["fen"]))
        )
    if not positions:
        raise ValueError("No corpus positions matched the requested split")
    return tuple(positions)


def limit_positions_per_phase(positions, limit):
    if limit is None:
        return tuple(positions)
    if limit <= 0:
        raise ValueError("Position limit per phase must be positive")
    counts = {}
    selected = []
    for position in positions:
        count = counts.get(position.phase, 0)
        if count >= limit:
            continue
        selected.append(position)
        counts[position.phase] = count + 1
    return tuple(selected)


def override_configs(configs, *, depth=None, time_limit=None):
    if depth is not None and depth <= 0:
        raise ValueError("Depth override must be positive")
    if time_limit is not None and time_limit <= 0:
        raise ValueError("Time-limit override must be positive")
    return tuple(
        replace(
            config,
            depth=depth if depth is not None else config.depth,
            time_limit=time_limit if time_limit is not None else config.time_limit,
        )
        for config in configs
    )


def parse_feature_weights(values):
    """Parse repeatable NAME=PERCENT evaluator overrides for offline A/B."""
    weights = {}
    for value in values or ():
        try:
            name, raw_weight = value.split("=", 1)
            weight = int(raw_weight)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid feature weight {value!r}; expected NAME=PERCENT"
            ) from exc
        if name not in CALIBRATED_FEATURE_WEIGHTS:
            allowed = ", ".join(sorted(CALIBRATED_FEATURE_WEIGHTS))
            raise ValueError(f"Unknown feature {name!r}; choose from: {allowed}")
        if not -200 <= weight <= 200:
            raise ValueError(f"Feature weight {name!r} must be between -200 and 200")
        weights[name] = weight
    return weights


def run(
    stockfish_path,
    nodes=12_000,
    *,
    configs=CONFIGS,
    positions=POSITIONS,
    feature_weights=None,
    use_tt=True,
):
    active_weights = dict(CALIBRATED_FEATURE_WEIGHTS)
    if feature_weights:
        active_weights.update(feature_weights)
    engine_session = chess_engine.EngineSession(
        evaluator=PositionEvaluator(active_weights)
    )
    engine = None
    try:
        with engine_session.activate():
            engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
            engine.configure({"Threads": 1, "Hash": 64})
            return {
                "stockfish": engine.id.get("name", "Stockfish"),
                "nodes_per_analysis": nodes,
                "feature_weights": active_weights,
                "use_tt": use_tt,
                "reports": [
                    run_config(engine, config, positions, nodes, use_tt=use_tt)
                    for config in configs
                ],
            }
    finally:
        if engine is not None:
            engine.quit()


def main():
    parser = argparse.ArgumentParser(description="Calibrate custom bot levels with Stockfish.")
    parser.add_argument("--stockfish", help="Path to the Stockfish UCI binary.")
    parser.add_argument("--nodes", type=int, default=12_000, help="Nodes per Stockfish judgment.")
    parser.add_argument("--json", action="store_true", help="Print full JSON results.")
    parser.add_argument("--output", help="Write the full JSON report to this path.")
    parser.add_argument("--corpus", help="JSON corpus generated by build_evaluation_corpus.py")
    parser.add_argument(
        "--split",
        action="append",
        choices=("train", "validation", "test"),
        help="limit an external corpus to one or more game-grouped splits",
    )
    parser.add_argument(
        "--config",
        action="append",
        choices=tuple(config.name for config in CONFIGS),
        help="run only selected bot configurations; may be repeated",
    )
    parser.add_argument(
        "--limit-per-phase",
        type=int,
        help="deterministic screening limit for each phase/topic",
    )
    parser.add_argument("--depth-override", type=int)
    parser.add_argument("--time-limit-override", type=float)
    parser.add_argument(
        "--feature-weight",
        action="append",
        default=[],
        metavar="NAME=PERCENT",
        help="override an evaluator feature weight; repeat for joint calibration",
    )
    parser.add_argument(
        "--no-tt",
        action="store_true",
        help="disable transposition-table lookup and storage for an A/B baseline",
    )
    args = parser.parse_args()

    try:
        feature_weights = parse_feature_weights(args.feature_weight)
    except ValueError as exc:
        parser.error(str(exc))

    selected_configs = tuple(
        config for config in CONFIGS if not args.config or config.name in args.config
    )
    selected_configs = override_configs(
        selected_configs,
        depth=args.depth_override,
        time_limit=args.time_limit_override,
    )
    positions = load_corpus_positions(args.corpus, args.split) if args.corpus else POSITIONS
    positions = limit_positions_per_phase(positions, args.limit_per_phase)
    report = run(
        find_stockfish(args.stockfish),
        nodes=args.nodes,
        configs=selected_configs,
        positions=positions,
        feature_weights=feature_weights,
        use_tt=not args.no_tt,
    )
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
