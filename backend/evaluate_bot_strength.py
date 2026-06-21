import argparse
import json
import time
from dataclasses import dataclass

import chess

import chess_engine


@dataclass(frozen=True)
class BotConfig:
    name: str
    depth: int
    time_limit: float | None
    use_book: bool
    adaptive_depth: bool
    style: str = "balanced"


@dataclass(frozen=True)
class TestPosition:
    name: str
    phase: str
    fen: str
    expected: tuple[str, ...]
    theme: str
    note: str
    must_find_mate: bool = False


BOT_CONFIGS = (
    BotConfig("newbie", 1, 0.35, False, False),
    BotConfig("beginner", 2, 0.7, False, False),
    BotConfig("intermediate", 4, 1.25, True, False),
    BotConfig("intermediate_trickster", 4, 1.25, True, False, "trickster"),
    BotConfig("advanced", 5, 1.5, True, True),
)


POSITIONS = (
    TestPosition(
        name="scholar_mate_finish",
        phase="middlegame",
        fen="r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        expected=("Qxf7#",),
        theme="mate_in_one",
        note="White should finish the attack on f7.",
        must_find_mate=True,
    ),
    TestPosition(
        name="two_knights_pressure",
        phase="middlegame",
        fen="r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        expected=("Qf3", "d4"),
        theme="develop_with_threat",
        note="White should add pressure without sacrificing unsafely.",
    ),
    TestPosition(
        name="queen_king_mate",
        phase="endgame",
        fen="7k/6Q1/5K2/8/8/8/8/8 w - - 0 1",
        expected=("Kf7#", "Kg6#"),
        theme="mate_in_one",
        note="King support creates an immediate mate.",
        must_find_mate=True,
    ),
    TestPosition(
        name="pawn_promotion",
        phase="endgame",
        fen="8/4P3/4K3/8/8/8/8/4k3 w - - 0 1",
        expected=("e8=Q",),
        theme="promotion",
        note="The passed pawn should promote immediately.",
    ),
    TestPosition(
        name="opening_development",
        phase="opening",
        fen=chess.STARTING_FEN,
        expected=("e4", "d4", "Nf3", "c4"),
        theme="opening_principles",
        note="A reasonable first move should take or influence the center.",
    ),
)


def move_to_san(board: chess.Board, move: chess.Move | None) -> str | None:
    if move is None:
        return None
    try:
        return board.san(move)
    except Exception:
        return move.uci()


def evaluate_position(config: BotConfig, position: TestPosition) -> dict:
    board = chess.Board(position.fen)
    started = time.perf_counter()
    analysis = chess_engine.get_analysis(
        board,
        depth=config.depth,
        time_limit=config.time_limit,
        use_book=config.use_book,
        adaptive_depth=config.adaptive_depth,
        style=config.style,
        difficulty=config.name.removesuffix("_trickster"),
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    san = move_to_san(board, analysis.get("best_move"))
    matched = san in position.expected
    missed_mate = position.must_find_mate and not matched

    return {
        "name": position.name,
        "phase": position.phase,
        "theme": position.theme,
        "expected": list(position.expected),
        "played": san,
        "matched": matched,
        "missed_mate": missed_mate,
        "score": analysis.get("score"),
        "display": analysis.get("eval_display"),
        "depth": analysis.get("depth"),
        "from_book": analysis.get("from_book", False),
        "style": analysis.get("style", "balanced"),
        "style_bonus": analysis.get("style_bonus", 0),
        "difficulty_loss": analysis.get("difficulty_loss", 0),
        "nodes": analysis.get("nodes"),
        "elapsed_ms": elapsed_ms,
        "note": position.note,
    }


def summarize(config: BotConfig, results: list[dict]) -> dict:
    total = len(results)
    matched = sum(1 for item in results if item["matched"])
    missed_mates = sum(1 for item in results if item["missed_mate"])
    by_phase = {}

    for item in results:
        phase = item["phase"]
        if phase not in by_phase:
            by_phase[phase] = {"total": 0, "matched": 0}
        by_phase[phase]["total"] += 1
        by_phase[phase]["matched"] += int(item["matched"])

    for phase in by_phase.values():
        phase["accuracy"] = round(phase["matched"] / phase["total"], 3)

    return {
        "config": {
            "name": config.name,
            "depth": config.depth,
            "time_limit": config.time_limit,
            "use_book": config.use_book,
            "adaptive_depth": config.adaptive_depth,
            "style": config.style,
        },
        "total": total,
        "matched": matched,
        "accuracy": round(matched / total, 3),
        "missed_mates": missed_mates,
        "avg_depth": round(sum(item["depth"] or 0 for item in results) / total, 2),
        "avg_elapsed_ms": round(sum(item["elapsed_ms"] for item in results) / total),
        "by_phase": by_phase,
    }


def run(configs: tuple[BotConfig, ...]) -> dict:
    reports = []
    for config in configs:
        results = [evaluate_position(config, position) for position in POSITIONS]
        reports.append({
            "summary": summarize(config, results),
            "positions": results,
        })
    return {"reports": reports}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Chess Coach bot strength on fixed teaching positions.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report = run(BOT_CONFIGS)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    for bot_report in report["reports"]:
        summary = bot_report["summary"]
        config = summary["config"]
        print(f"\n{config['name']} depth={config['depth']} time_limit={config['time_limit']} style={config['style']}")
        print(
            f"accuracy={summary['accuracy']:.0%} "
            f"missed_mates={summary['missed_mates']} "
            f"avg_depth={summary['avg_depth']} "
            f"avg_elapsed_ms={summary['avg_elapsed_ms']}"
        )
        for item in bot_report["positions"]:
            mark = "OK" if item["matched"] else "MISS"
            print(
                f"  [{mark}] {item['phase']}/{item['theme']} {item['name']}: "
                f"played={item['played']} expected={','.join(item['expected'])} "
                f"depth={item['depth']} book={item['from_book']} style_bonus={item['style_bonus']}"
            )


if __name__ == "__main__":
    main()
