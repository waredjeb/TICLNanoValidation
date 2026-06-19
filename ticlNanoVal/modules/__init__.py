"""Analysis modules: pluggable units that consume the RDataFrame + match columns."""

from .base import AnalysisModule, RunContext
from .registry import get_module, register_module, available_modules, order_modules

# Import built-ins so they self-register.
from . import distributions as _distributions  # noqa: F401
from . import efficiency as _efficiency  # noqa: F401

__all__ = [
    "AnalysisModule",
    "RunContext",
    "get_module",
    "register_module",
    "available_modules",
    "order_modules",
]
