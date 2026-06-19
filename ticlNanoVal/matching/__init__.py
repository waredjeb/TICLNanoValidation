"""Pluggable Sim<->Reco matching with a standardized output schema.

Every strategy, regardless of algorithm (shared energy, score, dR, association
map, ...), emits the *same* columns (see :class:`MatchColumns`), so downstream
modules consume matching results without knowing which strategy ran.
"""

from .base import MatchColumns, MatchingStrategy, apply_matching
from .registry import get_strategy, register_strategy, available_strategies

# Import built-in strategies so they register themselves.
from . import shared_energy as _shared_energy  # noqa: F401
from . import score as _score  # noqa: F401

__all__ = [
    "MatchColumns",
    "MatchingStrategy",
    "apply_matching",
    "get_strategy",
    "register_strategy",
    "available_strategies",
]
