"""Association-score matching: quality = link score (lower is better).

Best match = lowest score; a match passes if the score is below the configured
threshold (default 0.2 for sim2reco, 0.6 for reco2sim).
"""

from __future__ import annotations

from .base import MatchingStrategy
from .registry import register_strategy


@register_strategy
class ScoreStrategy(MatchingStrategy):
    name = "score"

    def quality_expr(self) -> str:
        return "score"

    def worst_quality(self) -> str:
        return "9999.f"

    def is_better_expr(self) -> str:
        return "q < best"

    def passes_expr(self, threshold: float) -> str:
        return f"best_q < {threshold}f"
