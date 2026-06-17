"""Matching quality metrics module."""

import ROOT
from pathlib import Path
from typing import Dict, Any, List
from validation.core.base_module import ValidationModule
from validation.core.matcher import Matcher
from validation.core.plotter import Plotter


class MatchingModule(ValidationModule):
    """Module for matching quality metrics."""

    def __init__(self, config):
        super().__init__(config, name="matching")
        self.matcher = None
        self.plotter = None
        if config is not None:
            self.matcher = Matcher(config)
            self.plotter = Plotter(config)

    def define_columns(self, rdf: ROOT.RDataFrame) -> ROOT.RDataFrame:
        """
        Define matching columns for all relevant collections.

        Args:
            rdf: Input RDataFrame

        Returns:
            RDataFrame with matching columns
        """
        collections = self.config.collections.get_all_collections()

        for collection in collections:
            # Skip if collection doesn't exist
            if not self._collection_exists(rdf, collection):
                continue

            # Define matching for each sim collection
            for sim_coll in self.config.matching.sim_collections:
                # Sim2Reco
                if self.matcher.check_sim_collection_exists(rdf, sim_coll, collection):
                    try:
                        rdf = self.matcher.define_sim2reco_matches(
                            rdf, sim_coll, collection
                        )
                    except Exception as e:
                        print(f"  Warning: Could not define {sim_coll}2{collection} matching: {e}")

                # Reco2Sim
                if self.matcher.check_reco2sim_exists(rdf, collection, sim_coll):
                    try:
                        rdf = self.matcher.define_reco2sim_matches(
                            rdf, collection, sim_coll
                        )
                    except Exception as e:
                        print(f"  Warning: Could not define {collection}2{sim_coll} matching: {e}")

        return rdf

    def _collection_exists(self, rdf: ROOT.RDataFrame, collection: str) -> bool:
        """Check if collection exists in RDataFrame."""
        size_branch = f"n{collection}"
        return size_branch in rdf.GetColumnNames()

    def get_available_sim_collections(self, rdf: ROOT.RDataFrame, collection: str) -> List[str]:
        """Get list of sim collections that have associations with this reco collection."""
        available = []
        for sim_coll in self.config.matching.sim_collections:
            if self.matcher.check_sim_collection_exists(rdf, sim_coll, collection):
                available.append(sim_coll)
        return available

    def book_histograms(self, collection: str, sim_collections: List[str] = None) -> Dict[str, Any]:
        """
        Book histograms for matching quality.

        Args:
            collection: Collection name
            sim_collections: List of available sim collections (optional)

        Returns:
            Dictionary of histogram definitions
        """
        cfg = self.config.binning
        histograms = {}

        if sim_collections is None:
            sim_collections = self.config.matching.sim_collections

        for sim_coll in sim_collections:
            # Get correct eta branch name
            if "SimCP" in sim_coll:
                eta_branch = "ticlSimTrackstersfromCPs_barycenter_eta"
            else:  # SimSC
                eta_branch = "ticlSimTracksters_barycenter_eta"

            # Matching quality distribution
            histograms[f"{sim_coll}_quality"] = {
                "variable": f"{sim_coll}_to_{collection}_quality",
                "bins": 100,
                "xmin": 0.0,
                "xmax": 1.0 if self.config.matching.method == "shared_energy" else 2.0,
                "title": f"{sim_coll} to {collection} Match Quality",
                "xlabel": "Shared Energy Fraction" if self.config.matching.method == "shared_energy" else "Score",
                "ylabel": "Entries",
            }

            # Matching quality vs eta (2D)
            histograms[f"{sim_coll}_quality_vs_eta"] = {
                "variable": (eta_branch, f"{sim_coll}_to_{collection}_quality"),
                "bins": (cfg.eta_bins // 2, 50),
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "ymin": 0.0,
                "ymax": 1.0 if self.config.matching.method == "shared_energy" else 2.0,
                "title": f"{sim_coll} to {collection} Quality vs Eta",
                "xlabel": r"$\eta$",
                "ylabel": "Match Quality",
                "zlabel": "Entries",
            }

            # Number of matched objects
            histograms[f"{sim_coll}_n_matched"] = {
                "variable": f"{sim_coll}_to_{collection}_is_matched",
                "bins": 2,
                "xmin": 0,
                "xmax": 2,
                "title": f"{sim_coll} Matched Status",
                "xlabel": "Matched (0=No, 1=Yes)",
                "ylabel": "Entries",
            }

        return histograms

    def fill_histograms(
        self,
        rdf: ROOT.RDataFrame,
        collection: str,
    ) -> Dict[str, ROOT.RDF.RResultPtr]:
        """
        Fill matching histograms.

        Args:
            rdf: RDataFrame
            collection: Collection name

        Returns:
            Dictionary of histogram RResultPtr objects
        """
        # Get available sim collections
        available_sims = self.get_available_sim_collections(rdf, collection)
        if not available_sims:
            print(f"  Warning: No sim associations found for {collection}")
            return {}

        print(f"  Available sim collections: {', '.join(available_sims)}")
        hist_defs = self.book_histograms(collection, available_sims)
        filled_hists = {}

        for key, hdef in hist_defs.items():
            var = hdef["variable"]

            try:
                if isinstance(var, tuple):  # 2D histogram
                    model = (hdef["title"], hdef["title"],
                            hdef["bins"][0], hdef["xmin"], hdef["xmax"],
                            hdef["bins"][1], hdef["ymin"], hdef["ymax"])
                    filled_hists[key] = rdf.Histo2D(model, var[0], var[1])
                else:  # 1D histogram
                    model = (hdef["title"], hdef["title"],
                            hdef["bins"], hdef["xmin"], hdef["xmax"])
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
        Compute matching metrics.

        Args:
            histograms: Dictionary of histograms
            collection: Collection name

        Returns:
            Dictionary of metrics
        """
        metrics = {}

        for sim_coll in self.config.matching.sim_collections:
            quality_key = f"{sim_coll}_quality"
            matched_key = f"{sim_coll}_n_matched"

            if quality_key in histograms:
                h = histograms[quality_key]
                metrics[f"{collection}_{sim_coll}_mean_quality"] = h.GetMean()
                metrics[f"{collection}_{sim_coll}_rms_quality"] = h.GetRMS()

            if matched_key in histograms:
                h = histograms[matched_key]
                # Bin 2 contains matched (value=1), bin 1 contains unmatched (value=0)
                total = h.Integral()
                matched = h.GetBinContent(2)
                if total > 0:
                    metrics[f"{collection}_{sim_coll}_match_fraction"] = matched / total

        return metrics

    def plot(
        self,
        histograms: Dict[str, Any],
        metrics: Dict[str, float],
        output_dir: Path,
        collection: str
    ):
        """
        Generate matching plots.

        Args:
            histograms: Dictionary of histograms
            metrics: Dictionary of metrics
            output_dir: Output directory
            collection: Collection name
        """
        output_dir = Path(output_dir) / collection
        output_dir.mkdir(parents=True, exist_ok=True)

        hist_defs = self.book_histograms(collection)

        for key, h in histograms.items():
            if key not in hist_defs:
                continue

            hdef = hist_defs[key]

            if isinstance(hdef["variable"], tuple):  # 2D
                self.plotter.plot_2d_histogram(
                    h,
                    output_dir,
                    key,
                    title=hdef["title"],
                    xlabel=hdef["xlabel"],
                    ylabel=hdef["ylabel"],
                    zlabel=hdef.get("zlabel", "Entries"),
                )
            else:  # 1D
                self.plotter.plot_1d_histogram(
                    h,
                    output_dir,
                    key,
                    title=hdef["title"],
                    xlabel=hdef["xlabel"],
                    ylabel=hdef["ylabel"],
                )

        print(f"  Saved matching plots to {output_dir}")
