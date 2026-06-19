"""Typed configuration objects.

These are plain dataclasses that mirror the YAML structure. They are built by
:func:`ticlNanoVal.config.loader.load_config`, which deep-merges one or more YAML
files (e.g. ``base.yaml`` + ``offline.yaml``) and applies CLI overrides.

Nothing here imports ROOT or law, so the config can be inspected/tested cheaply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Binning
# --------------------------------------------------------------------------- #
@dataclass
class Axis:
    """A single histogram axis."""

    bins: int
    min: float
    max: float

    @classmethod
    def from_dict(cls, d: dict) -> "Axis":
        return cls(bins=int(d["bins"]), min=float(d["min"]), max=float(d["max"]))


@dataclass
class BinningConfig:
    """Named axes, looked up by name from modules (e.g. ``binning.axis('eta')``)."""

    axes: Dict[str, Axis] = field(default_factory=dict)

    def axis(self, name: str) -> Axis:
        if name not in self.axes:
            raise KeyError(
                f"No binning axis named '{name}'. Available: {sorted(self.axes)}"
            )
        return self.axes[name]

    @classmethod
    def from_dict(cls, d: dict) -> "BinningConfig":
        return cls(axes={k: Axis.from_dict(v) for k, v in (d or {}).items()})


# --------------------------------------------------------------------------- #
# Matching
# --------------------------------------------------------------------------- #
@dataclass
class MatchingConfig:
    """Which matching strategy to use and its per-direction thresholds."""

    strategy: str = "shared_energy"
    # thresholds per strategy: {strategy_name: {"sim2reco": x, "reco2sim": y}}
    thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # which sim collections (schema sim keys) to match against; empty == all
    sim_keys: List[str] = field(default_factory=list)

    def threshold(self, direction: str) -> float:
        """Threshold for the active strategy in the given direction."""
        try:
            return float(self.thresholds[self.strategy][direction])
        except KeyError as exc:
            raise KeyError(
                f"No threshold for strategy '{self.strategy}' direction '{direction}'. "
                f"Configured: {self.thresholds}"
            ) from exc

    @classmethod
    def from_dict(cls, d: dict) -> "MatchingConfig":
        d = d or {}
        return cls(
            strategy=d.get("strategy", "shared_energy"),
            thresholds={k: dict(v) for k, v in (d.get("thresholds") or {}).items()},
            sim_keys=list(d.get("sim_keys") or []),
        )


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
@dataclass
class OutputConfig:
    formats: List[str] = field(default_factory=lambda: ["png"])
    dpi: int = 150
    figure_width: int = 10
    figure_height: int = 8
    save_summary_json: bool = True

    @property
    def save_png(self) -> bool:
        return "png" in self.formats

    @property
    def save_pdf(self) -> bool:
        return "pdf" in self.formats

    @classmethod
    def from_dict(cls, d: dict) -> "OutputConfig":
        d = d or {}
        return cls(
            formats=list(d.get("formats") or ["png"]),
            dpi=int(d.get("dpi", 150)),
            figure_width=int(d.get("figure_width", 10)),
            figure_height=int(d.get("figure_height", 8)),
            save_summary_json=bool(d.get("save_summary_json", True)),
        )


# --------------------------------------------------------------------------- #
# Collection schema (HLT vs offline names live entirely in config)
# --------------------------------------------------------------------------- #
@dataclass
class SimCollection:
    """A simulated reference collection.

    ``token`` is the short name used to build association branch names
    (e.g. ``SimCP``); ``tracksters`` is the physical collection holding the
    kinematics (e.g. ``ticlSimTrackstersfromCPs``). They differ, which is why a
    naive prefix rule cannot work.
    """

    key: str
    token: str
    tracksters: str


@dataclass
class SchemaConfig:
    """Maps logical collection keys to physical branch names + naming templates."""

    name: str = "offline"
    reco: Dict[str, str] = field(default_factory=dict)
    sim: Dict[str, SimCollection] = field(default_factory=dict)
    # field templates, keyed by logical field name; "{coll}" is substituted
    fields: Dict[str, str] = field(default_factory=dict)
    # association head templates; "{sim}" and "{reco}" are substituted
    assoc_sim2reco: str = "{sim}2{reco}ByHits"
    assoc_reco2sim: str = "Reco{reco}2{sim}ByHits"

    @classmethod
    def from_dict(cls, d: dict) -> "SchemaConfig":
        d = d or {}
        sim = {
            key: SimCollection(key=key, token=v["token"], tracksters=v["tracksters"])
            for key, v in (d.get("sim") or {}).items()
        }
        assoc = d.get("associations") or {}
        return cls(
            name=d.get("name", "offline"),
            reco=dict(d.get("reco") or {}),
            sim=sim,
            fields=dict(d.get("fields") or {}),
            assoc_sim2reco=assoc.get("sim2reco", "{sim}2{reco}ByHits"),
            assoc_reco2sim=assoc.get("reco2sim", "Reco{reco}2{sim}ByHits"),
        )


# --------------------------------------------------------------------------- #
# Top-level run config
# --------------------------------------------------------------------------- #
@dataclass
class RunConfig:
    """The fully-resolved configuration for a single pipeline run."""

    schema: SchemaConfig = field(default_factory=SchemaConfig)
    binning: BinningConfig = field(default_factory=BinningConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    modules: List[str] = field(default_factory=lambda: ["distributions"])
    reco_keys: List[str] = field(default_factory=list)  # empty == all in schema
    tree_name: str = "Events"
    enable_mt: bool = True
    threads: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        d = d or {}
        run = d.get("run") or {}
        return cls(
            schema=SchemaConfig.from_dict(d.get("schema")),
            binning=BinningConfig.from_dict(d.get("binning")),
            matching=MatchingConfig.from_dict(d.get("matching")),
            output=OutputConfig.from_dict(d.get("output")),
            modules=list(run.get("modules") or ["distributions"]),
            reco_keys=list(run.get("reco_keys") or []),
            tree_name=run.get("tree_name", "Events"),
            enable_mt=bool(run.get("enable_mt", True)),
            threads=run.get("threads"),
        )
