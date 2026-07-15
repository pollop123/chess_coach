"""Validate training lesson positions with python-chess and optional Stockfish."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import chess
import chess.engine


ROOT = Path(__file__).resolve().parents[1]
EXPORT_SCRIPT = ROOT / "frontend" / "scripts" / "export-training-lessons.mjs"
DEFAULT_STOCKFISH_PATHS = (
    "/opt/homebrew/bin/stockfish",
    "/usr/local/bin/stockfish",
    "/usr/games/stockfish",
)


class LessonValidationError(ValueError):
    pass


def load_lessons() -> list[dict]:
    result = subprocess.run(
        ["node", str(EXPORT_SCRIPT)],
        cwd=ROOT / "frontend",
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def initial_board(lesson: dict) -> chess.Board:
    return chess.Board(lesson.get("startFen") or chess.STARTING_FEN)


def validate_semantics(lessons: list[dict]) -> list[str]:
    errors: list[str] = []
    for lesson in lessons:
        lesson_id = lesson.get("id", "<missing-id>")
        try:
            board = initial_board(lesson)
        except ValueError as exc:
            errors.append(f"{lesson_id}: malformed FEN: {exc}")
            continue

        if not board.is_valid():
            errors.append(
                f"{lesson_id}: invalid position status={int(board.status())} fen={board.fen()}"
            )
            continue

        for ply, san in enumerate(lesson.get("moves") or [], start=1):
            try:
                board.push_san(san)
            except ValueError as exc:
                errors.append(f"{lesson_id}: illegal SAN at ply {ply}: {san}: {exc}")
                break
    return errors


def find_stockfish(explicit_path: str | None = None) -> str | None:
    candidates = [explicit_path, os.getenv("STOCKFISH_PATH"), shutil.which("stockfish")]
    candidates.extend(DEFAULT_STOCKFISH_PATHS)
    return next((path for path in candidates if path and Path(path).is_file()), None)


def _outcome_bucket(score: chess.engine.PovScore) -> str:
    cp = score.score(mate_score=100_000)
    if cp is None:
        return "unknown"
    if cp >= 150:
        return "win"
    if cp <= -150:
        return "loss"
    return "drawish"


def engine_loss_limit(lesson: dict) -> int:
    if "engineMaxCpLoss" in lesson:
        return int(lesson["engineMaxCpLoss"])
    return 30 if lesson.get("type") == "puzzle" else 80


def first_move_is_acceptable(
    lesson: dict, *, loss_cp: int, preserves_outcome: bool, delivers_checkmate: bool
) -> bool:
    if "checkmate" in (lesson.get("tags") or []):
        return delivers_checkmate
    return loss_cp <= engine_loss_limit(lesson) and preserves_outcome


def validate_first_moves_with_stockfish(
    lessons: list[dict], stockfish_path: str, nodes: int = 50_000
) -> tuple[list[str], list[dict]]:
    errors: list[str] = []
    results: list[dict] = []
    with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
        for lesson in lessons:
            if lesson.get("type") == "opening":
                continue
            board = initial_board(lesson)
            if not board.is_valid() or not lesson.get("moves"):
                continue
            lesson_id = lesson["id"]
            try:
                lesson_move = board.parse_san(lesson["moves"][0])
            except ValueError:
                continue

            root = engine.analyse(board, chess.engine.Limit(nodes=nodes))
            best_move = root.get("pv", [None])[0]
            if best_move is None:
                errors.append(f"{lesson_id}: Stockfish returned no principal variation")
                continue

            after = board.copy(stack=False)
            after.push(lesson_move)
            played = engine.analyse(
                board,
                chess.engine.Limit(nodes=nodes),
                root_moves=[lesson_move],
            )
            root_score = root["score"].pov(board.turn)
            played_score = played["score"].pov(board.turn)
            best_cp = root_score.score(mate_score=100_000)
            played_cp = played_score.score(mate_score=100_000)
            loss_cp = max(0, (best_cp or 0) - (played_cp or 0))
            preserves_outcome = _outcome_bucket(root_score) == _outcome_bucket(played_score)
            max_loss = engine_loss_limit(lesson)
            accepted = first_move_is_acceptable(
                lesson,
                loss_cp=loss_cp,
                preserves_outcome=preserves_outcome,
                delivers_checkmate=after.is_checkmate(),
            )
            result = {
                "id": lesson_id,
                "played": board.san(lesson_move),
                "best": board.san(best_move),
                "loss_cp": loss_cp,
                "preserves_outcome": preserves_outcome,
                "accepted": accepted,
            }
            results.append(result)
            if not accepted:
                errors.append(
                    f"{lesson_id}: {result['played']} vs {result['best']} loses {loss_cp}cp "
                    f"(limit {max_loss}, preserves_outcome={preserves_outcome})"
                )
    return errors, results


def raise_for_errors(errors: list[str]) -> None:
    if errors:
        raise LessonValidationError("\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stockfish")
    parser.add_argument("--nodes", type=int, default=50_000)
    parser.add_argument("--require-stockfish", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    lessons = load_lessons()
    semantic_errors = validate_semantics(lessons)
    errors = list(semantic_errors)
    stockfish_path = find_stockfish(args.stockfish) if (args.stockfish or args.require_stockfish) else None
    engine_results: list[dict] = []
    if args.require_stockfish and not stockfish_path:
        errors.append("Stockfish is required but was not found")
    if stockfish_path:
        engine_errors, engine_results = validate_first_moves_with_stockfish(
            lessons, stockfish_path, nodes=args.nodes
        )
        errors.extend(engine_errors)

    report = {
        "lessons": len(lessons),
        "semantic_valid": not semantic_errors,
        "stockfish": stockfish_path,
        "engine_results": engine_results,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif errors:
        print("Training lesson validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
    else:
        engine_suffix = f", {len(engine_results)} engine checks" if engine_results else ""
        print(f"Validated {len(lessons)} training lessons{engine_suffix}.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
