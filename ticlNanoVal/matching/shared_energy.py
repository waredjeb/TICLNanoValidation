"""Shared-energy-fraction matching: quality = sharedEnergy / source raw energy.

Best match = highest fraction; a match passes if the fraction exceeds the
configured threshold (default 0.5).
"""

from __future__ import annotations

from .base import MatchingStrategy
from .registry import register_strategy


@register_strategy
class SharedEnergyStrategy(MatchingStrategy):
    name = "shared_energy"

    def quality_expr(self) -> str:
        return "(denom > 0.f) ? (shared / denom) : 0.f"

    def worst_quality(self) -> str:
        return "-1.f"

    def is_better_expr(self) -> str:
        return "q > best"

    def passes_expr(self, threshold: float) -> str:
        return f"best_q > {threshold}f"
