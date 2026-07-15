"""Value objects returned by the position evaluator."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class EvaluationResult:
    """A white-centric score together with its explainable components."""

    score: int
    phase: str
    components: Mapping[str, int]
    terminal: bool = False

    @classmethod
    def build(
        cls,
        *,
        score: int,
        phase: str,
        components: dict[str, int],
        terminal: bool = False,
    ) -> "EvaluationResult":
        return cls(
            score=score,
            phase=phase,
            components=MappingProxyType(dict(components)),
            terminal=terminal,
        )
