"""Composable position evaluator with a stable white-centric score contract."""

import chess

from .endgame import mop_up_score
from .king_safety import king_safety_score
from .material import material_and_piece_square_scores
from .models import EvaluationResult
from .phase import is_endgame
from .terminal import terminal_score


class PositionEvaluator:
    """Evaluate positions while exposing the score's individual components."""

    def evaluate(self, board: chess.Board, ply_from_root: int = 0) -> EvaluationResult:
        score, phase, components, is_terminal = self._evaluate(
            board, ply_from_root
        )
        return EvaluationResult.build(
            score=score,
            phase=phase,
            components=components,
            terminal=is_terminal,
        )

    def score(self, board: chess.Board, ply_from_root: int = 0) -> int:
        score, _, _, _ = self._evaluate(board, ply_from_root)
        return score

    def _evaluate(
        self, board: chess.Board, ply_from_root: int
    ) -> tuple[int, str, dict[str, int], bool]:
        terminal = terminal_score(board, ply_from_root)
        if terminal is not None:
            return terminal, "terminal", {"terminal": terminal}, True

        endgame = is_endgame(board)
        material, piece_square = material_and_piece_square_scores(board, endgame)
        components = {
            "material": material,
            "piece_square": piece_square,
            "king_safety": king_safety_score(board, endgame),
        }
        base_score = sum(components.values())
        components["endgame_mop_up"] = mop_up_score(board, base_score, endgame)
        score = sum(components.values())

        # This preserves the old public behavior during modularization. Repetition
        # policy can move to the search layer in a separately benchmarked change.
        if board.is_repetition(2):
            if score > 500:
                repetition_score = -1000
            elif score < -500:
                repetition_score = 1000
            else:
                repetition_score = 0
            components["repetition_policy"] = repetition_score - score
            score = repetition_score

        return score, "endgame" if endgame else "middlegame", components, False


DEFAULT_EVALUATOR = PositionEvaluator()
