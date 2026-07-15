"""Independent Stockfish oracle for teaching-candidate accuracy."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import chess
import chess.engine

import chess_engine
from validate_training_lessons import find_stockfish


@dataclass(frozen=True)
class AccuracyPosition:
    name: str
    fen: str
    topic: str
    depth: int = 3
    candidate_count: int = 6


def _fen_after(*sans: str) -> str:
    board = chess.Board()
    for san in sans:
        board.push_san(san)
    return board.fen()


POSITIONS = (
    AccuracyPosition(
        "scholar_mate_finish",
        "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "tactics",
    ),
    AccuracyPosition(
        "two_knights_tactic",
        "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        "tactics",
    ),
    AccuracyPosition("queen_mate_net", "7k/8/5KQ1/8/8/8/8/8 w - - 0 1", "tactics"),
    AccuracyPosition("queen_safety", "7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1", "tactics"),
    AccuracyPosition("rook_activity", "8/5pk1/6p1/3R4/7P/6P1/5PK1/r7 w - - 0 1", "endgame"),
    AccuracyPosition("king_opposition", "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1", "endgame"),
    AccuracyPosition("black_back_rank_mate", "r5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1", "tactics"),
    AccuracyPosition("starting_position", chess.STARTING_FEN, "opening"),
    AccuracyPosition("italian_two_knights", _fen_after("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"), "opening"),
    AccuracyPosition("london_setup", _fen_after("d4", "d5", "Nf3", "Nf6", "Bf4"), "opening"),
    AccuracyPosition(
        "sicilian_setup",
        _fen_after("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6"),
        "opening",
    ),
    AccuracyPosition(
        "caro_kann_setup",
        _fen_after("e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"),
        "opening",
    ),
    AccuracyPosition(
        "center_pressure",
        "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w kq - 0 6",
        "positional",
    ),
    AccuracyPosition(
        "center_break",
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 w kq - 4 5",
        "positional",
    ),
    AccuracyPosition(
        "pin_pressure",
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 2 3",
        "positional",
    ),
    AccuracyPosition(
        "fen_only_middlegame",
        "r1bq1rk1/pp2bppp/2n1pn2/2pp4/3P4/2P1PN2/PP1NBPPP/R2Q1RK1 w - - 0 22",
        "positional",
    ),
    AccuracyPosition("white_back_rank_mate", "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "tactics"),
    AccuracyPosition("pawn_promotion", "8/4P3/4K3/8/8/8/8/4k3 w - - 0 1", "endgame"),
    AccuracyPosition("king_activation", "8/8/5k2/8/4P3/4K3/8/8 w - - 0 1", "endgame"),
    AccuracyPosition("lucena_bridge", "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 4 1", "endgame"),
    AccuracyPosition("free_queen_capture", "4k3/3q4/8/8/8/8/8/3Q2K1 w - - 0 1", "tactics"),
    AccuracyPosition("verified_knight_fork", "3qk2r/8/8/6N1/8/8/8/4K3 w - - 0 1", "tactics"),
    AccuracyPosition(
        "queenless_development",
        "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1",
        "positional",
    ),
)


def inversion_rate(scores_in_reported_order: list[int], tolerance_cp: int = 20) -> float:
    comparisons = 0
    inversions = 0
    for index, score in enumerate(scores_in_reported_order):
        for later_score in scores_in_reported_order[index + 1:]:
            comparisons += 1
            if later_score > score + tolerance_cp:
                inversions += 1
    return inversions / comparisons if comparisons else 0.0


def accuracy_gate(
    top3_rate: float,
    recall_rate: float,
    inversion: float,
    completion_rate: float,
    mean_loss_error_cp: float,
    mate_type_rate: float,
    only_move_precision: float,
    only_move_recall: float,
    loss_field_rate: float,
    max_position_loss_mae_cp: float,
    position_count: int,
    min_topic_top3_rate: float,
    min_topic_recall_rate: float,
) -> bool:
    """Strict release gate; ordinary benchmark runs may report without enforcing it."""
    return (
        position_count >= 20
        and top3_rate >= 0.9
        and recall_rate >= 0.9
        and min_topic_top3_rate >= 0.8
        and min_topic_recall_rate >= 0.8
        and inversion <= 0.15
        and completion_rate == 1.0
        and mean_loss_error_cp <= 100
        and mate_type_rate == 1.0
        and only_move_precision >= 0.95
        and only_move_recall >= 0.9
        and loss_field_rate == 1.0
        and max_position_loss_mae_cp <= 200
    )


def candidate_consistency(candidates: list[dict], forced_scores: list[int]) -> dict:
    if not candidates or not forced_scores:
        return {"loss_errors": [], "loss_fields_complete": False, "type_matches": False}
    candidate_best_score = max(forced_scores)
    oracle_best_is_mate = abs(candidate_best_score) >= 90_000
    loss_errors = []
    loss_fields_complete = True
    type_matches = True
    for item, forced_score in zip(candidates, forced_scores):
        oracle_is_mate = abs(forced_score) >= 90_000
        reported_is_mate = item.get("score_type") == "mate"
        # A shallow custom search may not see every distant forced mate, but it must
        # never label a centipawn oracle line as mate.
        type_matches = type_matches and (not reported_is_mate or oracle_is_mate)
        if oracle_best_is_mate or oracle_is_mate:
            continue
        reported_loss = item.get("loss_cp")
        if not isinstance(reported_loss, (int, float)):
            loss_fields_complete = False
            continue
        oracle_loss = max(0, candidate_best_score - forced_score)
        loss_errors.append(abs(reported_loss - oracle_loss))
    return {
        "loss_errors": loss_errors,
        "loss_fields_complete": loss_fields_complete,
        "type_matches": type_matches,
    }


def run(stockfish_path: str, nodes: int = 50_000) -> dict:
    results = []
    with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
        for position in POSITIONS:
            board = chess.Board(position.fen)
            oracle = engine.analyse(
                board,
                chess.engine.Limit(nodes=nodes),
                multipv=min(3, board.legal_moves.count()),
            )
            oracle_top = [item["pv"][0] for item in oracle if item.get("pv")]
            oracle_best = oracle_top[0]
            oracle_scores = [
                item["score"].pov(board.turn).score(mate_score=100_000) or 0
                for item in oracle
            ]

            base = chess_engine.get_analysis(board, depth=position.depth)
            teaching = chess_engine.get_teaching_analysis(
                board,
                base,
                candidate_count=position.candidate_count,
                depth=position.depth,
            )
            candidates = teaching.get("candidates") or []
            candidate_moves = [chess.Move.from_uci(item["move"]) for item in candidates]
            forced_scores = []
            for move in candidate_moves:
                forced = engine.analyse(
                    board,
                    chess.engine.Limit(nodes=nodes),
                    root_moves=[move],
                )
                forced_scores.append(
                    forced["score"].pov(board.turn).score(mate_score=100_000) or 0
                )

            reported_top = candidate_moves[0] if candidate_moves else None
            consistency = candidate_consistency(candidates, forced_scores)
            loss_errors = consistency["loss_errors"]
            oracle_gap = (
                max(0, oracle_scores[0] - oracle_scores[1])
                if len(oracle_scores) >= 2
                else 100_000
            )
            oracle_only_move = oracle_gap >= 150
            reported_only_move = teaching.get("criticality") == "only_move"
            oracle_top_is_mate = abs(oracle_scores[0]) >= 90_000
            reported_top_is_mate = bool(candidates and candidates[0].get("score_type") == "mate")
            mate_type_matches = consistency["type_matches"] and (
                not oracle_top_is_mate or reported_top_is_mate
            )
            results.append({
                "name": position.name,
                "topic": position.topic,
                "oracle_best": board.san(oracle_best),
                "oracle_top": [board.san(move) for move in oracle_top],
                "reported_top": board.san(reported_top) if reported_top else None,
                "top_in_oracle_top3": reported_top in oracle_top,
                "oracle_best_recalled": oracle_best in candidate_moves,
                "rank_inversion_rate": round(inversion_rate(forced_scores), 4),
                "candidate_loss_mae_cp": (
                    round(sum(loss_errors) / len(loss_errors), 1) if loss_errors else None
                ),
                "loss_errors_cp": loss_errors,
                "mate_type_matches": mate_type_matches,
                "loss_fields_complete": consistency["loss_fields_complete"],
                "oracle_only_move": oracle_only_move,
                "reported_criticality": teaching.get("criticality"),
                "only_move_matches": oracle_only_move == reported_only_move,
                "analysis_complete": teaching.get("analysis_complete"),
            })

    count = len(results)
    top3_rate = sum(item["top_in_oracle_top3"] for item in results) / count
    recall_rate = sum(item["oracle_best_recalled"] for item in results) / count
    average_inversion_rate = sum(item["rank_inversion_rate"] for item in results) / count
    completion_rate = sum(bool(item["analysis_complete"]) for item in results) / count
    all_loss_errors = [
        error for item in results for error in item["loss_errors_cp"]
    ]
    mean_loss_error_cp = sum(all_loss_errors) / len(all_loss_errors) if all_loss_errors else 0.0
    mate_type_rate = sum(item["mate_type_matches"] for item in results) / count
    only_move_true_positives = sum(
        item["oracle_only_move"] and item["reported_criticality"] == "only_move"
        for item in results
    )
    only_move_reported = sum(item["reported_criticality"] == "only_move" for item in results)
    only_move_oracle = sum(item["oracle_only_move"] for item in results)
    only_move_precision = (
        only_move_true_positives / only_move_reported if only_move_reported else 1.0
    )
    only_move_recall = (
        only_move_true_positives / only_move_oracle if only_move_oracle else 1.0
    )
    loss_field_rate = sum(item["loss_fields_complete"] for item in results) / count
    position_loss_maes = [
        item["candidate_loss_mae_cp"]
        for item in results
        if item["candidate_loss_mae_cp"] is not None
    ]
    max_position_loss_mae_cp = max(position_loss_maes, default=0.0)
    topic_metrics = {}
    for topic in sorted({item["topic"] for item in results}):
        topic_results = [item for item in results if item["topic"] == topic]
        topic_count = len(topic_results)
        topic_metrics[topic] = {
            "positions": topic_count,
            "top3_rate": round(
                sum(item["top_in_oracle_top3"] for item in topic_results) / topic_count,
                3,
            ),
            "recall_rate": round(
                sum(item["oracle_best_recalled"] for item in topic_results) / topic_count,
                3,
            ),
        }
    min_topic_top3_rate = min(
        (metrics["top3_rate"] for metrics in topic_metrics.values()), default=0.0
    )
    min_topic_recall_rate = min(
        (metrics["recall_rate"] for metrics in topic_metrics.values()), default=0.0
    )
    passed = accuracy_gate(
        top3_rate,
        recall_rate,
        average_inversion_rate,
        completion_rate,
        mean_loss_error_cp,
        mate_type_rate,
        only_move_precision,
        only_move_recall,
        loss_field_rate,
        max_position_loss_mae_cp,
        count,
        min_topic_top3_rate,
        min_topic_recall_rate,
    )
    return {
        "mode": "stockfish_accuracy",
        "stockfish": stockfish_path,
        "nodes": nodes,
        "positions": count,
        "top1_in_oracle_top3_rate": round(top3_rate, 3),
        "oracle_best_recall_rate": round(recall_rate, 3),
        "average_rank_inversion_rate": round(average_inversion_rate, 3),
        "analysis_completion_rate": round(completion_rate, 3),
        "mean_candidate_loss_error_cp": round(mean_loss_error_cp, 1),
        "mate_score_type_precision_rate": round(mate_type_rate, 3),
        "only_move_precision": round(only_move_precision, 3),
        "only_move_recall": round(only_move_recall, 3),
        "loss_field_completion_rate": round(loss_field_rate, 3),
        "max_position_loss_mae_cp": round(max_position_loss_mae_cp, 1),
        "by_topic": topic_metrics,
        "minimum_topic_top3_rate": min_topic_top3_rate,
        "minimum_topic_recall_rate": min_topic_recall_rate,
        "thresholds": {
            "minimum_positions": 20,
            "top3_rate": 0.9,
            "recall_rate": 0.9,
            "minimum_topic_top3_rate": 0.8,
            "minimum_topic_recall_rate": 0.8,
            "max_inversion_rate": 0.15,
            "completion_rate": 1.0,
            "max_mean_loss_error_cp": 100,
            "mate_type_rate": 1.0,
            "only_move_precision": 0.95,
            "only_move_recall": 0.9,
            "loss_field_rate": 1.0,
            "max_position_loss_mae_cp": 200,
        },
        "release_ready": passed,
        "passed": passed,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stockfish")
    parser.add_argument("--nodes", type=int, default=50_000)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--require-release-ready",
        action="store_true",
        help="Exit non-zero when the strict release gate is not satisfied.",
    )
    args = parser.parse_args()
    stockfish_path = find_stockfish(args.stockfish)
    if not stockfish_path:
        parser.error("Stockfish was not found; pass --stockfish or set STOCKFISH_PATH")
    report = run(stockfish_path, nodes=args.nodes)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"Teaching accuracy: top3={report['top1_in_oracle_top3_rate']:.0%} "
            f"recall={report['oracle_best_recall_rate']:.0%} "
            f"inversions={report['average_rank_inversion_rate']:.1%}"
        )
        for item in report["results"]:
            print(
                f"  {item['name']}: reported={item['reported_top']} "
                f"oracle={item['oracle_best']} top3={item['top_in_oracle_top3']} "
                f"recall={item['oracle_best_recalled']} inversions={item['rank_inversion_rate']:.1%}"
            )
    return 1 if args.require_release_ready and not report["release_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
