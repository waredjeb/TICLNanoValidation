"""Load configuration from one or more YAML files, with deep-merge + overrides.

Usage::

    cfg = load_config(["configs/base.yaml", "configs/offline.yaml"],
                      overrides={"run": {"threads": 8}})

Later files win over earlier ones; ``overrides`` (e.g. from the CLI or a LAW task)
win over everything. This lets a global ``base.yaml`` carry binning/thresholds while
``offline.yaml`` / ``hlt.yaml`` carry only the collection schema.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Iterable, Optional, Union

import yaml

from .schema import RunConfig

PathLike = Union[str, Path]


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into ``base`` (returns a new dict)."""
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_dict(paths: Iterable[PathLike], overrides: Optional[dict] = None) -> dict:
    """Merge YAML files (in order) plus an overrides dict into one plain dict."""
    merged: dict = {}
    for path in paths:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config {path} must be a mapping at top level")
        merged = _deep_merge(merged, data)
    if overrides:
        merged = _deep_merge(merged, overrides)
    return merged


def load_config(
    paths: Union[PathLike, Iterable[PathLike]],
    overrides: Optional[dict] = None,
) -> RunConfig:
    """Build a :class:`RunConfig` from YAML file(s) and optional overrides."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    return RunConfig.from_dict(load_dict(paths, overrides))
