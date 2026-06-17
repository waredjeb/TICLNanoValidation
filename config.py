"""Configuration classes for the validation framework."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class BinningConfig:
    """Configuration for histogram binning."""

    # Eta binning
    eta_bins: int = 50
    eta_min: float = -3.5
    eta_max: float = 3.5

    # Phi binning
    phi_bins: int = 50
    phi_min: float = -3.15
    phi_max: float = 3.15

    # Energy binning
    energy_bins: int = 100
    energy_min: float = 0.0
    energy_max: float = 200.0

    # pT binning
    pt_bins: int = 100
    pt_min: float = 0.0
    pt_max: float = 100.0

    # Resolution binning
    resolution_bins: int = 100
    resolution_min: float = -2.0
    resolution_max: float = 2.0

    # Response binning
    response_bins: int = 100
    response_min: float = 0.0
    response_max: float = 3.0


@dataclass
class MatchingConfig:
    """Configuration for Sim-Reco matching."""

    # Matching method: "shared_energy" or "score"
    method: str = "shared_energy"

    # SharedEnergyFraction thresholds
    sim2reco_sef_threshold: float = 0.5
    reco2sim_sef_threshold: float = 0.5

    # Score thresholds
    sim2reco_score_threshold: float = 0.2
    reco2sim_score_threshold: float = 0.6

    # Sim collections to use for matching
    sim_collections: List[str] = field(default_factory=lambda: ["SimCP", "SimSC"])


@dataclass
class CollectionConfig:
    """Configuration for which collections to analyze."""

    # Default collections to analyze
    trackster_collections: List[str] = field(default_factory=lambda: [
        "ticlTrackstersCLUE3DHigh",
        "ticlTracksterLinks",
        "ticlTracksterLinksSuperclusteringDNN",
    ])

    candidate_collections: List[str] = field(default_factory=lambda: [
        "ticlCandidate",
    ])

    # HLT collections (with hlt prefix)
    hlt_trackster_collections: List[str] = field(default_factory=lambda: [
        "hltTiclTrackstersCLUE3DHigh",
        "hltTiclTracksterLinks",
        "hltTiclTracksterLinksSuperclusteringDNN",
    ])

    hlt_candidate_collections: List[str] = field(default_factory=lambda: [
        "hltTiclCandidate",
    ])

    # Whether to analyze HLT collections
    analyze_hlt: bool = False

    # Whether to analyze offline collections
    analyze_offline: bool = True

    def get_all_collections(self) -> List[str]:
        """Get all collections to analyze based on flags."""
        collections = []
        if self.analyze_offline:
            collections.extend(self.trackster_collections)
            collections.extend(self.candidate_collections)
        if self.analyze_hlt:
            collections.extend(self.hlt_trackster_collections)
            collections.extend(self.hlt_candidate_collections)
        return collections


@dataclass
class OutputConfig:
    """Configuration for output settings."""

    # Output directory
    output_dir: str = "validation_output"

    # Output formats
    save_png: bool = True
    save_pdf: bool = True
    save_root: bool = True

    # Summary JSON
    save_summary_json: bool = True

    # Plot styling
    figure_width: int = 10
    figure_height: int = 8
    dpi: int = 150


@dataclass
class ValidationConfig:
    """Main configuration class combining all settings."""

    binning: BinningConfig = field(default_factory=BinningConfig)
    matching: MatchingConfig = field(default_factory=MatchingConfig)
    collections: CollectionConfig = field(default_factory=CollectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    # Multi-threading
    enable_mt: bool = True
    num_threads: Optional[int] = None  # None = auto-detect

    # Modules to run
    modules: List[str] = field(default_factory=lambda: ["all"])

    # Validation suite
    suite: Optional[str] = None

    def __post_init__(self):
        """Validate configuration."""
        if self.matching.method not in ["shared_energy", "score"]:
            raise ValueError(f"Invalid matching method: {self.matching.method}")

        if self.suite and self.modules != ["all"]:
            print("Warning: Both suite and modules specified. Suite takes precedence.")
