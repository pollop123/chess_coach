import argparse
import json
from dataclasses import dataclass

import chess

import chess_engine


@dataclass(frozen=True)
class TeachingPosition:
    name: str
    topic: str
    fen: str
    expected_best_san: tuple[str, ...]
    expected_themes: tuple[str, ...] = ()
    expected_warnings: tuple[str, ...] = ()
    expected_criticality: tuple[str, ...] = ("normal", "sharp", "only_move")
    candidate_count: int = 8
    depth: int = 2
    note: str = ""


POSITIONS = (
    TeachingPosition(
        name="opening_development",
        topic="opening",
        fen=chess.STARTING_FEN,
        expected_best_san=("Nf3",),
        expected_themes=("opening_principle", "development"),
        note="Teaching output should recognize normal development in the opening.",
    ),
    TeachingPosition(
        name="opening_center_control",
        topic="opening",
        fen=chess.STARTING_FEN,
        expected_best_san=("e4",),
        expected_themes=("opening_principle", "center_control"),
        note="The benchmark documents whether a central first move is explainable.",
    ),
    TeachingPosition(
        name="scholar_mate_finish",
        topic="tactics",
        fen="r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        expected_best_san=("Qxf7#",),
        expected_themes=("tactics", "only_move"),
        expected_criticality=("only_move",),
        note="Mate-in-one should be marked as a critical tactical position.",
    ),
    TeachingPosition(
        name="two_knights_pressure",
        topic="tactics",
        fen="r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
        expected_best_san=("Qf3", "d4", "Nxf7"),
        expected_themes=("tactics",),
        note="A pressure position should produce tactical teaching evidence.",
    ),
    TeachingPosition(
        name="queen_mate_net",
        topic="endgame",
        fen="7k/8/5KQ1/8/8/8/8/8 w - - 0 1",
        expected_best_san=("Qg7#",),
        expected_themes=("endgame", "tactics"),
        expected_criticality=("only_move", "sharp"),
        note="Queen and king mate should stay clearly tactical and endgame-oriented.",
    ),
    TeachingPosition(
        name="pawn_promotion",
        topic="endgame",
        fen="8/4P3/4K3/8/8/8/8/4k3 w - - 0 1",
        expected_best_san=("e8=Q", "e8=R"),
        expected_themes=("endgame", "tactics"),
        note="Promotion should be surfaced as an endgame conversion theme.",
    ),
    TeachingPosition(
        name="queen_hang_warning",
        topic="mistake_warning",
        fen="7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1",
        expected_best_san=("Qh3", "Qe5+", "Qh4+"),
        expected_themes=("endgame",),
        expected_warnings=("hangs_major_piece", "large_eval_drop"),
        expected_criticality=("sharp", "only_move"),
        candidate_count=40,
        depth=1,
        note="Candidate comparison should explicitly catch Qxh7+ losing the queen.",
    ),
    TeachingPosition(
        name="rook_endgame_activity",
        topic="endgame",
        fen="8/5pk1/6p1/3R4/7P/6P1/5PK1/r7 w - - 0 1",
        expected_best_san=("Rd7", "Rb5", "Rc5", "h5"),
        expected_themes=("endgame",),
        note="Rook endgame positions should at least be classified as endgames.",
    ),
)

POSITIONS_BY_NAME = {position.name: position for position in POSITIONS}


def _warning_set(teaching_analysis):
    warnings = set(teaching_analysis.get("mistake_warnings") or [])
    for candidate in teaching_analysis.get("candidates") or []:
        warnings.update(candidate.get("warnings") or [])
    return warnings


def run_position(position: TeachingPosition) -> dict:
    board = chess.Board(position.fen)
    base_analysis = chess_engine.get_analysis(board, depth=position.depth)
    teaching = chess_engine.get_teaching_analysis(
        board,
        base_analysis,
        candidate_count=position.candidate_count,
        depth=position.depth,
    )

    best = teaching["candidates"][0] if teaching["candidates"] else {}
    position_themes = set(teaching.get("position_themes") or [])
    warnings_found = _warning_set(teaching)
    expected_themes = set(position.expected_themes)
    expected_warnings = set(position.expected_warnings)
    matched_best = best.get("san") in position.expected_best_san
    matched_themes = expected_themes.issubset(position_themes)
    matched_warnings = expected_warnings.issubset(warnings_found)
    matched_criticality = teaching.get("criticality") in position.expected_criticality
    candidates = teaching.get("candidates") or []
    legal_sans = {board.san(move) for move in board.legal_moves}
    ranks = [item.get("rank") for item in candidates]
    complete_scores = [item.get("score_status") == "complete" for item in candidates]
    structure_valid = bool(candidates) and all(
        item.get("san") in legal_sans for item in candidates
    ) and ranks == list(range(1, len(candidates) + 1)) and all(complete_scores)
    structure_valid = structure_valid and bool(teaching.get("analysis_complete"))
    structure_valid = structure_valid and (
        teaching.get("evaluated_candidate_count") == teaching.get("requested_candidate_count")
    )
    if candidates and candidates[0].get("score_type") == "centipawn":
        structure_valid = structure_valid and candidates[0].get("loss_cp") == 0

    return {
        "name": position.name,
        "topic": position.topic,
        "best_san": best.get("san"),
        "expected_best_san": list(position.expected_best_san),
        "matched_best": matched_best,
        "criticality": teaching.get("criticality"),
        "expected_criticality": list(position.expected_criticality),
        "matched_criticality": matched_criticality,
        "position_themes": sorted(position_themes),
        "expected_themes": sorted(expected_themes),
        "matched_themes": matched_themes,
        "warnings_found": sorted(warnings_found),
        "expected_warnings": sorted(expected_warnings),
        "matched_warnings": matched_warnings,
        "candidate_count": len(teaching.get("candidates") or []),
        "structure_valid": structure_valid,
        "passed": structure_valid,
        "note": position.note,
    }


def run(positions=POSITIONS) -> dict:
    results = [run_position(position) for position in positions]
    failures = [item for item in results if not item["passed"]]
    by_topic = {}
    for item in results:
        topic = item["topic"]
        if topic not in by_topic:
            by_topic[topic] = {"positions": 0, "passed": 0}
        by_topic[topic]["positions"] += 1
        by_topic[topic]["passed"] += int(item["passed"])

    for topic_result in by_topic.values():
        topic_result["pass_rate"] = round(topic_result["passed"] / topic_result["positions"], 3)

    return {
        "mode": "structure",
        "positions": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "pass_rate": round((len(results) - len(failures)) / len(results), 3),
        "by_topic": by_topic,
        "failures": failures,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Evaluate structured teaching-analysis output on fixed chess positions.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report = run()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(
        f"Teaching benchmark: {report['passed']}/{report['positions']} passed "
        f"({report['pass_rate']:.0%})"
    )
    for item in report["results"]:
        mark = "OK" if item["passed"] else "MISS"
        print(
            f"  [{mark}] {item['topic']}/{item['name']}: "
            f"best={item['best_san']} expected={','.join(item['expected_best_san'])} "
            f"criticality={item['criticality']} themes={','.join(item['position_themes'])} "
            f"warnings={','.join(item['warnings_found']) or 'none'}"
        )


if __name__ == "__main__":
    main()
