"""Registry mapping strategy names (from YAML) to MatchingStrategy classes."""

from __future__ import annotations

from typing import Dict, List, Type

from .base import MatchingStrategy

_REGISTRY: Dict[str, Type[MatchingStrategy]] = {}


def register_strategy(cls: Type[MatchingStrategy]) -> Type[MatchingStrategy]:
    """Class decorator that registers a strategy by its ``name`` attribute."""
    name = getattr(cls, "name", None)
    if not name or name == "base":
        raise ValueError(f"Strategy {cls!r} must set a unique 'name'")
    _REGISTRY[name] = cls
    return cls


def get_strategy(name: str) -> Type[MatchingStrategy]:
    if name not in _REGISTRY:
        raise KeyError(
            f"Unknown matching strategy '{name}'. Available: {sorted(_REGISTRY)}"
        )
    return _REGISTRY[name]


def available_strategies() -> List[str]:
    return sorted(_REGISTRY)
