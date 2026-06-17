"""Distribution plots module."""

import ROOT
from pathlib import Path
from typing import Dict, Any
from core.base_module import ValidationModule
from core.plotter import Plotter


class DistributionsModule(ValidationModule):
    """Module for basic distribution plots."""

    def __init__(self, config):
        super().__init__(config, name="distributions")
        self.plotter = None
        if config is not None:
            self.plotter = Plotter(config)

    def define_columns(self, rdf: ROOT.RDataFrame) -> ROOT.RDataFrame:
        """No additional columns needed for basic distributions."""
        return rdf

    def book_histograms(self, collection: str) -> Dict[str, Any]:
        """
        Book histograms for basic distributions.

        Args:
            collection: Collection name

        Returns:
            Dictionary of histogram definitions
        """
        cfg = self.config.binning
        size_branch = f"n{collection}"

        histograms = {
            # Multiplicity
            "multiplicity": {
                "variable": size_branch,
                "bins": 100,
                "xmin": 0,
                "xmax": 100,
                "title": f"{collection} Multiplicity",
                "xlabel": "Number of objects",
                "ylabel": "Events",
            },
            # Energy
            "energy": {
                "variable": f"{collection}_raw_energy",
                "bins": cfg.energy_bins,
                "xmin": cfg.energy_min,
                "xmax": cfg.energy_max,
                "title": f"{collection} Energy",
                "xlabel": "Raw Energy [GeV]",
                "ylabel": "Entries",
            },
            # Eta
            "eta": {
                "variable": f"{collection}_barycenter_eta",
                "bins": cfg.eta_bins,
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "title": f"{collection} Eta",
                "xlabel": r"$\eta$",
                "ylabel": "Entries",
            },
            # Phi
            "phi": {
                "variable": f"{collection}_barycenter_phi",
                "bins": cfg.phi_bins,
                "xmin": cfg.phi_min,
                "xmax": cfg.phi_max,
                "title": f"{collection} Phi",
                "xlabel": r"$\phi$",
                "ylabel": "Entries",
            },
            # pT (derived from raw_pt if available)
            "pt": {
                "variable": f"{collection}_raw_pt",
                "bins": cfg.pt_bins,
                "xmin": cfg.pt_min,
                "xmax": cfg.pt_max,
                "title": f"{collection} pT",
                "xlabel": r"Raw $p_\mathrm{T}$ [GeV]",
                "ylabel": "Entries",
            },
            # Eta vs Phi (2D)
            "eta_phi": {
                "variable": (f"{collection}_barycenter_eta", f"{collection}_barycenter_phi"),
                "bins": (cfg.eta_bins // 2, cfg.phi_bins // 2),
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "ymin": cfg.phi_min,
                "ymax": cfg.phi_max,
                "title": f"{collection} Eta vs Phi",
                "xlabel": r"$\eta$",
                "ylabel": r"$\phi$",
                "zlabel": "Entries",
            },
            # Energy vs Eta (2D)
            "energy_eta": {
                "variable": (f"{collection}_barycenter_eta", f"{collection}_raw_energy"),
                "bins": (cfg.eta_bins // 2, cfg.energy_bins // 2),
                "xmin": cfg.eta_min,
                "xmax": cfg.eta_max,
                "ymin": cfg.energy_min,
                "ymax": cfg.energy_max,
                "title": f"{collection} Energy vs Eta",
                "xlabel": r"$\eta$",
                "ylabel": "Raw Energy [GeV]",
                "zlabel": "Entries",
            },
        }

        return histograms

    def fill_histograms(
        self,
        rdf: ROOT.RDataFrame,
        collection: str,
    ) -> Dict[str, ROOT.RDF.RResultPtr]:
        """
        Fill histograms using RDataFrame.

        Args:
            rdf: RDataFrame
            collection: Collection name

        Returns:
            Dictionary of histogram RResultPtr objects
        """
        hist_defs = self.book_histograms(collection)
        filled_hists = {}

        for key, hdef in hist_defs.items():
            var = hdef["variable"]

            if key == "multiplicity":
                # Special case: just histogram the size branch directly
                model = (hdef["title"], hdef["title"],
                        hdef["bins"], hdef["xmin"], hdef["xmax"])
                filled_hists[key] = rdf.Histo1D(model, var)

            elif isinstance(var, tuple):  # 2D histogram
                model = (hdef["title"], hdef["title"],
                        hdef["bins"][0], hdef["xmin"], hdef["xmax"],
                        hdef["bins"][1], hdef["ymin"], hdef["ymax"])
                # Flatten the collection arrays for 2D histos
                filled_hists[key] = rdf.Histo2D(model, var[0], var[1])

            else:  # 1D histogram
                model = (hdef["title"], hdef["title"],
                        hdef["bins"], hdef["xmin"], hdef["xmax"])
                # Flatten the collection array
                filled_hists[key] = rdf.Histo1D(model, var)

        return filled_hists

    def compute_metrics(
        self,
        histograms: Dict[str, Any],
        collection: str
    ) -> Dict[str, float]:
        """
        Compute summary metrics.

        Args:
            histograms: Dictionary of histograms
            collection: Collection name

        Returns:
            Dictionary of metrics
        """
        metrics = {}

        # Get multiplicity statistics
        if "multiplicity" in histograms:
            h = histograms["multiplicity"]
            metrics[f"{collection}_mean_multiplicity"] = h.GetMean()
            metrics[f"{collection}_rms_multiplicity"] = h.GetRMS()

        # Get energy statistics
        if "energy" in histograms:
            h = histograms["energy"]
            metrics[f"{collection}_mean_energy"] = h.GetMean()
            metrics[f"{collection}_rms_energy"] = h.GetRMS()

        # Get eta coverage
        if "eta" in histograms:
            h = histograms["eta"]
            metrics[f"{collection}_mean_eta"] = h.GetMean()
            metrics[f"{collection}_rms_eta"] = h.GetRMS()

        return metrics

    def plot(
        self,
        histograms: Dict[str, Any],
        metrics: Dict[str, float],
        output_dir: Path,
        collection: str
    ):
        """
        Generate plots.

        Args:
            histograms: Dictionary of histograms
            metrics: Dictionary of metrics
            output_dir: Output directory
            collection: Collection name
        """
        output_dir = Path(output_dir) / collection
        output_dir.mkdir(parents=True, exist_ok=True)

        hist_defs = self.book_histograms(collection)

        # Plot 1D histograms
        for key in ["multiplicity", "energy", "eta", "phi", "pt"]:
            if key in histograms:
                hdef = hist_defs[key]
                self.plotter.plot_1d_histogram(
                    histograms[key],
                    output_dir,
                    key,
                    title=hdef["title"],
                    xlabel=hdef["xlabel"],
                    ylabel=hdef["ylabel"],
                    logy=(key == "multiplicity" or key == "energy"),
                )

        # Plot 2D histograms
        for key in ["eta_phi", "energy_eta"]:
            if key in histograms:
                hdef = hist_defs[key]
                self.plotter.plot_2d_histogram(
                    histograms[key],
                    output_dir,
                    key,
                    title=hdef["title"],
                    xlabel=hdef["xlabel"],
                    ylabel=hdef["ylabel"],
                    zlabel=hdef.get("zlabel", "Entries"),
                )

        print(f"  Saved distribution plots to {output_dir}")
