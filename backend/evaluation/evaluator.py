"""Composable position evaluator with a stable white-centric score contract."""

from types import MappingProxyType
from typing import Mapping

import chess

from .endgame import mop_up_score
from .king_activity import king_activity_score
from .king_safety import king_safety_score
from .material import material_and_piece_square_scores
from .models import EvaluationResult
from .pawn_structure import pawn_structure_score
from .phase import is_endgame, strategic_weight_percent
from .piece_activity import piece_activity_score
from .rook_activity import rook_activity_score
from .terminal import terminal_score


CALIBRATED_FEATURE_WEIGHTS = MappingProxyType(
    {
        "pawn_structure": 0,
        "piece_activity": 0,
        "rook_activity": 0,
        "king_activity": 100,
    }
)


class PositionEvaluator:
    """Evaluate positions while exposing the score's individual components."""

    def __init__(self, feature_weights: Mapping[str, int] | None = None):
        weights = dict(CALIBRATED_FEATURE_WEIGHTS)
        if feature_weights is not None:
            weights.update(feature_weights)
        self.feature_weights = MappingProxyType(weights)

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
        strategic_weight = strategic_weight_percent(board)
        material, piece_square = material_and_piece_square_scores(board, endgame)
        components = {
            "material": material,
            "piece_square": piece_square,
            "king_safety": king_safety_score(board, endgame),
        }
        legacy_base_score = sum(components.values())
        components.update(
            {
                "pawn_structure": self._weighted_feature(
                    "pawn_structure", pawn_structure_score, strategic_weight, board
                ),
                "piece_activity": self._weighted_feature(
                    "piece_activity", piece_activity_score, strategic_weight, board
                ),
                "rook_activity": self._weighted_feature(
                    "rook_activity", rook_activity_score, strategic_weight, board
                ),
                "king_activity": self._weighted_feature(
                    "king_activity",
                    king_activity_score,
                    strategic_weight,
                    board,
                    endgame,
                ),
            }
        )
        components["endgame_mop_up"] = mop_up_score(
            board, legacy_base_score, endgame
        )
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

    @staticmethod
    def _taper(score: int, weight_percent: int) -> int:
        return round(score * weight_percent / 100)

    def _weighted_feature(
        self, name, function, phase_weight: int, *function_arguments
    ) -> int:
        feature_weight = self.feature_weights[name]
        if phase_weight == 0 or feature_weight == 0:
            return 0
        calibrated = round(function(*function_arguments) * feature_weight / 100)
        return self._taper(calibrated, phase_weight)


DEFAULT_EVALUATOR = PositionEvaluator()
