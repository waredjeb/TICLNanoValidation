"""Energy resolution module."""

import ROOT
from pathlib import Path
from typing import Dict, Any
from core.base_module import ValidationModule
from core.matcher import Matcher
from core.plotter import Plotter


class ResolutionModule(ValidationModule):
    """Module for energy resolution studies."""

    def __init__(self, config):
        super().__init__(config, name="resolution")
        self.dependencies = ["matching"]  # Needs matching
        self.matcher = None
        self.plotter = None
        if config is not None:
            self.matcher = Matcher(config)
            self.plotter = Plotter(config)

    def define_columns(self, rdf: ROOT.RDataFrame) -> ROOT.RDataFrame:
        """
        Define resolution columns.

        Adds columns for (Reco - Sim) / Sim for matched objects.
        """
        collections = self.config.collections.get_all_collections()

        for collection in collections:
            if not self._collection_exists(rdf, collection):
                continue

            # Only define columns for sim collections that exist
            available_sims = self.get_available_sim_collections(rdf, collection)
            for sim_coll in available_sims:
                try:
                    # Define resolution columns for energy, pt, eta
                    rdf = self._define_resolution_columns(
                        rdf, sim_coll, collection
                    )
                except Exception as e:
                    print(f"  Warning: Could not define resolution for {collection}-{sim_coll}: {e}")

        return rdf

    def _collection_exists(self, rdf: ROOT.RDataFrame, collection: str) -> bool:
        """Check if collection exists."""
        return f"n{collection}" in rdf.GetColumnNames()

    def get_available_sim_collections(self, rdf: ROOT.RDataFrame, collection: str) -> list:
        """Get list of sim collections that have associations."""
        available = []
        for sim_coll in self.config.matching.sim_collections:
            if self.matcher.check_sim_collection_exists(rdf, sim_coll, collection):
                available.append(sim_coll)
        return available

    def _define_resolution_columns(
        self,
        rdf: ROOT.RDataFrame,
        sim_coll: str,
        reco_coll: str
    ) -> ROOT.RDataFrame:
        """
        Define resolution columns for a sim-reco pair.

        Args:
            rdf: RDataFrame
            sim_coll: Sim collection
            reco_coll: Reco collection

        Returns:
            RDataFrame with resolution columns
        """
        # Get sim energy branch
        if "SimCP" in sim_coll:
            sim_energy_branch = "ticlSimTrackstersfromCPs_raw_energy"
            sim_pt_branch = "ticlSimTrackstersfromCPs_raw_pt"
        else:  # SimSC
            sim_energy_branch = "ticlSimTracksters_raw_energy"
            sim_pt_branch = "ticlSimTracksters_raw_pt"

        # Reco branches
        reco_energy_branch = f"{reco_coll}_raw_energy"
        reco_pt_branch = f"{reco_coll}_raw_pt"
        reco_eta_branch = f"{reco_coll}_barycenter_eta"

        # Matched index column
        matched_col = f"{sim_coll}_to_{reco_coll}_matched"

        # Energy resolution: (Reco - Sim) / Sim
        energy_res_code = f"""
        std::vector<float> resolutions;
        for (size_t i = 0; i < {sim_energy_branch}.size(); ++i) {{
            int matched_idx = {matched_col}[i];
            if (matched_idx >= 0) {{
                float sim_e = {sim_energy_branch}[i];
                float reco_e = {reco_energy_branch}[matched_idx];
                if (sim_e > 0) {{
                    resolutions.push_back((reco_e - sim_e) / sim_e);
                }}
            }}
        }}
        return resolutions;
        """

        rdf = rdf.Define(f"{sim_coll}_{reco_coll}_energy_resolution", energy_res_code)

        # pT resolution
        pt_res_code = f"""
        std::vector<float> resolutions;
        for (size_t i = 0; i < {sim_pt_branch}.size(); ++i) {{
            int matched_idx = {matched_col}[i];
            if (matched_idx >= 0) {{
                float sim_pt = {sim_pt_branch}[i];
                float reco_pt = {reco_pt_branch}[matched_idx];
                if (sim_pt > 0) {{
                    resolutions.push_back((reco_pt - sim_pt) / sim_pt);
                }}
            }}
        }}
        return resolutions;
        """

        rdf = rdf.Define(f"{sim_coll}_{reco_coll}_pt_resolution", pt_res_code)

        # Sim eta branch
        if "SimCP" in sim_coll:
            sim_eta_branch = "ticlSimTrackstersfromCPs_barycenter_eta"
        else:  # SimSC
            sim_eta_branch = "ticlSimTracksters_barycenter_eta"

        # Also save the sim eta and energy for the matched objects (for 2D plots)
        matched_sim_eta_code = f"""
        std::vector<float> etas;
        for (size_t i = 0; i < {sim_eta_branch}.size(); ++i) {{
            if ({matched_col}[i] >= 0) {{
                etas.push_back({sim_eta_branch}[i]);
            }}
        }}
        return etas;
        """

        rdf = rdf.Define(f"{sim_coll}_{reco_coll}_matched_sim_eta", matched_sim_eta_code)

        matched_sim_energy_code = f"""
        std::vector<float> energies;
        for (size_t i = 0; i < {sim_energy_branch}.size(); ++i) {{
            if ({matched_col}[i] >= 0) {{
                energies.push_back({sim_energy_branch}[i]);
            }}
        }}
        return energies;
        """

        rdf = rdf.Define(f"{sim_coll}_{reco_coll}_matched_sim_energy", matched_sim_energy_code)

        matched_sim_pt_code = f"""
        std::vector<float> pts;
        for (size_t i = 0; i < {sim_pt_branch}.size(); ++i) {{
            if ({matched_col}[i] >= 0) {{
                pts.push_back({sim_pt_branch}[i]);
            }}
        }}
        return pts;
        """

        rdf = rdf.Define(f"{sim_coll}_{reco_coll}_matched_sim_pt", matched_sim_pt_code)

        # Response = Reco / Sim
        energy_response_code = f"""
        std::vector<float> responses;
        for (size_t i = 0; i < {sim_energy_branch}.size(); ++i) {{
            int matched_idx = {matched_col}[i];
            if (matched_idx >= 0) {{
                float sim_e = {sim_energy_branch}[i];
                float reco_e = {reco_energy_branch}[matched_idx];
                if (sim_e > 0) {{
                    responses.push_back(reco_e / sim_e);
                }}
            }}
        }}
        return responses;
        """

        rdf = rdf.Define(f"{sim_coll}_{reco_coll}_energy_response", energy_response_code)

        return rdf

    def book_histograms(self, collection: str, sim_collections: list = None) -> Dict[str, Any]:
        """
        Book resolution histograms.

        Args:
            collection: Collection name
            sim_collections: List of available sim collections

        Returns:
            Dictionary of histogram definitions
        """
        cfg = self.config.binning
        histograms = {}

        if sim_collections is None:
            sim_collections = self.config.matching.sim_collections

        for sim_coll in sim_collections:
            # Energy resolution distribution
            histograms[f"{sim_coll}_energy_resolution"] = {
                "variable": f"{sim_coll}_{collection}_energy_resolution",
                "bins": cfg.resolution_bins,
                "xmin": cfg.resolution_min,
                "xmax": cfg.resolution_max,
                "title": f"{collection} Energy Resolution ({sim_coll})",
                "xlabel": r"$(E_\mathrm{reco} - E_\mathrm{sim}) / E_\mathrm{sim}$",
                "ylabel": "Entries",
            }

            # pT resolution distribution
            histograms[f"{sim_coll}_pt_resolution"] = {
                "variable": f"{sim_coll}_{collection}_pt_resolution",
                "bins": cfg.resolution_bins,
                "xmin": cfg.resolution_min,
                "xmax": cfg.resolution_max,
                "title": f"{collection} pT Resolution ({sim_coll})",
                "xlabel": r"$(p_{\mathrm{T,reco}} - p_{\mathrm{T,sim}}) / p_{\mathrm{T,sim}}$",
                "ylabel": "Entries",
            }

            # Energy resolution vs eta (2D)
            histograms[f"{sim_coll}_energy_resolution_vs_eta"] = {
                "variable": (
                    f"{sim_coll}_{collection}_matched_sim_eta",
                    f"{sim_coll}_{collection}_energy_resolution"
                ),
                "bins": (cfg.eta_bins // 2, cfg.resolution_bins // 2),
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "ymin": cfg.resolution_min,
                "ymax": cfg.resolution_max,
                "title": f"{collection} Energy Resolution vs Eta ({sim_coll})",
                "xlabel": r"$\eta$",
                "ylabel": r"$(E_\mathrm{reco} - E_\mathrm{sim}) / E_\mathrm{sim}$",
                "zlabel": "Entries",
            }

            # Energy resolution vs energy (2D)
            histograms[f"{sim_coll}_energy_resolution_vs_energy"] = {
                "variable": (
                    f"{sim_coll}_{collection}_matched_sim_energy",
                    f"{sim_coll}_{collection}_energy_resolution"
                ),
                "bins": (cfg.energy_bins // 2, cfg.resolution_bins // 2),
                "xmin": cfg.energy_min,
                "xmax": cfg.energy_max,
                "ymin": cfg.resolution_min,
                "ymax": cfg.resolution_max,
                "title": f"{collection} Energy Resolution vs Energy ({sim_coll})",
                "xlabel": r"$E_\mathrm{sim}$ [GeV]",
                "ylabel": r"$(E_\mathrm{reco} - E_\mathrm{sim}) / E_\mathrm{sim}$",
                "zlabel": "Entries",
            }

            # pT resolution vs pT (2D)
            histograms[f"{sim_coll}_pt_resolution_vs_pt"] = {
                "variable": (
                    f"{sim_coll}_{collection}_matched_sim_pt",
                    f"{sim_coll}_{collection}_pt_resolution"
                ),
                "bins": (cfg.pt_bins // 2, cfg.resolution_bins // 2),
                "xmin": cfg.pt_min,
                "xmax": cfg.pt_max,
                "ymin": cfg.resolution_min,
                "ymax": cfg.resolution_max,
                "title": f"{collection} pT Resolution vs pT ({sim_coll})",
                "xlabel": r"$p_{\mathrm{T,sim}}$ [GeV]",
                "ylabel": r"$(p_{\mathrm{T,reco}} - p_{\mathrm{T,sim}}) / p_{\mathrm{T,sim}}$",
                "zlabel": "Entries",
            }

            # Energy response
            histograms[f"{sim_coll}_energy_response"] = {
                "variable": f"{sim_coll}_{collection}_energy_response",
                "bins": cfg.response_bins,
                "xmin": cfg.response_min,
                "xmax": cfg.response_max,
                "title": f"{collection} Energy Response ({sim_coll})",
                "xlabel": r"$E_\mathrm{reco} / E_\mathrm{sim}$",
                "ylabel": "Entries",
            }

            # Energy response vs eta (2D)
            histograms[f"{sim_coll}_energy_response_vs_eta"] = {
                "variable": (
                    f"{sim_coll}_{collection}_matched_sim_eta",
                    f"{sim_coll}_{collection}_energy_response"
                ),
                "bins": (cfg.eta_bins // 2, cfg.response_bins // 2),
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "ymin": cfg.response_min,
                "ymax": cfg.response_max,
                "title": f"{collection} Energy Response vs Eta ({sim_coll})",
                "xlabel": r"$\eta$",
                "ylabel": r"$E_\mathrm{reco} / E_\mathrm{sim}$",
                "zlabel": "Entries",
            }

        return histograms

    def fill_histograms(
        self,
        rdf: ROOT.RDataFrame,
        collection: str,
    ) -> Dict[str, ROOT.RDF.RResultPtr]:
        """Fill resolution histograms."""
        available_sims = self.get_available_sim_collections(rdf, collection)
        if not available_sims:
            print(f"  Warning: No sim associations found for {collection}")
            return {}

        hist_defs = self.book_histograms(collection, available_sims)
        filled_hists = {}

        for key, hdef in hist_defs.items():
            var = hdef["variable"]

            try:
                if isinstance(var, tuple):  # 2D
                    model = (hdef["title"], hdef["title"],
                            hdef["bins"][0], hdef["xmin"], hdef["xmax"],
                            hdef["bins"][1], hdef["ymin"], hdef["ymax"])
                    filled_hists[key] = rdf.Histo2D(model, var[0], var[1])
                else:  # 1D
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
        """Compute resolution metrics."""
        metrics = {}

        for sim_coll in self.config.matching.sim_collections:
            # Energy resolution statistics
            key = f"{sim_coll}_energy_resolution"
            if key in histograms:
                h = histograms[key]
                metrics[f"{collection}_{sim_coll}_energy_resolution_mean"] = h.GetMean()
                metrics[f"{collection}_{sim_coll}_energy_resolution_rms"] = h.GetRMS()

            # pT resolution statistics
            key = f"{sim_coll}_pt_resolution"
            if key in histograms:
                h = histograms[key]
                metrics[f"{collection}_{sim_coll}_pt_resolution_mean"] = h.GetMean()
                metrics[f"{collection}_{sim_coll}_pt_resolution_rms"] = h.GetRMS()

            # Energy response statistics
            key = f"{sim_coll}_energy_response"
            if key in histograms:
                h = histograms[key]
                metrics[f"{collection}_{sim_coll}_energy_response_mean"] = h.GetMean()
                metrics[f"{collection}_{sim_coll}_energy_response_rms"] = h.GetRMS()

        return metrics

    def plot(
        self,
        histograms: Dict[str, Any],
        metrics: Dict[str, float],
        output_dir: Path,
        collection: str
    ):
        """Generate resolution plots."""
        output_dir = Path(output_dir) / collection
        output_dir.mkdir(parents=True, exist_ok=True)

        hist_defs = self.book_histograms(collection)

        for key, h in histograms.items():
            if key not in hist_defs:
                continue

            hdef = hist_defs[key]

            if isinstance(hdef["variable"], tuple):  # 2D
                if "resolution_vs" in key or "response_vs" in key:
                    # Use resolution plotter for 2D plots
                    self.plotter.plot_resolution(
                        h,
                        output_dir,
                        key,
                        title=hdef["title"],
                        xlabel=hdef["xlabel"],
                        ylabel=hdef["ylabel"],
                    )
                else:
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

        print(f"  Saved resolution plots to {output_dir}")
