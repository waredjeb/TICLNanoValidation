"""ROOT-histogram -> matplotlib/mplhep plotting, in CMS style.

Decoupled from analysis logic: it takes ROOT histograms and an
:class:`~ticlNanoVal.config.schema.OutputConfig`, and knows nothing about
matching or modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mplhep as hep  # noqa: E402
import numpy as np  # noqa: E402
import ROOT  # noqa: E402

from ..config.schema import OutputConfig  # noqa: E402

_STYLE_DONE = False


def _ensure_style(out: OutputConfig):
    global _STYLE_DONE
    if _STYLE_DONE:
        return
    plt.style.use(hep.style.CMS)
    plt.rcParams["figure.figsize"] = (out.figure_width, out.figure_height)
    plt.rcParams["figure.dpi"] = out.dpi
    plt.rcParams["text.usetex"] = False
    plt.rcParams["mathtext.default"] = "regular"
    _STYLE_DONE = True


class Plotter:
    def __init__(self, out: OutputConfig, cms_label: str = "Preliminary"):
        self.out = out
        self.cms_label = cms_label
        _ensure_style(out)

    # -- ROOT -> numpy ----------------------------------------------------- #
    @staticmethod
    def _h1(h: "ROOT.TH1"):
        n = h.GetNbinsX()
        edges = np.array([h.GetBinLowEdge(i) for i in range(1, n + 2)])
        vals = np.array([h.GetBinContent(i) for i in range(1, n + 1)])
        errs = np.array([h.GetBinError(i) for i in range(1, n + 1)])
        return edges, vals, errs

    @staticmethod
    def _h2(h: "ROOT.TH2"):
        nx, ny = h.GetNbinsX(), h.GetNbinsY()
        xe = np.array([h.GetXaxis().GetBinLowEdge(i) for i in range(1, nx + 2)])
        ye = np.array([h.GetYaxis().GetBinLowEdge(i) for i in range(1, ny + 2)])
        z = np.array(
            [[h.GetBinContent(i, j) for i in range(1, nx + 1)] for j in range(1, ny + 1)]
        )
        return xe, ye, z

    def _label(self, ax):
        hep.cms.label(self.cms_label, data=False, lumi="Phase-2", ax=ax, loc=0)

    def save(self, fig, output_dir: Path, name: str):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        if self.out.save_png:
            fig.savefig(output_dir / f"{name}.png", bbox_inches="tight")
        if self.out.save_pdf:
            fig.savefig(output_dir / f"{name}.pdf", bbox_inches="tight")
        plt.close(fig)

    # -- plot kinds -------------------------------------------------------- #
    def hist1d(self, h, output_dir, name, xlabel="", ylabel="Entries", logy=False):
        edges, vals, errs = self._h1(h)
        fig, ax = plt.subplots()
        hep.histplot(vals, bins=edges, yerr=errs, ax=ax, histtype="step", linewidth=2)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if logy:
            ax.set_yscale("log")
            ax.set_ylim(bottom=0.5)
        ax.grid(True, alpha=0.3)
        self._label(ax)
        self.save(fig, output_dir, name)

    def hist2d(self, h, output_dir, name, xlabel="", ylabel="", zlabel="Entries"):
        xe, ye, z = self._h2(h)
        fig, ax = plt.subplots(figsize=(self.out.figure_width + 1, self.out.figure_height))
        im = ax.pcolormesh(xe, ye, z, cmap="viridis", shading="auto")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label(zlabel)
        self._label(ax)
        self.save(fig, output_dir, name)

    def efficiency(
        self, passed_h, total_h, output_dir, name, xlabel="", ylabel="Efficiency"
    ):
        _, passed, _ = self._h1(passed_h)
        edges, total, _ = self._h1(total_h)
        centers = (edges[:-1] + edges[1:]) / 2
        eff = np.divide(passed, total, out=np.zeros_like(passed, float), where=total > 0)
        # binomial (normal-approx) errors
        err = np.divide(
            np.sqrt(np.clip(eff * (1 - eff), 0, None) / np.where(total > 0, total, 1)),
            1.0,
        )
        err = np.where(total > 0, 1.96 * err, 0.0)
        elo = np.clip(eff - np.clip(eff - err, 0, 1), 0, 1)
        ehi = np.clip(np.clip(eff + err, 0, 1) - eff, 0, 1)
        fig, ax = plt.subplots()
        ax.errorbar(centers, eff, yerr=[elo, ehi], fmt="o", markersize=6, capsize=3)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_ylim(-0.05, 1.15)
        ax.axhline(1.0, color="gray", ls="--", lw=1, alpha=0.5)
        ax.grid(True, alpha=0.3)
        self._label(ax)
        self.save(fig, output_dir, name)

    def compare1d(
        self, hists: List, labels: List[str], output_dir, name, xlabel="", ylabel="Entries"
    ):
        fig, ax = plt.subplots()
        for h, label in zip(hists, labels):
            edges, vals, _ = self._h1(h)
            hep.histplot(vals, bins=edges, ax=ax, label=label, histtype="step", linewidth=2)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.legend()
        ax.grid(True, alpha=0.3)
        self._label(ax)
        self.save(fig, output_dir, name)
