"""Common plotting utilities using matplotlib and mplhep."""

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import mplhep as hep
import numpy as np
from pathlib import Path
from typing import Optional, List
import ROOT


class Plotter:
    """Handles plot generation with CMS style using matplotlib and mplhep."""

    def __init__(self, config):
        """
        Initialize plotter.

        Args:
            config: ValidationConfig object
        """
        self.config = config
        if config is not None:
            self._setup_style()

    def _setup_style(self):
        """Set up matplotlib plotting style with CMS style."""
        plt.style.use(hep.style.CMS)
        # Additional customizations
        plt.rcParams['figure.figsize'] = (
            self.config.output.figure_width,
            self.config.output.figure_height
        )
        plt.rcParams['figure.dpi'] = self.config.output.dpi
        plt.rcParams['font.size'] = 14
        plt.rcParams['axes.labelsize'] = 16
        plt.rcParams['axes.titlesize'] = 18
        plt.rcParams['xtick.labelsize'] = 14
        plt.rcParams['ytick.labelsize'] = 14
        plt.rcParams['legend.fontsize'] = 12
        plt.rcParams['grid.alpha'] = 0.3

        # Enable LaTeX-style math rendering
        plt.rcParams['text.usetex'] = False  # Use matplotlib's mathtext, not full LaTeX
        plt.rcParams['mathtext.default'] = 'regular'

    def _root_hist_to_numpy(self, hist: ROOT.TH1) -> tuple:
        """
        Convert ROOT histogram to numpy arrays.

        Args:
            hist: ROOT TH1 histogram

        Returns:
            Tuple of (bin_edges, bin_contents, bin_errors)
        """
        n_bins = hist.GetNbinsX()
        bin_edges = np.array([hist.GetBinLowEdge(i) for i in range(1, n_bins + 2)])
        bin_contents = np.array([hist.GetBinContent(i) for i in range(1, n_bins + 1)])
        bin_errors = np.array([hist.GetBinError(i) for i in range(1, n_bins + 1)])
        return bin_edges, bin_contents, bin_errors

    def _root_hist2d_to_numpy(self, hist: ROOT.TH2) -> tuple:
        """
        Convert ROOT 2D histogram to numpy arrays.

        Args:
            hist: ROOT TH2 histogram

        Returns:
            Tuple of (x_edges, y_edges, contents)
        """
        nx = hist.GetNbinsX()
        ny = hist.GetNbinsY()

        x_edges = np.array([hist.GetXaxis().GetBinLowEdge(i) for i in range(1, nx + 2)])
        y_edges = np.array([hist.GetYaxis().GetBinLowEdge(i) for i in range(1, ny + 2)])

        contents = np.zeros((ny, nx))
        for i in range(1, nx + 1):
            for j in range(1, ny + 1):
                contents[j - 1, i - 1] = hist.GetBinContent(i, j)

        return x_edges, y_edges, contents

    def save_plot(self, fig, output_dir: Path, name: str):
        """
        Save figure to file(s).

        Args:
            fig: matplotlib figure
            output_dir: Output directory
            name: Base filename (without extension)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if self.config.output.save_png:
            fig.savefig(output_dir / f"{name}.png", bbox_inches='tight')

        if self.config.output.save_pdf:
            fig.savefig(output_dir / f"{name}.pdf", bbox_inches='tight')

        plt.close(fig)

    def plot_1d_histogram(
        self,
        hist: ROOT.TH1,
        output_dir: Path,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "Entries",
        logy: bool = False,
        cms_label: str = "Preliminary",
    ):
        """
        Plot a 1D histogram.

        Args:
            hist: ROOT TH1 histogram
            output_dir: Output directory
            name: Filename (without extension)
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            logy: Use log scale on y-axis
            cms_label: CMS label (Preliminary, Work in Progress, etc.)
        """
        bin_edges, bin_contents, bin_errors = self._root_hist_to_numpy(hist)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        fig, ax = plt.subplots()

        # Plot histogram with step style
        hep.histplot(
            bin_contents,
            bins=bin_edges,
            yerr=bin_errors,
            ax=ax,
            histtype='step',
            linewidth=2,
            color='blue'
        )

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if logy:
            ax.set_yscale('log')
            ax.set_ylim(bottom=0.5)

        # Add CMS label
        hep.cms.label(cms_label, data=False, lumi="Phase-2", ax=ax, loc=0)

        # Add grid
        ax.grid(True, alpha=0.3)

        self.save_plot(fig, output_dir, name)

    def plot_2d_histogram(
        self,
        hist: ROOT.TH2,
        output_dir: Path,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        zlabel: str = "Entries",
        cms_label: str = "Preliminary",
    ):
        """
        Plot a 2D histogram.

        Args:
            hist: ROOT TH2 histogram
            output_dir: Output directory
            name: Filename (without extension)
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            zlabel: Z-axis label (colorbar)
            cms_label: CMS label
        """
        x_edges, y_edges, contents = self._root_hist2d_to_numpy(hist)

        fig, ax = plt.subplots(figsize=(self.config.output.figure_width + 1,
                                        self.config.output.figure_height))

        # Create 2D histogram plot
        im = ax.pcolormesh(x_edges, y_edges, contents, cmap='viridis', shading='auto')

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        # Add colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(zlabel)

        # Add CMS label
        hep.cms.label(cms_label, data=False, lumi="Phase-2", ax=ax, loc=0)

        self.save_plot(fig, output_dir, name)

    def plot_efficiency(
        self,
        passed_hist: ROOT.TH1,
        total_hist: ROOT.TH1,
        output_dir: Path,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "Efficiency",
        cms_label: str = "Preliminary",
    ):
        """
        Plot efficiency curve with error bars.

        Args:
            passed_hist: Histogram of passed events
            total_hist: Histogram of total events
            output_dir: Output directory
            name: Filename (without extension)
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            cms_label: CMS label
        """
        _, passed, _ = self._root_hist_to_numpy(passed_hist)
        bin_edges, total, _ = self._root_hist_to_numpy(total_hist)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # Calculate efficiency and binomial errors
        efficiency = np.zeros_like(passed, dtype=float)
        err_low = np.zeros_like(passed, dtype=float)
        err_high = np.zeros_like(passed, dtype=float)

        for i in range(len(passed)):
            if total[i] > 0:
                eff = passed[i] / total[i]
                efficiency[i] = eff

                # Clopper-Pearson errors (approximate)
                err_low[i] = eff - max(0, eff - 1.96 * np.sqrt(eff * (1 - eff) / total[i]))
                err_high[i] = min(1, eff + 1.96 * np.sqrt(eff * (1 - eff) / total[i])) - eff

        fig, ax = plt.subplots()

        # Plot efficiency with error bars
        ax.errorbar(
            bin_centers,
            efficiency,
            yerr=[err_low, err_high],
            fmt='o',
            markersize=6,
            capsize=3,
            color='blue',
            label='Efficiency'
        )

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_ylim(-0.05, 1.15)
        ax.axhline(y=1.0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.grid(True, alpha=0.3)

        # Add CMS label
        hep.cms.label(cms_label, data=False, lumi="Phase-2", ax=ax, loc=0)

        self.save_plot(fig, output_dir, name)

    def plot_comparison(
        self,
        hists: list,
        labels: list,
        output_dir: Path,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "Entries",
        logy: bool = False,
        normalize: bool = False,
        cms_label: str = "Preliminary",
    ):
        """
        Plot multiple histograms for comparison.

        Args:
            hists: List of ROOT TH1 histograms
            labels: List of labels for each histogram
            output_dir: Output directory
            name: Filename (without extension)
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            logy: Use log scale on y-axis
            normalize: Normalize histograms to unity
            cms_label: CMS label
        """
        fig, ax = plt.subplots()

        colors = ['blue', 'red', 'green', 'orange', 'purple']

        for i, (hist, label) in enumerate(zip(hists, labels)):
            bin_edges, bin_contents, _ = self._root_hist_to_numpy(hist)

            if normalize and bin_contents.sum() > 0:
                bin_contents = bin_contents / bin_contents.sum()

            hep.histplot(
                bin_contents,
                bins=bin_edges,
                ax=ax,
                label=label,
                histtype='step',
                linewidth=2,
                color=colors[i % len(colors)]
            )

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if logy:
            ax.set_yscale('log')

        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add CMS label
        hep.cms.label(cms_label, data=False, lumi="Phase-2", ax=ax, loc=0)

        self.save_plot(fig, output_dir, name)

    def plot_resolution(
        self,
        hist: ROOT.TH2,
        output_dir: Path,
        name: str,
        title: str = "",
        xlabel: str = "",
        ylabel: str = "Resolution",
        cms_label: str = "Preliminary",
    ):
        """
        Plot resolution with mean and RMS per bin (profile).

        Args:
            hist: ROOT TH2 histogram (x: variable, y: resolution)
            output_dir: Output directory
            name: Filename (without extension)
            title: Plot title
            xlabel: X-axis label
            ylabel: Y-axis label
            cms_label: CMS label
        """
        # Create profile from 2D histogram
        profile = hist.ProfileX(f"{name}_profile")

        # Convert to numpy
        n_bins = profile.GetNbinsX()
        bin_centers = np.array([profile.GetBinCenter(i) for i in range(1, n_bins + 1)])
        means = np.array([profile.GetBinContent(i) for i in range(1, n_bins + 1)])
        errors = np.array([profile.GetBinError(i) for i in range(1, n_bins + 1)])

        fig, ax = plt.subplots()

        # Plot profile
        ax.errorbar(
            bin_centers,
            means,
            yerr=errors,
            fmt='o',
            markersize=6,
            capsize=3,
            color='blue',
            label='Mean resolution'
        )

        # Add zero line
        ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.7)

        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        ax.legend()

        # Add CMS label
        hep.cms.label(cms_label, data=False, lumi="Phase-2", ax=ax, loc=0)

        self.save_plot(fig, output_dir, name)
