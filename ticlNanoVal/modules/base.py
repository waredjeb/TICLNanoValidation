"""AnalysisModule interface + per-run context.

Modules are collection-agnostic: the pipeline calls them once per reco collection.
They reference branches only through the :class:`CollectionSchema` and read matching
results only through the standardized :class:`MatchColumns` in the context, so the
same module runs unchanged on HLT and offline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import ROOT

from ..config.schema import RunConfig
from ..data.collections import CollectionSchema
from ..matching.base import MatchColumns


@dataclass
class RunContext:
    """Everything a module needs about the current file beyond the RDataFrame."""

    schema: CollectionSchema
    config: RunConfig
    columns: Set[str]
    # (direction, sim_key, reco_key) -> MatchColumns
    match_map: Dict[Tuple[str, str, str], MatchColumns] = field(default_factory=dict)

    def sims_for(self, reco_key: str, direction: str) -> List[str]:
        """Sim keys with an existing matched association to ``reco_key``."""
        return [
            sim
            for (d, sim, reco) in self.match_map
            if d == direction and reco == reco_key
        ]

    def match(
        self, reco_key: str, sim_key: str, direction: str
    ) -> Optional[MatchColumns]:
        return self.match_map.get((direction, sim_key, reco_key))


# A booking is a name -> lazy RResultPtr map.
Bookings = Dict[str, "ROOT.RDF.RResultPtr"]


class AnalysisModule(ABC):
    """Base class for analysis modules."""

    name: str = "base"
    requires: List[str] = []  # other module names whose columns this one needs
    supports_sim: bool = False  # opt-in: also run book_sim/plot_sim over sim collections

    def __init__(self, config: RunConfig, schema: CollectionSchema):
        self.config = config
        self.schema = schema
        self.binning = config.binning
        self.plotter = None  # injected by the pipeline before plot() is called

    def define(self, rdf: "ROOT.RDataFrame", ctx: RunContext) -> "ROOT.RDataFrame":
        """Optionally define extra columns once (all collections). Default: no-op."""
        return rdf

    @abstractmethod
    def book(
        self, rdf: "ROOT.RDataFrame", ctx: RunContext, reco_key: str
    ) -> Bookings:
        """Return lazy RResultPtr histograms for one reco collection."""

    def book_sim(self, rdf: "ROOT.RDataFrame", ctx: RunContext, sim_key: str) -> Bookings:
        """Return lazy RResultPtr histograms for one sim collection.

        Only called when ``supports_sim`` is True. Default: none.
        """
        return {}

    def metrics(
        self, results: Dict[str, object], ctx: RunContext, reco_key: str
    ) -> Dict[str, float]:
        """Compute scalar metrics from realized histograms. Default: none."""
        return {}

    def metrics_sim(
        self, results: Dict[str, object], ctx: RunContext, sim_key: str
    ) -> Dict[str, float]:
        """Compute scalar metrics for one sim collection. Default: none."""
        return {}

    @abstractmethod
    def plot(
        self,
        results: Dict[str, object],
        metrics: Dict[str, float],
        output_dir: Path,
        ctx: RunContext,
        reco_key: str,
    ):
        """Render plots for one reco collection into ``output_dir``."""

    def plot_sim(
        self,
        results: Dict[str, object],
        metrics: Dict[str, float],
        output_dir: Path,
        ctx: RunContext,
        sim_key: str,
    ):
        """Render plots for one sim collection into ``output_dir``. Default: no-op."""
