"""Module registry + dependency-aware ordering."""

from __future__ import annotations

from typing import Dict, List, Type

from .base import AnalysisModule

_REGISTRY: Dict[str, Type[AnalysisModule]] = {}


def register_module(cls: Type[AnalysisModule]) -> Type[AnalysisModule]:
    name = getattr(cls, "name", None)
    if not name or name == "base":
        raise ValueError(f"Module {cls!r} must set a unique 'name'")
    _REGISTRY[name] = cls
    return cls


def get_module(name: str) -> Type[AnalysisModule]:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown module '{name}'. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def available_modules() -> List[str]:
    return sorted(_REGISTRY)


def order_modules(names: List[str]) -> List[str]:
    """Topologically order ``names`` so a module's ``requires`` come first.

    Only dependencies that are themselves in ``names`` are inserted; missing ones
    are ignored (the module may degrade gracefully).
    """
    ordered: List[str] = []
    seen = set()
    visiting = set()

    def visit(name: str):
        if name in seen:
            return
        if name in visiting:
            raise ValueError(f"Circular module dependency at '{name}'")
        visiting.add(name)
        for dep in get_module(name).requires:
            if dep in names:
                visit(dep)
        visiting.discard(name)
        seen.add(name)
        ordered.append(name)

    for n in names:
        visit(n)
    return ordered
