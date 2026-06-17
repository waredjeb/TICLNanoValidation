"""Configuration: typed dataclasses + YAML loader."""

from .schema import (
    Axis,
    BinningConfig,
    MatchingConfig,
    OutputConfig,
    RunConfig,
    SchemaConfig,
    SimCollection,
)
from .loader import load_config

__all__ = [
    "Axis",
    "BinningConfig",
    "MatchingConfig",
    "OutputConfig",
    "RunConfig",
    "SchemaConfig",
    "SimCollection",
    "load_config",
]
