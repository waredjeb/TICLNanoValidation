"""Efficiency and fake rate module."""

import ROOT
from pathlib import Path
from typing import Dict, Any
from validation.core.base_module import ValidationModule
from validation.core.matcher import Matcher
from validation.core.plotter import Plotter


class EfficiencyModule(ValidationModule):
    """Module for efficiency and fake rate calculations."""

    def __init__(self, config):
        super().__init__(config, name="efficiency")
        self.dependencies = ["matching"]  # Depends on matching module
        self.matcher = None
        self.plotter = None
        if config is not None:
            self.matcher = Matcher(config)
            self.plotter = Plotter(config)

    def define_columns(self, rdf: ROOT.RDataFrame) -> ROOT.RDataFrame:
        """
        Define helper columns for matched sim objects.
        Matching columns should already be defined by the matching module.
        """
        collections = self.config.collections.get_all_collections()

        for collection in collections:
            # Check if collection exists
            if f"n{collection}" not in rdf.GetColumnNames():
                continue

            for sim_coll in self.config.matching.sim_collections:
                # Check if matching columns exist
                is_matched_col = f"{sim_coll}_to_{collection}_is_matched"
                if is_matched_col not in rdf.GetColumnNames():
                    continue

                # Get branch names
                if "SimCP" in sim_coll:
                    eta_branch = "ticlSimTrackstersfromCPs_barycenter_eta"
                    energy_branch = "ticlSimTrackstersfromCPs_raw_energy"
                    pt_branch = "ticlSimTrackstersfromCPs_raw_pt"
                else:  # SimSC
                    eta_branch = "ticlSimTracksters_barycenter_eta"
                    energy_branch = "ticlSimTracksters_raw_energy"
                    pt_branch = "ticlSimTracksters_raw_pt"

                # Check if sim branches exist
                if eta_branch not in rdf.GetColumnNames():
                    continue

                # Define matched-only columns using Take
                # These will contain only the values where is_matched is true
                try:
                    rdf = rdf.Define(f"{sim_coll}_{collection}_matched_eta",
                                    f"ROOT::VecOps::RVec<float>({eta_branch})[ROOT::VecOps::RVec<bool>({is_matched_col})]")
                    rdf = rdf.Define(f"{sim_coll}_{collection}_matched_energy",
                                    f"ROOT::VecOps::RVec<float>({energy_branch})[ROOT::VecOps::RVec<bool>({is_matched_col})]")
                    rdf = rdf.Define(f"{sim_coll}_{collection}_matched_pt",
                                    f"ROOT::VecOps::RVec<float>({pt_branch})[ROOT::VecOps::RVec<bool>({is_matched_col})]")
                except Exception as e:
                    print(f"  Warning: Could not define efficiency columns for {sim_coll}-{collection}: {e}")

        return rdf

    def get_available_sim_collections(self, rdf: ROOT.RDataFrame, collection: str) -> list:
        """Get list of sim collections that have associations."""
        available = []
        for sim_coll in self.config.matching.sim_collections:
            if self.matcher.check_sim_collection_exists(rdf, sim_coll, collection):
                available.append(sim_coll)
        return available

    def book_histograms(self, collection: str, sim_collections: list = None) -> Dict[str, Any]:
        """
        Book histograms for efficiency calculations.

        Args:
            collection: Collection name

        Returns:
            Dictionary of histogram definitions
        """
        cfg = self.config.binning
        histograms = {}

        if sim_collections is None:
            sim_collections = self.config.matching.sim_collections

        for sim_coll in sim_collections:
            # Get correct branch names for SimCP and SimSC
            if "SimCP" in sim_coll:
                eta_branch = "ticlSimTrackstersfromCPs_barycenter_eta"
                energy_branch = "ticlSimTrackstersfromCPs_raw_energy"
                pt_branch = "ticlSimTrackstersfromCPs_raw_pt"
            else:  # SimSC
                eta_branch = "ticlSimTracksters_barycenter_eta"
                energy_branch = "ticlSimTracksters_raw_energy"
                pt_branch = "ticlSimTracksters_raw_pt"

            # For efficiency: total sim objects and matched sim objects
            # Efficiency vs eta
            histograms[f"{sim_coll}_total_vs_eta"] = {
                "variable": eta_branch,
                "bins": cfg.eta_bins // 2,
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "title": f"{sim_coll} Total vs Eta",
                "xlabel": r"$\eta$",
                "ylabel": "Entries",
            }

            histograms[f"{sim_coll}_matched_vs_eta"] = {
                "variable": eta_branch,
                "filter": f"{sim_coll}_to_{collection}_is_matched",
                "bins": cfg.eta_bins // 2,
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "title": f"{sim_coll} Matched vs Eta",
                "xlabel": r"$\eta$",
                "ylabel": "Entries",
            }

            # Efficiency vs energy
            histograms[f"{sim_coll}_total_vs_energy"] = {
                "variable": energy_branch,
                "bins": cfg.energy_bins // 2,
                "xmin": cfg.energy_min,
                "xmax": cfg.energy_max,
                "title": f"{sim_coll} Total vs Energy",
                "xlabel": "Energy [GeV]",
                "ylabel": "Entries",
            }

            histograms[f"{sim_coll}_matched_vs_energy"] = {
                "variable": energy_branch,
                "filter": f"{sim_coll}_to_{collection}_is_matched",
                "bins": cfg.energy_bins // 2,
                "xmin": cfg.energy_min,
                "xmax": cfg.energy_max,
                "title": f"{sim_coll} Matched vs Energy",
                "xlabel": "Energy [GeV]",
                "ylabel": "Entries",
            }

            # Efficiency vs pT
            histograms[f"{sim_coll}_total_vs_pt"] = {
                "variable": pt_branch,
                "bins": cfg.pt_bins // 2,
                "xmin": cfg.pt_min,
                "xmax": cfg.pt_max,
                "title": f"{sim_coll} Total vs pT",
                "xlabel": r"$p_\mathrm{T}$ [GeV]",
                "ylabel": "Entries",
            }

            histograms[f"{sim_coll}_matched_vs_pt"] = {
                "variable": pt_branch,
                "filter": f"{sim_coll}_to_{collection}_is_matched",
                "bins": cfg.pt_bins // 2,
                "xmin": cfg.pt_min,
                "xmax": cfg.pt_max,
                "title": f"{sim_coll} Matched vs pT",
                "xlabel": r"$p_\mathrm{T}$ [GeV]",
                "ylabel": "Entries",
            }

            # For fake rate: total reco objects and fake reco objects
            histograms[f"{collection}_total_vs_eta"] = {
                "variable": f"{collection}_barycenter_eta",
                "bins": cfg.eta_bins // 2,
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "title": f"{collection} Total vs Eta",
                "xlabel": r"$\eta$",
                "ylabel": "Entries",
            }

            histograms[f"{collection}_fake_vs_eta_{sim_coll}"] = {
                "variable": f"{collection}_barycenter_eta",
                "filter": f"{collection}_to_{sim_coll}_is_fake",
                "bins": cfg.eta_bins // 2,
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "title": f"{collection} Fake vs Eta ({sim_coll})",
                "xlabel": r"$\eta$",
                "ylabel": "Entries",
            }

        return histograms

    def fill_histograms(
        self,
        rdf: ROOT.RDataFrame,
        collection: str,
    ) -> Dict[str, ROOT.RDF.RResultPtr]:
        """
        Fill efficiency histograms.

        Args:
            rdf: RDataFrame
            collection: Collection name

        Returns:
            Dictionary of histogram RResultPtr objects
        """
        available_sims = self.get_available_sim_collections(rdf, collection)
        if not available_sims:
            print(f"  Warning: No sim associations found for {collection}")
            return {}

        hist_defs = self.book_histograms(collection, available_sims)
        filled_hists = {}

        # Fill histograms
        for key, hdef in hist_defs.items():
            var = hdef["variable"]
            model = (hdef["title"], hdef["title"],
                    hdef["bins"], hdef["xmin"], hdef["xmax"])

            try:
                if "filter" in hdef:
                    # Use the pre-defined matched column
                    sim_coll = key.split("_")[0]
                    if "eta" in key:
                        var = f"{sim_coll}_{collection}_matched_eta"
                    elif "energy" in key:
                        var = f"{sim_coll}_{collection}_matched_energy"
                    elif "pt" in key:
                        var = f"{sim_coll}_{collection}_matched_pt"

                    # Check if the column exists
                    if var not in rdf.GetColumnNames():
                        print(f"  Warning: Column {var} not found, skipping {key}")
                        continue

                filled_hists[key] = rdf.Histo1D(model, var)
            except Exception as e:
                print(f"  Warning: Could not fill histogram {key}: {e}")

        return filled_hists

    def compute_metrics(
        self,
        histograms: Dict[str, Any],
        collection: str
    ) -> Dict[str, float]:
        """
        Compute efficiency and fake rate metrics.

        Args:
            histograms: Dictionary of histograms
            collection: Collection name

        Returns:
            Dictionary of metrics
        """
        metrics = {}

        for sim_coll in self.config.matching.sim_collections:
            # Overall efficiency
            total_key = f"{sim_coll}_total_vs_eta"
            matched_key = f"{sim_coll}_matched_vs_eta"

            if total_key in histograms and matched_key in histograms:
                total = histograms[total_key].Integral()
                matched = histograms[matched_key].Integral()
                if total > 0:
                    efficiency = matched / total
                    metrics[f"{collection}_{sim_coll}_overall_efficiency"] = efficiency

            # Overall fake rate
            reco_total_key = f"{collection}_total_vs_eta"
            fake_key = f"{collection}_fake_vs_eta_{sim_coll}"

            if reco_total_key in histograms and fake_key in histograms:
                total_reco = histograms[reco_total_key].Integral()
                fake = histograms[fake_key].Integral()
                if total_reco > 0:
                    fake_rate = fake / total_reco
                    metrics[f"{collection}_{sim_coll}_fake_rate"] = fake_rate

        return metrics

    def plot(
        self,
        histograms: Dict[str, Any],
        metrics: Dict[str, float],
        output_dir: Path,
        collection: str
    ):
        """
        Generate efficiency plots.

        Args:
            histograms: Dictionary of histograms
            metrics: Dictionary of metrics
            output_dir: Output directory
            collection: Collection name
        """
        output_dir = Path(output_dir) / collection
        output_dir.mkdir(parents=True, exist_ok=True)

        for sim_coll in self.config.matching.sim_collections:
            # Efficiency vs eta
            self._plot_efficiency_curve(
                histograms,
                f"{sim_coll}_matched_vs_eta",
                f"{sim_coll}_total_vs_eta",
                output_dir,
                f"efficiency_vs_eta_{sim_coll}",
                f"{collection} Efficiency vs Eta ({sim_coll})",
                r"$\eta$"
            )

            # Efficiency vs energy
            self._plot_efficiency_curve(
                histograms,
                f"{sim_coll}_matched_vs_energy",
                f"{sim_coll}_total_vs_energy",
                output_dir,
                f"efficiency_vs_energy_{sim_coll}",
                f"{collection} Efficiency vs Energy ({sim_coll})",
                "Energy [GeV]"
            )

            # Efficiency vs pT
            self._plot_efficiency_curve(
                histograms,
                f"{sim_coll}_matched_vs_pt",
                f"{sim_coll}_total_vs_pt",
                output_dir,
                f"efficiency_vs_pt_{sim_coll}",
                f"{collection} Efficiency vs pT ({sim_coll})",
                r"$p_\mathrm{T}$ [GeV]"
            )

            # Fake rate vs eta
            self._plot_efficiency_curve(
                histograms,
                f"{collection}_fake_vs_eta_{sim_coll}",
                f"{collection}_total_vs_eta",
                output_dir,
                f"fake_rate_vs_eta_{sim_coll}",
                f"{collection} Fake Rate vs Eta ({sim_coll})",
                r"$\eta$",
                ylabel="Fake Rate"
            )

        print(f"  Saved efficiency plots to {output_dir}")

    def _plot_efficiency_curve(
        self,
        histograms: Dict[str, Any],
        passed_key: str,
        total_key: str,
        output_dir: Path,
        name: str,
        title: str,
        xlabel: str,
        ylabel: str = "Efficiency"
    ):
        """Helper to plot efficiency curves."""
        if passed_key in histograms and total_key in histograms:
            self.plotter.plot_efficiency(
                histograms[passed_key],
                histograms[total_key],
                output_dir,
                name,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
            )
