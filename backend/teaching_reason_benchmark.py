import argparse
import json
from dataclasses import dataclass

import chess

import chess_engine


@dataclass(frozen=True)
class ReasonCase:
    name: str
    fen: str
    san: str
    expected_reason: str | None = None
    forbidden_reasons: tuple[str, ...] = ()
    expected_themes: tuple[str, ...] = ()
    forbidden_themes: tuple[str, ...] = ()
    expected_warnings: tuple[str, ...] = ()
    forbidden_warnings: tuple[str, ...] = ()


CASES = (
    ReasonCase(
        "opening_development",
        chess.STARTING_FEN,
        "Nf3",
        expected_reason="develops_piece",
        expected_themes=("opening_principle", "development"),
    ),
    ReasonCase(
        "free_rook_capture",
        "6k1/3r4/8/8/8/8/8/3Q2K1 w - - 0 1",
        "Qxd7",
        expected_reason="wins_material",
        expected_themes=("tactics",),
    ),
    ReasonCase(
        "defended_rook_capture",
        "6k1/3r4/8/5b2/8/8/8/3Q2K1 w - - 0 1",
        "Qxd7",
        forbidden_reasons=("wins_material",),
        forbidden_themes=("tactics",),
    ),
    ReasonCase(
        "legal_queen_threat",
        "k6r/8/8/7Q/8/8/8/4K3 w - - 0 1",
        "Qg5",
        expected_reason="avoids_major_piece_loss",
        forbidden_warnings=("hangs_major_piece", "allows_mate_threat"),
    ),
    ReasonCase(
        "queen_hang_warning",
        "7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1",
        "Qxh7+",
        expected_reason="check",
        expected_warnings=("hangs_major_piece",),
        forbidden_warnings=("allows_mate_threat",),
    ),
    ReasonCase(
        "pinned_attacker",
        "4k3/4n3/8/5Q2/8/8/8/K3R3 w - - 0 1",
        "Qg4",
        forbidden_reasons=("avoids_major_piece_loss",),
    ),
    ReasonCase(
        "pawn_leaves_center",
        "4k3/8/8/8/3P4/8/8/4K3 w - - 0 1",
        "d5",
        forbidden_reasons=("controls_center",),
        forbidden_themes=("center_control",),
    ),
    ReasonCase(
        "enemy_king_attack",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "Qxf7#",
        expected_reason="checkmate",
        expected_themes=("king_attack", "tactics"),
        forbidden_themes=("king_safety",),
    ),
    ReasonCase(
        "two_knights_fork",
        "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        "Nxf7",
        expected_reason="creates_valuable_piece_fork",
        expected_themes=("tactics",),
        forbidden_themes=("center_control",),
    ),
    ReasonCase(
        "single_valuable_target",
        "3qk3/8/8/6N1/8/8/8/4K3 w - - 0 1",
        "Nf7",
        forbidden_reasons=("creates_valuable_piece_fork",),
    ),
    ReasonCase(
        "fen_only_middlegame",
        "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P4/2P1PN2/PP1NBPPP/R2Q1RK1 w - - 0 22",
        "dxc5",
        forbidden_themes=("opening_principle",),
    ),
    ReasonCase(
        "queenless_full_armies",
        "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1",
        "Nf3",
        forbidden_themes=("opening_principle", "endgame"),
    ),
)


def _mirror(board, move):
    return board.mirror(), chess.Move(
        chess.square_mirror(move.from_square),
        chess.square_mirror(move.to_square),
        promotion=move.promotion,
    )


def evaluate_case(case, perspective):
    board = chess.Board(case.fen)
    move = board.parse_san(case.san)
    if perspective == "black":
        board, move = _mirror(board, move)
    warnings = []
    if chess_engine.major_piece_loss_after_move(board, move):
        warnings.append("hangs_major_piece")
    if chess_engine._move_allows_immediate_mate(board, move):
        warnings.append("allows_mate_threat")
    reason = chess_engine._move_reason(board, move, warnings)
    themes = chess_engine._move_themes(board, move, reason)
    failures = []
    if case.expected_reason and reason != case.expected_reason:
        failures.append(f"expected reason {case.expected_reason}, got {reason}")
    for forbidden in case.forbidden_reasons:
        if reason == forbidden:
            failures.append(f"forbidden reason {forbidden}")
    for expected in case.expected_themes:
        if expected not in themes:
            failures.append(f"missing theme {expected}")
    for forbidden in case.forbidden_themes:
        if forbidden in themes:
            failures.append(f"forbidden theme {forbidden}")
    for expected in case.expected_warnings:
        if expected not in warnings:
            failures.append(f"missing warning {expected}")
    for forbidden in case.forbidden_warnings:
        if forbidden in warnings:
            failures.append(f"forbidden warning {forbidden}")
    return {
        "name": case.name,
        "perspective": perspective,
        "reason": reason,
        "themes": themes,
        "warnings": warnings,
        "failures": failures,
        "passed": not failures,
    }


def run(cases=CASES):
    results = [
        evaluate_case(case, perspective)
        for case in cases
        for perspective in ("white", "black")
    ]
    failures = [result for result in results if not result["passed"]]
    return {
        "mode": "reason_false_positive",
        "positions": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "failures": failures,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check teaching reasons/themes for positive and false-positive fixtures."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = run()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Teaching reason benchmark: {report['passed']}/{report['positions']} passed")
        for failure in report["failures"]:
            print(f"  [MISS] {failure['perspective']}/{failure['name']}: {', '.join(failure['failures'])}")
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
