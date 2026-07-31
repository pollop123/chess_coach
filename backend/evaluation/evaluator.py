"""Composable position evaluator with a stable white-centric score contract."""

from types import MappingProxyType
from typing import Mapping

import chess

from .endgame import mop_up_score
from .king_activity import king_activity_score
from .king_safety import (
    contextual_pawn_shelter_score,
    graded_king_safety_score,
    king_safety_score,
)
from .material import material_and_piece_square_scores
from .models import EvaluationResult
from .pawn_structure import pawn_structure_score
from .phase import ENDGAME_LABEL_THRESHOLD, endgame_weight_percent
from .piece_activity import piece_activity_score
from .rook_activity import rook_activity_score
from .terminal import terminal_score


CALIBRATED_FEATURE_WEIGHTS = MappingProxyType(
    {
        "pawn_structure": 0,
        "piece_activity": 0,
        "rook_activity": 0,
        "king_activity": 100,
        "king_safety_blend": 0,
        "quiet_pawn_shelter": 0,
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

    def score_nonterminal(self, board: chess.Board, ply_from_root: int = 0) -> int:
        """Score a position the caller has already proven is non-terminal."""
        score, _, _, _ = self._evaluate(
            board, ply_from_root, check_terminal=False
        )
        return score

    def score_quiet_nonterminal(
        self, board: chess.Board, ply_from_root: int = 0
    ) -> int:
        """Score a proven non-terminal, non-check leaf with contextual knowledge."""
        score, _, _, _ = self._evaluate(
            board,
            ply_from_root,
            check_terminal=False,
            quiet_context=True,
        )
        return score

    def _evaluate(
        self,
        board: chess.Board,
        ply_from_root: int,
        *,
        check_terminal: bool = True,
        quiet_context: bool = False,
    ) -> tuple[int, str, dict[str, int], bool]:
        terminal = terminal_score(board, ply_from_root) if check_terminal else None
        if terminal is not None:
            return terminal, "terminal", {"terminal": terminal}, True

        endgame_weight = endgame_weight_percent(board)
        endgame = endgame_weight >= ENDGAME_LABEL_THRESHOLD
        feature_phase_weights = self._feature_phase_weights(board, endgame_weight)
        material, piece_square = material_and_piece_square_scores(
            board, endgame_weight
        )
        legacy_king_safety = king_safety_score(board, endgame_weight)
        king_safety_blend = round(
            self.feature_weights["king_safety_blend"]
            * feature_phase_weights["king_safety_blend"]
            / 100
        )
        if king_safety_blend == 0:
            king_safety = legacy_king_safety
        else:
            graded_king_safety = graded_king_safety_score(board, endgame_weight)
            king_safety = round(
                (
                    legacy_king_safety * (100 - king_safety_blend)
                    + graded_king_safety * king_safety_blend
                )
                / 100
            )
        components = {
            "material": material,
            "piece_square": piece_square,
            "king_safety": king_safety,
        }
        legacy_base_score = sum(components.values())
        components.update(
            {
                "pawn_structure": self._weighted_feature(
                    "pawn_structure",
                    pawn_structure_score,
                    feature_phase_weights["pawn_structure"],
                    board,
                ),
                "piece_activity": self._weighted_feature(
                    "piece_activity",
                    piece_activity_score,
                    feature_phase_weights["piece_activity"],
                    board,
                ),
                "rook_activity": self._weighted_feature(
                    "rook_activity",
                    rook_activity_score,
                    feature_phase_weights["rook_activity"],
                    board,
                ),
                "king_activity": self._weighted_feature(
                    "king_activity",
                    king_activity_score,
                    feature_phase_weights["king_activity"],
                    board,
                    True,
                ),
            }
        )
        components["endgame_mop_up"] = mop_up_score(
            board, legacy_base_score, endgame_weight
        )
        if quiet_context and self.feature_weights["quiet_pawn_shelter"]:
            components["quiet_pawn_shelter"] = round(
                contextual_pawn_shelter_score(board, endgame_weight)
                * self.feature_weights["quiet_pawn_shelter"]
                / 100
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

    @staticmethod
    def _feature_phase_weights(
        board: chess.Board, endgame_weight: int
    ) -> dict[str, int]:
        """Give each strategic feature the phase profile it actually needs.

        Pawn structure matters throughout the game. Piece activity is strongest
        before heavy material disappears, rook activity grows as lines open, and
        king activity belongs specifically to the endgame.
        """
        half_endgame = round(endgame_weight / 2)
        starting_minors = (
            (chess.B1, chess.KNIGHT, chess.WHITE),
            (chess.G1, chess.KNIGHT, chess.WHITE),
            (chess.C1, chess.BISHOP, chess.WHITE),
            (chess.F1, chess.BISHOP, chess.WHITE),
            (chess.B8, chess.KNIGHT, chess.BLACK),
            (chess.G8, chess.KNIGHT, chess.BLACK),
            (chess.C8, chess.BISHOP, chess.BLACK),
            (chess.F8, chess.BISHOP, chess.BLACK),
        )
        undeveloped = sum(
            board.piece_at(square) == chess.Piece(piece_type, color)
            for square, piece_type, color in starting_minors
        )
        development_weight = round((len(starting_minors) - undeveloped) * 100 / 8)
        piece_activity_weight = round(
            development_weight * (100 - half_endgame) / 100
        )
        king_safety_development = max(0, (development_weight - 50) * 2)
        king_safety_weight = (
            0
            if endgame_weight >= 75
            else round(king_safety_development * (100 - endgame_weight) / 100)
        )
        return {
            "pawn_structure": 100,
            "piece_activity": piece_activity_weight,
            "rook_activity": 50 + half_endgame,
            "king_activity": endgame_weight,
            "king_safety_blend": king_safety_weight,
        }

    def _weighted_feature(
        self, name, function, phase_weight: int, *function_arguments
    ) -> int:
        feature_weight = self.feature_weights[name]
        if phase_weight == 0 or feature_weight == 0:
            return 0
        calibrated = round(function(*function_arguments) * feature_weight / 100)
        return self._taper(calibrated, phase_weight)


DEFAULT_EVALUATOR = PositionEvaluator()
